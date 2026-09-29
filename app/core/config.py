"""Local, per-machine app configuration (API key, model, preferences).

Stored under the user's home directory so it never ends up in the repo /
portable build. Never commit this file or print the key to logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".fillicity"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_api_key() -> str:
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key
    return load_config().get("openrouter_api_key", "").strip()


def set_api_key(key: str) -> None:
    data = load_config()
    data["openrouter_api_key"] = key.strip()
    save_config(data)


def get_model() -> str:
    env_model = os.environ.get("OPENROUTER_MODEL", "").strip()
    if env_model:
        return env_model
    return load_config().get("model", "").strip() or DEFAULT_MODEL


def set_model(model: str) -> None:
    data = load_config()
    data["model"] = model.strip() or DEFAULT_MODEL
    save_config(data)
