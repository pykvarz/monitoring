#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TableSettingsManager - Управление настройками таблицы
Инкапсулирует логику работы с настройками колонок (ширина, порядок, скрытие)
"""

import logging
from typing import Dict
from PyQt5.QtWidgets import QTableView
from PyQt5.QtCore import Qt, QObject, pyqtSlot

from models import AppConfig
from interfaces import IStorageRepository


class TableSettingsManager(QObject):
    """
    Менеджер настроек таблицы.
    
    Отвечает за:
    - Восстановление настроек колонок при запуске
    - Сохранение изменений ширины, порядка и видимости колонок
    - Обработку сигналов от QHeaderView
    """
    
    def __init__(self, table: QTableView, config: AppConfig, storage: IStorageRepository):
        super().__init__()
        self._table = table
        self._config = config
        self._storage = storage
        
        # Подключение сигналов
        self._connect_signals()
        
        logging.debug("TableSettingsManager initialized")
    
    def _connect_signals(self) -> None:
        """Подключение сигналов от таблицы"""
        header = self._table.horizontalHeader()
        header.sectionResized.connect(self._on_column_resized)
        header.sectionMoved.connect(self._on_column_moved)
    
    def restore_settings(self) -> None:
        """Восстановление настроек таблицы из конфигурации"""
        header = self._table.horizontalHeader()
        
        # 1. Восстановление ширины колонок
        if self._config.column_widths:
            for col_idx_str, width in self._config.column_widths.items():
                try:
                    col_idx = int(col_idx_str)
                    if 0 <= col_idx < header.count():
                        self._table.setColumnWidth(col_idx, width)
                except (ValueError, TypeError):
                    logging.warning(f"Invalid column width config: {col_idx_str}={width}")
        
        # 2. Восстановление порядка колонок
        if getattr(self._config, 'column_order', None):
            if len(self._config.column_order) == header.count():
                try:
                    # Блокируем сигналы во время перестановки
                    header.blockSignals(True)
                    for visual_idx, logical_idx in enumerate(self._config.column_order):
                        if 0 <= logical_idx < header.count():
                            current_visual = header.visualIndex(logical_idx)
                            if current_visual != visual_idx:
                                header.moveSection(current_visual, visual_idx)
                finally:
                    header.blockSignals(False)
                    
                logging.debug(f"Restored column order: {self._config.column_order}")
        
        # 3. Восстановление скрытых колонок
        if self._config.hidden_columns:
            for col_idx in self._config.hidden_columns:
                if 0 <= col_idx < header.count():
                    self._table.setColumnHidden(col_idx, True)
                    
            logging.debug(f"Restored hidden columns: {self._config.hidden_columns}")
    
    @pyqtSlot(int, int, int)
    def _on_column_resized(self, index: int, old_size: int, new_size: int) -> None:
        """Обработка изменения ширины колонки"""
        if not self._config.column_widths:
            self._config.column_widths = {}
        
        self._config.column_widths[str(index)] = new_size
        self._storage.save_config(self._config)
        
        logging.debug(f"Column {index} resized: {old_size} -> {new_size}")
    
    @pyqtSlot(int, int, int)
    def _on_column_moved(self, logical_index: int, old_visual: int, new_visual: int) -> None:
        """Обработка перемещения колонки"""
        header = self._table.horizontalHeader()
        
        # Сохраняем текущий порядок колонок
        new_order = [header.logicalIndex(i) for i in range(header.count())]
        self._config.column_order = new_order
        self._storage.save_config(self._config)
        
        logging.debug(f"Column {logical_index} moved: {old_visual} -> {new_visual}")
        logging.debug(f"New column order: {new_order}")
    
    def update_hidden_columns(self) -> None:
        """
        Обновление списка скрытых колонок в конфигурации.
        Вызывается из контекстного меню после скрытия/показа колонок.
        """
        header = self._table.horizontalHeader()
        hidden = []
        
        for i in range(header.count()):
            if self._table.isColumnHidden(i):
                hidden.append(i)
        
        self._config.hidden_columns = hidden
        self._storage.save_config(self._config)
        
        logging.debug(f"Updated hidden columns: {hidden}")
