#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер контекстных меню
"""

import sys
import subprocess
from typing import List, Callable
from PyQt5.QtWidgets import QMenu, QMessageBox, QAction
from PyQt5.QtCore import QPoint, Qt

from models import Host, validate_ip_or_hostname
from host_manager import HostManager
from ui_components import UIComponents
from constants import (
    get_menu_style, SVG_MAINTENANCE, SVG_ONLINE, SVG_WAITING,
    get_svg_add_group, get_svg_delete, get_svg_ping, get_svg_edit
)
from data_manager import DataManager

class ContextMenuManager:
    """
    Класс для управления контекстными меню таблицы
    """

    def __init__(self, parent, table, table_model, groups: List[str], 
                 theme_getter: Callable, data_manager: DataManager):
        """
        Инициализация менеджера контекстных меню
        
        Args:
            parent: Родительский виджет (MainWindow)
            table: Виджет таблицы
            table_model: Модель таблицы
            groups: Список групп
            theme_getter: Функция получения текущей темы
            data_manager: Менеджер данных
        """
        self._parent = parent
        self._table = table
        self._table_model = table_model
        self._groups = groups
        self._get_theme = theme_getter
        self._data_manager = data_manager

    def update_groups(self, groups):
        """Обновление списка групп"""
        self._groups = groups

    def show_host_context_menu(self, position: QPoint) -> None:
        """Показ контекстного меню для хоста"""
        row = self._table.rowAt(position.y())
        if row < 0:
            return

        theme = self._get_theme()
        menu = QMenu()
        menu.setStyleSheet(get_menu_style(theme))

        action_ping = menu.addAction(UIComponents._get_qicon(get_svg_ping(theme)), "Пинг в CMD")
        action_edit = menu.addAction(UIComponents._get_qicon(get_svg_edit(theme)), "Редактировать")
        action_delete = menu.addAction(UIComponents._get_qicon(get_svg_delete(theme)), "Удалить")
        menu.addSeparator()
        
        host = self._table_model.get_host(row)
        if host:
            if host.status == "MAINTENANCE":
                action_maint = menu.addAction(UIComponents._get_qicon(SVG_ONLINE), "Снять с тех.обслуживания")
            else:
                action_maint = menu.addAction(UIComponents._get_qicon(SVG_MAINTENANCE), "Поставить на тех.обслуживание")

            if host.notifications_enabled:
                action_notify = menu.addAction(UIComponents._get_qicon(SVG_WAITING), "Отключить уведомления")
            else:
                action_notify = menu.addAction(UIComponents._get_qicon(SVG_ONLINE), "Включить уведомления")
        # ---
        
        action = menu.exec_(self._table.viewport().mapToGlobal(position))

        if action == action_ping:
            self._ping_host_cmd(row)
        elif action == action_edit:
            HostManager.edit_host(self._parent, row, self._table_model, self._groups, self._data_manager)
        elif action == action_delete:
            HostManager.delete_host(self._parent, row, self._table_model, self._data_manager)
        elif action == action_maint:
            HostManager.toggle_maintenance(self._parent, row, self._table_model, self._data_manager)
        elif action == action_notify:
            HostManager.toggle_notifications(self._parent, row, self._table_model, self._data_manager)

    def show_bulk_menu(self, sender):
        """Показ меню массовых действий"""
        theme = self._get_theme()
        menu = QMenu(self._parent)
        menu.setStyleSheet(get_menu_style(theme))

        action_maint = menu.addAction(UIComponents._get_qicon(SVG_MAINTENANCE), "Переключить тех.обслуживание")
        action_group = menu.addAction(UIComponents._get_qicon(get_svg_add_group(theme)), "Изменить группу")
        action_notify = menu.addAction(UIComponents._get_qicon(SVG_WAITING), "Переключить уведомления")
        menu.addSeparator()
        action_delete = menu.addAction(UIComponents._get_qicon(get_svg_delete(theme)), "Удалить выбранные")

        action = menu.exec_(sender.mapToGlobal(sender.rect().bottomLeft()))

        if action == action_maint:
            HostManager.toggle_maintenance_selected(self._parent, self._table_model, self._data_manager)
        elif action == action_group:
            HostManager.change_group_selected(self._parent, self._table_model, self._groups, self._data_manager)
        elif action == action_notify:
            HostManager.toggle_notifications_selected(self._parent, self._table_model, self._data_manager)
        elif action == action_delete:
            HostManager.delete_selected(self._parent, self._table_model, self._data_manager)

    def show_header_context_menu(self, pos: QPoint, config) -> None:
        """Контекстное меню заголовка таблицы"""
        header = self._table.horizontalHeader()
        menu = QMenu(self._parent)
        menu.setStyleSheet(get_menu_style(config.theme))
        
        from table_model import HostTableModel
        column_names = HostTableModel.COLUMNS
        
        for i, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self._table.isColumnHidden(i))
            if i == 1:  # Не даем скрыть колонку "Название"
                action.setEnabled(False)
                
            def toggle_col(checked, col_idx=i):
                self._table.setColumnHidden(col_idx, not checked)
                if hasattr(self._parent, 'update_hidden_columns_config'):
                    self._parent.update_hidden_columns_config()
                
            action.triggered.connect(toggle_col)
            
        menu.exec_(header.mapToGlobal(pos))

    def _ping_host_cmd(self, row: int):
        """Открытие CMD с ping -t"""
        host = self._table_model.get_host(row)
        if not host:
            return
        
        if not validate_ip_or_hostname(host.ip):
            QMessageBox.warning(self._parent, "Ошибка", f"Некорректный IP адрес: {host.ip}")
            return
        
        try:
            if sys.platform == "win32":
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', 'ping', '-t', host.ip])
            else:
                subprocess.Popen(['xterm', '-e', f'ping {host.ip}'])
        except Exception as e:
            QMessageBox.warning(self._parent, "Ошибка", f"Не удалось открыть терминал: {e}")
