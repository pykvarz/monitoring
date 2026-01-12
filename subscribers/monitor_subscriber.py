#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MonitorSubscriber - Подписчик для синхронизации с MonitorThread

Оптимизации:
- НЕ обновляет MonitorThread при изменении статусов (MonitorThread сам их обновляет)
- Обновляет только при добавлении/удалении хостов или смене IP
- Умная проверка на необходимость обновления
"""

import logging
from typing import List
from PyQt5.QtCore import QObject

from core.host_repository import HostRepository
from models import Host


class MonitorSubscriber(QObject):
    """
    Подписчик для синхронизации HostRepository с MonitorThread
    
    Стратегии:
    - host_added/deleted: Обновить список хостов в MonitorThread
    - host_updated: Только если изменился IP или настройки мониторинга
    - status_changed: НЕ обновлять (MonitorThread сам обновляет статусы)
    """
    
    def __init__(self, repository: HostRepository, monitor_thread):
        super().__init__()
        self._repository = repository
        self._monitor_thread = monitor_thread
        
        # Подписка на события
        repository.host_added.connect(self._on_host_changed)
        repository.host_deleted.connect(lambda id, host: self._on_host_changed())
        repository.host_updated.connect(self._on_host_updated)
        repository.hosts_loaded.connect(self._on_hosts_loaded)
        
        logging.debug("MonitorSubscriber initialized")
    
    def _on_host_changed(self):
        """
        Хост добавлен или удалён
        
        Стратегия: Обновить весь список хостов в MonitorThread
        """
        hosts = self._repository.get_all()
        self._monitor_thread.update_hosts(hosts)
        logging.debug(f"MonitorThread updated: {len(hosts)} hosts")
    
    def _on_host_updated(self, host_id: str, old_host: Host, new_host: Host):
        """
        Хост обновлён
        
        Стратегия: Обновить ТОЛЬКО если изменился IP или настройки мониторинга
        (изменение статуса НЕ триггерит обновление - MonitorThread сам обновляет статусы)
        """
        # Проверяем, изменились ли критичные поля
        needs_update = (
            old_host.ip != new_host.ip or
            old_host.notifications_enabled != new_host.notifications_enabled
        )
        
        if needs_update:
            hosts = self._repository.get_all()
            self._monitor_thread.update_hosts(hosts)
            logging.debug(f"MonitorThread updated: host {host_id} config changed")
    
    def _on_hosts_loaded(self, hosts: List[Host]):
        """
        Хосты загружены при старте
        
        Стратегия: Обновить список хостов в MonitorThread
        """
        self._monitor_thread.update_hosts(hosts)
        logging.info(f"MonitorThread initialized with {len(hosts)} hosts")
