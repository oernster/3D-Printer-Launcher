# styles.py
from __future__ import annotations

THEMES = {
    "dark": {
        "bg": "#0B0E14",
        "panel": "#0F1422",
        "card": "#121A2C",
        "border": "rgba(255,255,255,0.10)",
        "border_strong": "rgba(255,255,255,0.14)",
        "text": "#EAF0FF",
        "text_muted": "rgba(234,240,255,0.62)",
        "grad_a": "#7C5CFF",
        "grad_b": "#FFB84D",
        "btn": "rgba(255,255,255,0.06)",
        "btn_hover": "rgba(255,255,255,0.10)",
        "btn_pressed": "rgba(255,255,255,0.05)",
        "btn_disabled": "rgba(255,255,255,0.03)",
        "log_bg": "#070A10",
        "log_text": "#D7E1FF",
        "ok": "#3DDC97",
        "stopped": "#FF5D5D",
        "warn": "#FFCC66",
        "error": "#FF5D5D",
    },
    "light": {
        "bg": "#F4F6FB",
        "panel": "#FFFFFF",
        "card": "#FFFFFF",
        "border": "rgba(10,14,22,0.14)",
        "border_strong": "rgba(10,14,22,0.20)",
        "text": "#0A0E16",
        "text_muted": "rgba(10,14,22,0.60)",
        "grad_a": "#6E56FF",
        "grad_b": "#FFB454",
        "btn": "rgba(10,14,22,0.05)",
        "btn_hover": "rgba(10,14,22,0.08)",
        "btn_pressed": "rgba(10,14,22,0.04)",
        "btn_disabled": "rgba(10,14,22,0.03)",
        "log_bg": "#F7F9FF",
        "log_text": "#101522",
        "ok": "#22C55E",
        "stopped": "#EF4444",
        "warn": "#F59E0B",
        "error": "#EF4444",
    },
}


def build_styles(theme: str = "dark") -> str:
    t = THEMES.get(theme, THEMES["dark"])

    return f"""
    /* Base */
    QMainWindow {{ background: {t["bg"]}; }}
    QWidget#Root {{ background: {t["bg"]}; }}

    /* Panels (explicit so light mode is actually light) */
    QWidget#LeftPanel, QWidget#RightPanel {{
        background: {t["panel"]};
        border: 1px solid {t["border"]};
        border-radius: 18px;
    }}

    /* Explicit panel backgrounds (this fixes your “light mode isn’t light”) */
    QWidget#LeftPanel, QWidget#RightPanel {{
        background: {t["panel"]};
        border: 1px solid {t["border"]};
        border-radius: 18px;
    }}

    QLabel {{ color: {t["text"]}; }}
    #PanelTitle {{ font-size: 14px; font-weight: 900; margin-left: 2px; }}

    /* Cards */
    QWidget#AppCard {{
        background: {t["card"]};
        border: 1px solid {t["border"]};
        border-radius: 18px;
    }}
    QLabel#CardTitle {{ font-size: 16px; font-weight: 900; }}
    QLabel#CardMeta {{ color: {t["text_muted"]}; font-size: 12px; }}

    /* General buttons */
    QPushButton {{
        background: {t["btn"]};
        border: 1px solid {t["border"]};
        padding: 8px 12px;
        border-radius: 12px;
        color: {t["text"]};
        font-weight: 800;
    }}
    QPushButton:hover {{
        background: {t["btn_hover"]};
        border: 1px solid {t["border_strong"]};
    }}
    QPushButton:pressed {{ background: {t["btn_pressed"]}; }}
    QPushButton:disabled {{
        color: {t["text_muted"]};
        background: {t["btn_disabled"]};
        border: 1px solid {t["border"]};
    }}

    /* Small icon buttons for theme toggle */
    QPushButton#IconButton {{
        padding: 6px 10px;
        border-radius: 12px;
        font-weight: 900;
    }}

    /* Highlight the active theme button */
    QPushButton#IconButton[active="true"] {{
        background: {t["btn_hover"]};
        border: 1px solid {t["border_strong"]};
    }}

    /* Gradient primary buttons */
    QPushButton#PrimaryButton {{
        border: 0px;
        padding: 9px 14px;
        border-radius: 14px;
        color: white;
        font-weight: 950;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {t["grad_a"]},
            stop:1 {t["grad_b"]}
        );
    }}

    /* Start/Stop buttons */
    QPushButton#StartButton {{
        border: 0px;
        padding: 8px 12px;
        border-radius: 12px;
        color: #0B0E14;
        font-weight: 950;
        background: {t["ok"]};
    }}
    QPushButton#StopButton {{
        border: 0px;
        padding: 8px 12px;
        border-radius: 12px;
        color: #0B0E14;
        font-weight: 950;
        background: {t["stopped"]};
    }}

    /* Status badge */
    QLabel#StatusBadge {{
        border-radius: 12px;
        padding: 3px 10px;
        font-weight: 950;
        color: #0B0E14;
        min-width: 92px;
    }}
    QLabel#StatusBadge[kind="ok"]      {{ background: {t["ok"]}; }}
    QLabel#StatusBadge[kind="stopped"] {{ background: {t["stopped"]}; }}
    QLabel#StatusBadge[kind="warn"]    {{ background: {t["warn"]}; }}
    QLabel#StatusBadge[kind="error"]   {{ background: {t["error"]}; }}

    /* Log */
    #LogView {{
        background: {t["log_bg"]};
        border: 1px solid {t["border"]};
        border-radius: 16px;
        padding: 10px;
        color: {t["log_text"]};
        font-family: Consolas, "Cascadia Mono", monospace;
        font-size: 12px;
    }}

    /* Menus */
    QMenuBar {{ background: {t["bg"]}; color: {t["text"]}; }}
    QMenuBar::item:selected {{ background: {t["btn_hover"]}; border-radius: 6px; }}
    QMenu {{ background: {t["panel"]}; color: {t["text"]}; border: 1px solid {t["border"]}; }}
    QMenu::item:selected {{ background: {t["btn_hover"]}; }}

    /* Scroll area that holds the cards */
    QWidget#CardsContainer {{
        background: {t["panel"]};
    }}
    QScrollArea#CardsScroll {{
        background: transparent;
        border: 0px;
    }}

    QScrollArea {{ background: transparent; }}
    """
