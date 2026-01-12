#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TableSubscriber - Подписчик для умного обновления таблицы

Оптимизации:
- Обновляет только изменённые ячейки (не всю таблицу)
- Batching для множественных обновлений
- Debouncing для частых изменений
"""

import logging
from typing import List
from PyQt5.QtCore import QObject, QTimer

from core.host_repository import HostRepository
from models import Host


class TableSubscriber(QObject):
    """
    Подписчик для оптимизированного обновления QTableView
    
    Стратегии обновления:
    - host_added: Добавить строку в конец
    - host_updated: Обновить только изменённую строку
    - status_changed: Обновить только ячейку статуса
    - hosts_batch_updated: Batch обновление с debouncing
    - host_deleted: Удалить строку
    """
    
    def __init__(self, repository: HostRepository, table_model):
        super().__init__()
        self._repository = repository
        self._table_model = table_model
        
        # Batching для множественных обновлений
        self._pending_updates = {}
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(100)  # 100ms debounce
        self._debounce_timer.timeout.connect(self._flush_pending_updates)
        
        # Подписка на события
        repository.host_added.connect(self._on_host_added)
        repository.host_updated.connect(self._on_host_updated)
        repository.host_deleted.connect(self._on_host_deleted)
        repository.hosts_loaded.connect(self._on_hosts_loaded)
        repository.status_changed.connect(self._on_status_changed)
        repository.hosts_batch_updated.connect(self._on_batch_updated)
        
        logging.debug("TableSubscriber initialized")
    
    def _on_host_added(self, host_id: str):
        """
        Новый хост добавлен
        
        Стратегия: Полная перезагрузка (новая строка может быть вставлена в середину при сортировке)
        """
        hosts = self._repository.get_all()
        self._table_model.set_hosts(hosts)
        logging.debug(f"Table updated: host added ({host_id})")
    
    def _on_host_updated(self, host_id: str, old_host: Host, new_host: Host):
        """
        Хост обновлён
        
        Стратегия: Обновить только конкретную строку
        """
        # Добавляем в очередь для batch обновления
        self._pending_updates[host_id] = new_host
        self._debounce_timer.start()
    
    def _on_host_deleted(self, host_id: str, deleted_host: Host):
        """
        Хост удалён
        
        Стратегия: Полная перезагрузка (проще и быстрее чем искать строку)
        """
        hosts = self._repository.get_all()
        self._table_model.set_hosts(hosts)
        logging.debug(f"Table updated: host deleted ({host_id})")
    
    def _on_hosts_loaded(self, hosts: List[Host]):
        """
        Хосты загружены при старте
        
        Стратегия: Полная загрузка
        """
        self._table_model.set_hosts(hosts)
        logging.info(f"Table loaded with {len(hosts)} hosts")
    
    def _on_status_changed(self, host_id: str, old_status: str, new_status: str):
        """
        Статус хоста изменён
        
        Стратегия: Обновить только ячейку статуса (самое частое событие)
        """
        self._table_model.update_host_status(host_id, new_status, None, None)
        logging.debug(f"Table status updated: {host_id} ({old_status} → {new_status})")
    
    def _on_batch_updated(self, changes: List[tuple]):
        """
        Массовое обновление статусов (от MonitorThread)
        
        Стратегия: Batch обновление всех изменений
        
        Args:
            changes: [(host_id, old_status, new_status), ...]
        """
        for host_id, old_status, new_status in changes:
            self._table_model.update_host_status(host_id, new_status, None, None)
        
        logging.debug(f"Table batch updated: {len(changes)} hosts")
    
    def _flush_pending_updates(self):
        """
        Применить накопленные обновления (debounced)
        """
        if not self._pending_updates:
            return
        
        # Обновить только изменённые строки
        for host_id, host in self._pending_updates.items():
            row = self._table_model.get_row_by_id(host_id)
            if row >= 0:
                self._table_model.update_row(row, host)
        
        count = len(self._pending_updates)
        self._pending_updates.clear()
        logging.debug(f"Flushed {count} pending table updates")
