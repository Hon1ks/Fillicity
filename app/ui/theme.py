"""Dark, modern QSS theme shared by every window in the app."""

ACCENT = "#7C5CFC"
ACCENT_HOVER = "#8F73FF"
ACCENT_PRESSED = "#6746E0"
BG = "#15151C"
PANEL = "#1D1D27"
PANEL_ALT = "#24242F"
BORDER = "#2E2E3B"
TEXT = "#EDEDF4"
TEXT_DIM = "#9797A8"
SUCCESS = "#3DD68C"
DANGER = "#FF6B6B"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

QLabel {{
    background-color: transparent;
}}

#Header {{
    background-color: transparent;
}}
#TitleLabel {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
#SubtitleLabel {{
    font-size: 12px;
    color: {TEXT_DIM};
}}

#Card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

QPushButton {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #2C2C3A;
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: #26262F;
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: {PANEL};
}}

QPushButton#Primary {{
    background-color: {ACCENT};
    border: none;
    color: white;
}}
QPushButton#Primary:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#Primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton#Primary:disabled {{
    background-color: #3C3555;
    color: #8B85A5;
}}

QPushButton#Success {{
    background-color: {SUCCESS};
    border: none;
    color: #0B2318;
}}
QPushButton#Success:hover {{
    background-color: #4EE39C;
}}
QPushButton#Success:disabled {{
    background-color: #24402F;
    color: #6B8B7A;
}}

QPushButton#Ghost {{
    background-color: transparent;
    border: 1px solid {BORDER};
}}
QPushButton#Ghost:hover {{
    border-color: {ACCENT};
}}

QPushButton#IconButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}}
QPushButton#IconButton:hover {{
    background-color: {PANEL_ALT};
}}

QListWidget {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px;
    border-radius: 8px;
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QComboBox {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL_ALT};
    selection-background-color: {ACCENT};
}}

QTableWidget {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: #3A3354;
}}
QTableWidget::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #6A6A7C;
    border-radius: 3px;
    background-color: {PANEL};
}}
QTableWidget::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QHeaderView::section {{
    background-color: {PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px 6px;
}}

QTextEdit, QLineEdit {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: {ACCENT};
}}
QTextEdit:focus, QLineEdit:focus {{
    border-color: {ACCENT};
}}

QLabel#StatusLabel {{
    color: {TEXT_DIM};
}}

QLabel#SectionTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
