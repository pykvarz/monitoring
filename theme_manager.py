#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ThemeManager - Управление темами оформления приложения
"""

from typing import Callable
from PyQt5.QtWidgets import QMainWindow, QPushButton, QHBoxLayout, QLabel, QTableView
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QByteArray, Qt
from models import AppConfig, HostStatus
from storage import StorageManager
from table_model import HostTableModel
from constants import (
    get_main_style, get_table_style, get_dashboard_style,
    get_button_style, get_stat_card_style,
    get_svg_total, get_svg_add_host, get_svg_add_group,
    get_svg_import, get_svg_export, get_svg_scan, get_svg_bulk,
    get_svg_theme, get_svg_settings, get_svg_delete,
    COLOR_TOTAL
)
from ui_components import UIComponents


class ThemeManager:
    """Менеджер управления темами оформления"""

    def __init__(self, main_window: QMainWindow, config: AppConfig, 
                 storage: StorageManager, table: QTableView, 
                 table_model: HostTableModel):
        """
        Инициализация менеджера тем
        
        Args:
            main_window: Главное окно приложения
            config: Конфигурация приложения
            storage: Менеджер хранения данных
            table: Таблица с хостами
            table_model: Модель таблицы
        """
        self._window = main_window
        self._config = config
        self._storage = storage
        self._table = table
        self._table_model = table_model
        
        # Ссылки на UI компоненты (будут установлены позже)
        self._dashboard_frame = None
        self._dashboard_labels = None
        self._toolbar_layout = None
        self._filters_layout = None
        self._refresh_callback = None

    def set_ui_components(self, dashboard_frame, dashboard_labels, 
                          toolbar_layout, filters_layout, refresh_callback: Callable = None):
        """
        Установка ссылок на UI компоненты
        
        Args:
            dashboard_frame: Фрейм дашборда
            dashboard_labels: Словарь меток дашборда
            toolbar_layout: Лэйаут тулбара
            filters_layout: Лэйаут фильтров
            refresh_callback: Callback для обновления дашборда
        """
        self._dashboard_frame = dashboard_frame
        self._dashboard_labels = dashboard_labels
        self._toolbar_layout = toolbar_layout
        self._filters_layout = filters_layout
        self._refresh_callback = refresh_callback

    def get_current_theme(self) -> str:
        """Получение текущей темы"""
        return getattr(self._config, 'theme', 'light')

    def toggle_theme(self) -> None:
        """Переключение между светлой и темной темой"""
        current_theme = self.get_current_theme()
        new_theme = 'dark' if current_theme == 'light' else 'light'
        
        # Сохраняем новую тему
        self._config.theme = new_theme
        self._storage.save_config(self._config)
        
        # Применяем стили
        self._apply_theme(new_theme)
        
        # Показываем уведомление
        self._window.statusBar().showMessage(
            f"Тема изменена на {'темную' if new_theme == 'dark' else 'светлую'}", 
            3000
        )

    def _apply_theme(self, theme: str) -> None:
        """
        Применение темы ко всем компонентам
        
        Args:
            theme: Название темы ('light' или 'dark')
        """
        # Основные стили окна
        self._window.setStyleSheet(get_main_style(theme))
        
        if self._dashboard_frame:
            self._dashboard_frame.setStyleSheet(get_dashboard_style(theme))
        
        if self._table:
            self._table.setStyleSheet(get_table_style(theme))
        
        if self._table_model:
            self._table_model.set_theme(theme)
        
        # Обновляем карточки в дашборде
        if self._dashboard_labels:
            self._update_dashboard_cards(theme)
        
        # Обновляем иконки кнопок в тулбаре
        if self._toolbar_layout:
            self._update_toolbar_buttons(theme)
        
        # Обновляем кнопки в фильтрах
        if self._filters_layout:
            self._update_filter_buttons(theme)
        
        # Обновляем иконку окна
        self.set_window_icon(theme)
        
        # Обновляем дашборд
        if self._refresh_callback:
            self._refresh_callback()

    def _update_dashboard_cards(self, theme: str) -> None:
        """Обновление стилей карточек дашборда"""
        for key, label in self._dashboard_labels.items():
            if key == 'total':
                color = COLOR_TOTAL
            else:
                color = getattr(HostStatus, key.upper()).color
            label.setStyleSheet(get_stat_card_style(color, theme))

    def _update_toolbar_buttons(self, theme: str) -> None:
        """Обновление иконок и стилей кнопок тулбара"""
        buttons_map = {
            "добавить узел": get_svg_add_host,
            "создать группу": get_svg_add_group,
            "импорт": get_svg_import,
            "экспорт": get_svg_export,
            "проверить": get_svg_scan,
            "массовые действия": get_svg_bulk,
            "тема": get_svg_theme,
            "настройки": get_svg_settings
        }

        for i in range(self._toolbar_layout.count()):
            widget = self._toolbar_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet(get_button_style(theme))
                btn_text = widget.text().lower().strip()
                if btn_text in buttons_map:
                    svg_func = buttons_map[btn_text]
                    widget.setIcon(UIComponents._get_qicon(svg_func(theme)))

    def _update_filter_buttons(self, theme: str) -> None:
        """Обновление кнопок в панели фильтров"""
        for i in range(self._filters_layout.count()):
            item = self._filters_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), QPushButton):
                btn = item.widget()
                btn.setStyleSheet(get_button_style(theme))
                if "сбросить" in btn.text().lower():
                    btn.setIcon(UIComponents._get_qicon(get_svg_delete(theme)))

    def set_window_icon(self, theme: str = "light") -> None:
        """
        Установка иконки главного окна
        
        Args:
            theme: Название темы
        """
        svg_data = get_svg_total(theme)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self._window.setWindowIcon(QIcon(pixmap))

    def apply_initial_theme(self) -> None:
        """Применение начальной темы при запуске приложения"""
        theme = self.get_current_theme()
        self._apply_theme(theme)
