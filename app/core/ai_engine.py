"""Calls a vision-capable model via OpenRouter (OpenAI-compatible API) to
(1) locate the fillable fields in a screenshot and (2) decide what value from
the user's source documents belongs in each one.

OpenRouter docs: https://openrouter.ai/docs
"""
from __future__ import annotations

import json
import re

from app.core.config import DEFAULT_MODEL
from app.core.models import CaptureRegion, FieldFill, FillPlan, SourceDocument

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """You are Fillicity, a careful vision assistant that finds fillable \
fields (text inputs, checkboxes, dropdowns, signature lines, etc.) inside a screenshot \
of a form or document, and proposes what value belongs in each field based on the \
reference data the user supplied.

Rules:
- Only report fields that are actually empty and fillable, or that need correction.
- Coordinates MUST be pixel coordinates within the screenshot you were given, \
top-left origin, matching the exact image pixel dimensions stated in the prompt.
- Only propose a value when the reference data actually contains the information. \
Never invent data (no fake names, numbers, dates, addresses, etc.). If no matching \
value exists for a visible field, skip that field entirely.
- Keep values short and exactly as they should be typed into the field.
- Do NOT think out loud, do NOT explain your reasoning, do NOT narrate which \
field you're looking at. Output NOTHING except the JSON object below - no prose \
before or after it, no markdown code fences. Your entire response must start \
with "{" and end with "}".
{"fields": [{"label": str, "value": str, "x": int, "y": int, "width": int, \
"height": int, "confidence": float}], "notes": str}
"notes" is a one-sentence, human-readable summary (in the same language as the \
reference data) of what you filled or why nothing was filled.
"""

MAX_OUTPUT_TOKENS = 8192


class AIEngineError(Exception):
    pass


def analyze(
    api_key: str,
    region: CaptureRegion,
    screenshot_b64: str,
    image_width: int,
    image_height: int,
    sources: list[SourceDocument],
    model: str = DEFAULT_MODEL,
) -> FillPlan:
    if not api_key:
        raise AIEngineError("Не задан OpenRouter API ключ. Откройте Настройки и укажите его.")

    from openai import OpenAI

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Screenshot pixel size: {image_width}x{image_height}.\n"
                "Reference data the user wants filled into this form follows."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
        },
    ]

    if not sources:
        content.append({"type": "text", "text": "(No reference data was provided.)"})

    for src in sources:
        if src.kind == "image":
            content.append({"type": "text", "text": f"Reference image: {src.name}"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{src.media_type};base64,{src.image_b64}"},
                }
            )
        else:
            snippet = src.text[:20000]
            content.append(
                {"type": "text", "text": f"Reference file '{src.name}':\n{snippet}"}
            )

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            extra_headers={
                "HTTP-Referer": "https://github.com/fillicity/fillicity",
                "X-Title": "Fillicity",
            },
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
    except Exception as exc:  # openai raises various APIError subclasses
        raise AIEngineError(f"Ошибка запроса к AI ({model}): {exc}") from exc

    choice = response.choices[0] if response.choices else None
    raw_text = (choice.message.content or "") if choice else ""
    finish_reason = getattr(choice, "finish_reason", "unknown") if choice else "no choices"

    if finish_reason == "length":
        raise AIEngineError(
            f"Модель {model} исчерпала лимит токенов, не дойдя до ответа "
            "(finish_reason=length) — обычно это модели, которые сначала долго "
            "«размышляют» текстом и не укладываются в бюджет. Смените модель в "
            "Настройках на менее «многословную», например anthropic/claude-sonnet-4.5, "
            "openai/gpt-4o-mini или google/gemini-2.5-flash."
        )
    if not raw_text.strip():
        raise AIEngineError(
            f"Модель {model} вернула пустой ответ (finish_reason={finish_reason}). "
            "Попробуйте другую модель в Настройках — не все модели на OpenRouter "
            "умеют работать с изображениями и строгим JSON-форматом."
        )
    data = _parse_json(raw_text)

    fields = []
    for item in data.get("fields", []):
        try:
            fields.append(
                FieldFill(
                    label=str(item.get("label", "")),
                    value=str(item.get("value", "")),
                    x=region.x + int(item["x"]),
                    y=region.y + int(item["y"]),
                    width=max(1, int(item.get("width", 40))),
                    height=max(1, int(item.get("height", 24))),
                    confidence=float(item.get("confidence", 1.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return FillPlan(region=region, fields=fields, notes=str(data.get("notes", "")))


def _parse_json(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text).strip()
    raw_text = re.sub(r"```$", "", raw_text).strip()
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise AIEngineError(f"AI вернул неожиданный ответ:\n{raw_text[:500]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AIEngineError(f"Не удалось разобрать JSON от AI: {exc}") from exc
