from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.core import config

# Vision-capable models that reliably return strict JSON. Free-tier models are
# omitted on purpose: they are rate-limited (429) or "think out loud" and never
# reach the JSON. The box stays editable for any other OpenRouter model id.
RECOMMENDED_MODELS = [
    ("anthropic/claude-sonnet-4.5", "точнее всего размечает поля"),
    ("openai/gpt-4o-mini", "дёшево и быстро"),
    ("google/gemini-2.5-flash", "дёшево, хорошо читает мелкий текст"),
    ("openai/gpt-4o", "надёжный универсал"),
]


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки Fillicity")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("OpenRouter API ключ")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Ключ хранится локально в ~/.fillicity/config.json и используется "
            "для распознавания форм и подбора значений. Получить ключ: "
            "openrouter.ai/keys"
        )
        hint.setObjectName("StatusLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.key_input = QLineEdit(config.get_api_key())
        self.key_input.setPlaceholderText("sk-or-v1-...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key_input)

        show_btn = QPushButton("Показать/скрыть")
        show_btn.setObjectName("Ghost")
        show_btn.clicked.connect(self._toggle_echo)
        layout.addWidget(show_btn)

        model_title = QLabel("Модель (OpenRouter)")
        model_title.setObjectName("SectionTitle")
        layout.addWidget(model_title)

        model_hint = QLabel(
            "Выберите из списка проверенных или впишите любой ID модели с поддержкой "
            "изображений (openrouter.ai/models). Бесплатные (:free) часто отвечают "
            "ошибкой 429 или не возвращают JSON."
        )
        model_hint.setObjectName("StatusLabel")
        model_hint.setWordWrap(True)
        layout.addWidget(model_hint)

        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        for model_id, note in RECOMMENDED_MODELS:
            self.model_input.addItem(f"{model_id}  —  {note}", model_id)
        self.model_input.setEditText(config.get_model())
        self.model_input.activated.connect(
            lambda i: self.model_input.setEditText(self.model_input.itemData(i))
        )
        layout.addWidget(self.model_input)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("Ghost")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _toggle_echo(self) -> None:
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _save(self) -> None:
        config.set_api_key(self.key_input.text())
        config.set_model(self.model_input.currentText().split()[0] if self.model_input.currentText().strip() else "")
        self.accept()
