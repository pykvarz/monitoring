"""
Константы и стили приложения
"""

# Цвета статусов
COLOR_ONLINE = "#28a745"
COLOR_WAITING = "#fd7e14"
COLOR_OFFLINE = "#dc3545"
COLOR_MAINTENANCE = "#6f42c1"
COLOR_TOTAL = "#007bff"

# Цвета темы (Dark Mode)
DARK_BG = "#1e1e1e"
DARK_SURFACE = "#2d2d2d"
DARK_BORDER = "#404040"
DARK_TEXT = "#e1e1e1"
DARK_TEXT_SECONDARY = "#aaaaaa"
DARK_SELECTION = "#3d5afe"

# CSS Стили

def get_table_style(theme="light"):
    if theme == "dark":
        return f"""
            QTableView {{
                border: 1px solid {DARK_BORDER};
                border-radius: 6px;
                background-color: {DARK_SURFACE};
                gridline-color: {DARK_BORDER};
                selection-background-color: {DARK_SELECTION};
                selection-color: white;
                color: {DARK_TEXT};
                show-decoration-selected: 1;
            }}
            QHeaderView::section {{
                background-color: {DARK_BG};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {DARK_BORDER};
                border-right: 1px solid {DARK_BORDER};
                font-weight: bold;
                color: {DARK_TEXT};
            }}
        """
    return """
        QTableView {
            border: 1px solid #d0d7de;
            border-radius: 6px;
            background-color: white;
            gridline-color: #bbb;
            selection-background-color: #e3f2fd;
            selection-color: #000;
            show-decoration-selected: 1;
        }
        QHeaderView::section {
            background-color: #f6f8fa;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #d0d7de;
            border-right: 1px solid #d0d7de;
            font-weight: bold;
            color: #24292f;
        }
    """

def get_dashboard_style(theme="light"):
    if theme == "dark":
        return f"""
            QFrame {{
                background-color: {DARK_BG};
                border: 1px solid {DARK_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """
    return """
        QFrame {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 6px 12px;
        }
    """

def get_stat_card_style(color, theme="light"):
    """Создание стиля для карточки статистики"""
    if theme == "dark":
        return f"""
            QLabel {{
                background-color: {DARK_SURFACE};
                border-left: 3px solid {color};
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 13px;
                min-width: 110px;
                color: {DARK_TEXT};
            }}
        """
    return f"""
        QLabel {{
            background-color: white;
            border-left: 3px solid {color};
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            min-width: 110px;
        }}
    """

def get_button_style(theme="light"):
    if theme == "dark":
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                background-color: {DARK_SURFACE};
                color: {DARK_TEXT};
            }}
            QPushButton:hover {{
                background-color: {DARK_BORDER};
            }}
            QPushButton:pressed {{
                background-color: #505050;
            }}
        """
    return """
        QPushButton {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
        }
        QPushButton:hover {
            background-color: #f8f9fa;
        }
        QPushButton:pressed {
            background-color: #e9ecef;
        }
    """

def get_main_style(theme="light"):
    if theme == "dark":
        return f"background-color: {DARK_BG}; color: {DARK_TEXT};"
    return ""

def get_menu_style(theme="light"):
    if theme == "dark":
        return f"""
            QMenu {{
                background-color: {DARK_SURFACE};
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                padding: 5px;
            }}
            QMenu::item:selected {{
                background-color: {DARK_SELECTION};
            }}
        """
    return """
        QMenu {
            background-color: white;
            border: 1px solid #ddd;
            padding: 5px;
        }
        QMenu::item {
            padding: 8px 25px 8px 20px;
        }
        QMenu::item:selected {
            background-color: #e3f2fd;
        }
    """

SCAN_LABEL_STYLE_ACTIVE = "color: #007bff; font-weight: bold;"
SCAN_LABEL_STYLE_FINISHED = "color: #28a745;"

# SVG Иконки (Paths)
# SVG Иконки (Paths в стиле Lucide)
def _get_svg_wrapper(path_data, theme="light", size=16, stroke_width=2):
    color = "#e1e1e1" if theme == "dark" else "#24292f"
    return f"""
    <svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">
        {path_data}
    </svg>
    """

def get_svg_add_host(theme="light"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>', theme)

def get_svg_add_group(theme="light"):
    return _get_svg_wrapper('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>', theme)

def get_svg_import(theme="light"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>', theme)

def get_svg_export(theme="light"):
    return _get_svg_wrapper('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>', theme)

def get_svg_scan(theme="light"):
    return _get_svg_wrapper('<path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>', theme)

def get_svg_bulk(theme="light"):
    return _get_svg_wrapper('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>', theme)

def get_svg_settings(theme="light"):
    return _get_svg_wrapper('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>', theme)

def get_svg_delete(theme="light"):
    return _get_svg_wrapper('<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>', theme)

def get_svg_edit(theme="light"):
    return _get_svg_wrapper('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4L18.5 2.5z"/>', theme)

def get_svg_theme(theme="light"):
    if theme == "dark":
        return _get_svg_wrapper('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>', theme)
    return _get_svg_wrapper('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>', theme)

def get_svg_ping(theme="light"):
    return _get_svg_wrapper('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>', theme)

def get_svg_total(theme="light"):
    return _get_svg_wrapper('<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>', theme)

SVG_ONLINE = """
<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#28a745" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
    <polyline points="22 4 12 14.01 9 11.01"/>
</svg>
"""

SVG_OFFLINE = """
<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#dc3545" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <line x1="15" y1="9" x2="9" y2="15"/>
    <line x1="9" y1="9" x2="15" y2="15"/>
</svg>
"""

SVG_WAITING = """
<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fd7e14" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <polyline points="12 6 12 12 16 14"/>
</svg>
"""

SVG_MAINTENANCE = """
<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#6f42c1" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l1.4-1.4a1 1 0 0 0 0-1.4l-1.6-1.6a1 1 0 0 0-1.4 0l-1.4 1.4z"/>
    <path d="M14.5 10.5l-8 8a2.12 2.12 0 0 1-3-3l8-8"/>
</svg>
"""
