#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HostRepository - Единственный источник данных о хостах (Single Source of Truth)

Архитектура:
- In-Memory хранилище для быстродействия
- Qt Signals для event-driven обновлений
- Thread-safe через QMutex
- O(1) операции через Dict[host_id, Host]
"""

import logging
from typing import Dict, List, Optional, Set
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from dataclasses import replace

from models import Host


class HostRepository(QObject):
    """
    In-Memory репозиторий хостов с событийной моделью
    
    Сигналы (Event Bus):
    - host_added(host_id: str) - новый хост добавлен
    - host_updated(host_id: str, old_host: Host, new_host: Host) - хост обновлён
    - host_deleted(host_id: str, deleted_host: Host) - хост удалён
    - hosts_loaded(hosts: List[Host]) - хосты загружены при старте
    - status_changed(host_id: str, old_status: str, new_status: str) - статус изменён
    - hosts_batch_updated(changes: List[tuple]) - массовое обновление
    """
    
    # Qt Signals для event-driven архитектуры
    host_added = pyqtSignal(str)  # host_id
    host_updated = pyqtSignal(str, object, object)  # host_id, old_host, new_host
    host_deleted = pyqtSignal(str, object)  # host_id, deleted_host
    hosts_loaded = pyqtSignal(list)  # all_hosts
    status_changed = pyqtSignal(str, str, str)  # host_id, old_status, new_status
    hosts_batch_updated = pyqtSignal(list)  # [(host_id, old_status, new_status), ...]
    
    def __init__(self):
        super().__init__()
        self._hosts: Dict[str, Host] = {}
        self._mutex = QMutex()
        logging.info("HostRepository initialized")
    
    # ==================== QUERIES (Read) ====================
    
    def get(self, host_id: str) -> Optional[Host]:
        """
        Получить хост по ID (O(1))
        
        Args:
            host_id: ID хоста
            
        Returns:
            Host или None если не найден
        """
        with QMutexLocker(self._mutex):
            return self._hosts.get(host_id)
    
    def get_all(self) -> List[Host]:
        """
        Получить все хосты (O(n))
        
        Returns:
            Список всех хостов
        """
        with QMutexLocker(self._mutex):
            return list(self._hosts.values())
    
    def find_by_group(self, group: str) -> List[Host]:
        """
        Найти хосты по группе (O(n))
        
        Args:
            group: Название группы
            
        Returns:
            Список хостов в группе
        """
        with QMutexLocker(self._mutex):
            return [h for h in self._hosts.values() if h.group == group]
    
    def find_by_status(self, status: str) -> List[Host]:
        """
        Найти хосты по статусу (O(n))
        
        Args:
            status: Статус (ONLINE, OFFLINE, WAITING, MAINTENANCE)
            
        Returns:
            Список хостов с данным статусом
        """
        with QMutexLocker(self._mutex):
            return [h for h in self._hosts.values() if h.status == status]
    
    def get_stats(self) -> Dict[str, int]:
        """
        Получить статистику по статусам (O(n))
        
        Returns:
            Словарь {статус: количество}
        """
        with QMutexLocker(self._mutex):
            stats = {"ONLINE": 0, "WAITING": 0, "OFFLINE": 0, "MAINTENANCE": 0}
            for host in self._hosts.values():
                stats[host.status] = stats.get(host.status, 0) + 1
            return stats
    
    def get_all_groups(self) -> Set[str]:
        """
        Получить список всех уникальных групп
        
        Returns:
            Множество названий групп
        """
        with QMutexLocker(self._mutex):
            return {h.group for h in self._hosts.values()}
    
    def count(self) -> int:
        """
        Получить количество хостов
        
        Returns:
            Количество хостов в репозитории
        """
        with QMutexLocker(self._mutex):
            return len(self._hosts)
    
    # ==================== COMMANDS (Write) ====================
    
    def add(self, host: Host) -> None:
        """
        Добавить новый хост (O(1))
        
        Args:
            host: Объект Host для добавления
        """
        with QMutexLocker(self._mutex):
            if host.id in self._hosts:
                logging.warning(f"Host {host.id} already exists, use update() instead")
                return
            self._hosts[host.id] = host
        
        # Emit signal вне lock для избежания deadlock
        self.host_added.emit(host.id)
        logging.info(f"Host added: {host.name} ({host.ip})")
    
    def update(self, host: Host) -> None:
        """
        Обновить существующий хост (O(1))
        
        Args:
            host: Обновлённый объект Host
        """
        with QMutexLocker(self._mutex):
            old_host = self._hosts.get(host.id)
            self._hosts[host.id] = host
        
        # Emit signals вне lock
        if old_host:
            self.host_updated.emit(host.id, old_host, host)
            
            # Специальное событие для изменения статуса
            if old_host.status != host.status:
                self.status_changed.emit(host.id, old_host.status, host.status)
                logging.info(f"Host {host.name}: {old_host.status} → {host.status}")
        else:
            # Хост не существовал - добавляем
            self.host_added.emit(host.id)
            logging.info(f"Host created via update: {host.name}")
    
    def delete(self, host_id: str) -> bool:
        """
        Удалить хост (O(1))
        
        Args:
            host_id: ID хоста для удаления
            
        Returns:
            True если хост был удалён, False если не найден
        """
        with QMutexLocker(self._mutex):
            host = self._hosts.pop(host_id, None)
        
        if host:
            self.host_deleted.emit(host_id, host)
            logging.info(f"Host deleted: {host.name}")
            return True
        return False
    
    def update_status(self, host_id: str, new_status: str, 
                     offline_since: Optional[str] = None,
                     offline_time: Optional[str] = None) -> None:
        """
        Быстрое обновление только статуса хоста (оптимизировано для MonitorThread)
        
        Args:
            host_id: ID хоста
            new_status: Новый статус
            offline_since: Время когда хост стал offline (опционально)
            offline_time: Время простоя (опционально)
        """
        with QMutexLocker(self._mutex):
            host = self._hosts.get(host_id)
            if not host:
                logging.warning(f"Cannot update status: host {host_id} not found")
                return
            
            old_status = host.status
            
            # Используем dataclass replace для immutability
            updated_host = replace(
                host,
                status=new_status,
                offline_since=offline_since if offline_since else host.offline_since,
                notified=False if new_status == "ONLINE" else host.notified
            )
            
            # Сброс offline_since при переходе в ONLINE
            if new_status == "ONLINE" and host.status != "ONLINE":
                updated_host = replace(updated_host, offline_since=None)
            
            self._hosts[host_id] = updated_host
        
        # Emit signals
        if old_status != new_status:
            self.status_changed.emit(host_id, old_status, new_status)
    
    def bulk_update_status(self, status_updates: List[tuple]) -> None:
        """
        Массовое обновление статусов (оптимизировано для MonitorThread)
        
        Args:
            status_updates: [(host_id, new_status, offline_since, offline_time), ...]
        """
        changes = []
        
        with QMutexLocker(self._mutex):
            for update in status_updates:
                host_id = update[0]
                new_status = update[1]
                offline_since = update[2] if len(update) > 2 else None
                
                host = self._hosts.get(host_id)
                if not host:
                    continue
                
                old_status = host.status
                if old_status == new_status:
                    continue  # Статус не изменился
                
                # Обновляем статус
                updated_host = replace(
                    host,
                    status=new_status,
                    offline_since=offline_since if new_status != "ONLINE" else None,
                    notified=False if new_status == "ONLINE" else host.notified
                )
                
                self._hosts[host_id] = updated_host
                changes.append((host_id, old_status, new_status))
        
        # Emit batch signal
        if changes:
            self.hosts_batch_updated.emit(changes)
            logging.info(f"Batch updated {len(changes)} hosts")
    
    def load(self, hosts: List[Host]) -> None:
        """
        Загрузить хосты (при старте приложения)
        
        Args:
            hosts: Список хостов для загрузки
        """
        with QMutexLocker(self._mutex):
            self._hosts = {h.id: h for h in hosts}
        
        self.hosts_loaded.emit(hosts)
        logging.info(f"Loaded {len(hosts)} hosts into repository")
    
    def clear(self) -> None:
        """Очистить все хосты (для тестов)"""
        with QMutexLocker(self._mutex):
            count = len(self._hosts)
            self._hosts.clear()
        
        logging.info(f"Repository cleared ({count} hosts removed)")
