#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterManager - Управление фильтрацией и поиском хостов
"""

from typing import List, Optional
from PyQt5.QtWidgets import QLineEdit, QComboBox, QTableView
from PyQt5.QtCore import QTimer
from models import Host, HostStatus
from table_model import HostTableModel


class FilterManager:
    """Менеджер фильтрации и поиска хостов"""

    def __init__(self, search_edit: QLineEdit, group_filter: QComboBox, 
                 status_filter: QComboBox, table: QTableView, table_model: HostTableModel):
        """
        Инициализация менеджера фильтров
        
        Args:
            search_edit: Поле для текстового поиска
            group_filter: Комбобокс для фильтрации по группам
            status_filter: Комбобокс для фильтрации по статусу
            table: Таблица с хостами
            table_model: Модель таблицы
        """
        self._search_edit = search_edit
        self._group_filter = group_filter
        self._status_filter = status_filter
        self._table = table
        self._table_model = table_model
        
        # Таймер для debounce текстового поиска (300ms задержка)
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(300)
        self._filter_timer.timeout.connect(self._apply_filters_internal)
        
        # Подключаем сигналы только если виджеты существуют
        if self._search_edit:
            self._search_edit.textChanged.connect(self._schedule_filter)
        if self._group_filter:
            self._group_filter.currentIndexChanged.connect(self.apply_filters)
        if self._status_filter:
            self._status_filter.currentIndexChanged.connect(self.apply_filters)
    
    def _schedule_filter(self) -> None:
        """Планирование фильтрации с debounce (только для текстового поиска)"""
        self._filter_timer.start()
    
    def _apply_filters_internal(self) -> None:
        """Внутренний метод применения фильтров (вызывается через таймер)"""
        self.apply_filters()

    def apply_filters(self) -> None:
        """Применение всех активных фильтров к таблице"""
        search_text = self._search_edit.text().lower() if self._search_edit else ""
        
        # Получаем фильтры только если виджеты существуют
        group_filter = None
        if self._group_filter:
            group_filter = self._group_filter.currentText().replace("📁 ", "")
            if group_filter == "Все группы":
                group_filter = None
        
        status_filter = None
        if self._status_filter:
            status_filter = self._status_filter.currentText()
            if status_filter == "📊 Все статусы":
                status_filter = None

        # Получаем данные о статусах для сопоставления заголовка и кода (ONLINE, etc)
        status_map = {s.title: s.name for s in HostStatus}

        for row in range(self._table_model.rowCount()):
            host = self._table_model.get_host(row)
            if not host:
                continue

            show = True
            
            # Поиск по имени, IP, адресу и группе
            if search_text:
                text_to_search = f"{host.name} {host.ip} {host.address} {host.group}".lower()
                show = search_text in text_to_search

            # Фильтр по группе (если активен)
            if show and group_filter:
                show = host.group == group_filter

            # Фильтр по статусу (если активен)
            if show and status_filter:
                target_status_name = status_map.get(status_filter)
                show = host.status == target_status_name

            self._table.setRowHidden(row, not show)

    def reset_filters(self) -> None:
        """Сброс всех фильтров"""
        if self._search_edit:
            self._search_edit.clear()
        if self._group_filter:
            self._group_filter.setCurrentIndex(0)
        if self._status_filter:
            self._status_filter.setCurrentIndex(0)
        # apply_filters будет вызван автоматически через сигналы

    def update_group_filter(self, groups: List[str]) -> None:
        """
        Обновление списка групп в комбобоксе
        
        Args:
            groups: Список доступных групп
        """
        if not self._group_filter:
            return  # Фильтр отключен
        
        current_group = self._group_filter.currentText()
        self._group_filter.blockSignals(True)  # Блокируем сигналы для избежания лишних перерисовок
        self._group_filter.clear()
        self._group_filter.addItem("📁 Все группы")
        self._group_filter.addItems(groups)
        
        # Восстанавливаем предыдущий выбор, если возможно
        index = self._group_filter.findText(current_group)
        if index >= 0:
            self._group_filter.setCurrentIndex(index)
        
        self._group_filter.blockSignals(False)

    def set_status_filter(self, status_title: str) -> None:
        """
        Установка фильтра по статусу
        
        Args:
            status_title: Название статуса (например, "Online")
        """
        if not self._status_filter:
            return  # Фильтр отключен
        
        index = self._status_filter.findText(status_title)
        if index >= 0:
            self._status_filter.setCurrentIndex(index)

    def get_current_search_text(self) -> str:
        """Получение текущего поискового запроса"""
        return self._search_edit.text()

    def get_current_group_filter(self) -> str:
        """Получение текущего фильтра по группе"""
        return self._group_filter.currentText().replace("📁 ", "")

    def get_current_status_filter(self) -> str:
        """Получение текущего фильтра по статусу"""
        return self._status_filter.currentText()
