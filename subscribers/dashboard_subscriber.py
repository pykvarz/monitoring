#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DashboardSubscriber - Подписчик для умного обновления статистики

Оптимизации:
- Инкрементальное обновление счётчиков (O(1) вместо O(n))
- Debouncing для частых обновлений
- Только изменения статусов триггерят обновления
"""

import logging
from typing import List
from PyQt5.QtCore import QObject, QTimer

from core.host_repository import HostRepository
from models import Host


class DashboardSubscriber(QObject):
    """
    Подписчик для оптимизированного обновления Dashboard
    
    Стратегии:
    - status_changed: Инкрементальное обновление (старый -1, новый +1)
    - hosts_loaded: Полный пересчёт
    - hosts_batch_updated: Batch инкремент/декремент
    """
    
    def __init__(self, repository: HostRepository, dashboard_manager):
        super().__init__()
        self._repository = repository
        self._dashboard_manager = dashboard_manager
        
        # Debouncing для частых обновлений
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(500)  # 500ms debounce
        self._update_timer.timeout.connect(self._delayed_update)
        self._pending_update = False
        
        # Подписка на события
        repository.status_changed.connect(self._on_status_changed)
        repository.hosts_loaded.connect(self._on_hosts_loaded)
        repository.hosts_batch_updated.connect(self._on_batch_updated)
        repository.host_added.connect(self._on_host_added)
        repository.host_deleted.connect(self._on_host_deleted)
        
        logging.debug("DashboardSubscriber initialized")
    
    def _on_status_changed(self, host_id: str, old_status: str, new_status: str):
        """
        Статус хоста изменён
        
        Стратегия: Инкрементальное обновление (O(1))
        """
        # Используем инкрементальное обновление DashboardManager
        self._dashboard_manager.update_status_transition(old_status, new_status)
        logging.debug(f"Dashboard updated: {old_status} → {new_status}")
    
    def _on_hosts_loaded(self, hosts: List[Host]):
        """
        Хосты загружены при старте
        
        Стратегия: Полный пересчёт статистики
        """
        stats = self._repository.get_stats()
        self._dashboard_manager.update_stats(stats)
        logging.info("Dashboard stats fully recalculated")
    
    def _on_batch_updated(self, changes: List[tuple]):
        """
        Массовое обновление статусов
        
        Стратегия: Применить все изменения инкрементально
        """
        for host_id, old_status, new_status in changes:
            self._dashboard_manager.update_status_transition(old_status, new_status)
        
        logging.debug(f"Dashboard batch updated: {len(changes)} transitions")
    
    def _on_host_added(self, host_id: str):
        """
        Новый хост добавлен
        
        Стратегия: Инкремент счётчика статуса хоста
        """
        host = self._repository.get(host_id)
        if host:
            self._dashboard_manager.increment_status(host.status)
            logging.debug(f"Dashboard: host added with status {host.status}")
    
    def _on_host_deleted(self, host_id: str, deleted_host: Host):
        """
        Хост удалён
        
        Стратегия: Декремент счётчика статуса хоста
        """
        self._dashboard_manager.decrement_status(deleted_host.status)
        logging.debug(f"Dashboard: host deleted with status {deleted_host.status}")
    
    def _schedule_update(self):
        """Запланировать debounced обновление"""
        self._pending_update = True
        self._update_timer.start()
    
    def _delayed_update(self):
        """Отложенное обновление (debounced)"""
        if self._pending_update:
            self._dashboard_manager.force_refresh()
            self._pending_update = False
