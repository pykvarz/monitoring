#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер данных (DataManager).
Центральный компонент архитектуры.
Отвечает за:
1. Взаимодействие с БД
2. Кеширование данных (опционально)
3. Throttling обновлений UI (для поддержки 1000+ узлов)
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from PyQt5.QtSql import QSqlQuery, QSqlDatabase

from database import DatabaseManager
from models import Host

class DataManager(QObject):
    # Сигнал для обновления UI. 
    # Отправляет список ID измененных хостов, чтобы таблица перерисовывала только их.
    # Если список пуст/None -> полное обновление.
    hosts_updated = pyqtSignal(list)
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        
        # === Batch Updates Logic ===
        # Накапливаем изменения и отправляем их раз в N мс
        self._changed_host_ids = set()
        self._update_timer = QTimer()
        self._update_timer.setInterval(250)  # Обновление UI 4 раза в секунду макс.
        self._update_timer.timeout.connect(self._flush_updates)
        self._batch_mutex = QMutex()
        
    def get_all_hosts(self, connection_name: str = None) -> List[Host]:
        """Получение всех хостов из БД"""
        hosts = []
        db = QSqlDatabase.database(connection_name) if connection_name else self.db_manager.get_db()
        
        if not db.isOpen():
            return hosts

        query = QSqlQuery("SELECT * FROM hosts ORDER BY status, name", db)
        while query.next():
            host = self._record_to_host(query)
            hosts.append(host)
        
        return hosts

    def add_host(self, host: Host) -> bool:
        """Добавление нового хоста"""
        query = QSqlQuery()
        query.prepare("""
            INSERT INTO hosts (id, ip, name, grp, status, notifications_enabled)
            VALUES (:id, :ip, :name, :grp, :status, :notifications_enabled)
        """)
        query.bindValue(":id", host.id)
        query.bindValue(":ip", host.ip)
        query.bindValue(":name", host.name)
        query.bindValue(":grp", host.group)
        query.bindValue(":status", host.status)
        query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
        
        if query.exec_():
            self._trigger_update() # Полное обновление для корректного отображения и сортировки
            return True
        else:
            logging.error(f"Ошибка добавления хоста: {query.lastError().text()}")
            return False

    def add_hosts(self, hosts: List[Host]) -> Tuple[int, int]:
        """
        Пакетное добавление хостов (Transaction)
        Returns: (added_count, errors_count)
        """
        added = 0
        errors = 0
        db = self.db_manager.get_db()
        
        if not db.transaction():
            logging.error("Failed to start transaction for batch add")
            return 0, len(hosts)

        query = QSqlQuery(db)
        query.prepare("""
            INSERT INTO hosts (id, ip, name, grp, status, notifications_enabled)
            VALUES (:id, :ip, :name, :grp, :status, :notifications_enabled)
        """)
        
        for host in hosts:
            query.bindValue(":id", host.id)
            query.bindValue(":ip", host.ip)
            query.bindValue(":name", host.name)
            query.bindValue(":grp", host.group)
            query.bindValue(":status", host.status)
            query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
            
            if query.exec_():
                added += 1
            else:
                logging.warning(f"Failed to add host {host.name}: {query.lastError().text()}")
                errors += 1
                
        if not db.commit():
            logging.error("Failed to commit batch add transaction")
            db.rollback()
            return 0, len(hosts)
            
        if added > 0:
            self._trigger_update() # Full update after batch import
            
        return added, errors

    def delete_host(self, host_id: str) -> bool:
        """Удаление хоста"""
        query = QSqlQuery()
        query.prepare("DELETE FROM hosts WHERE id = :id")
        query.bindValue(":id", host_id)
        
        if query.exec_():
            self._trigger_update() # Полное обновление списка, т.к. удаление
            return True
        return False

    def update_host_status(self, host_id: str, status: str, offline_since: Optional[str] = None):
        """
        Обновление статуса хоста.
        """
        query = QSqlQuery()
        
        # Обновляем status и last_seen всегда
        # offline_since обновляем только если передано
        sql = """
            UPDATE hosts 
            SET status = :status, 
                last_seen = :last_seen
        """
        if offline_since is not None:
            sql += ", offline_since = :offline_since"
            
        sql += " WHERE id = :id"
        
        query.prepare(sql)
        query.bindValue(":status", status)
        query.bindValue(":last_seen", datetime.now().isoformat())
        if offline_since is not None:
            query.bindValue(":offline_since", offline_since)
        query.bindValue(":id", host_id)
        
        if query.exec_():
            # Добавляем в batch для обновления UI
            with QMutexLocker(self._batch_mutex):
                self._changed_host_ids.add(host_id)
                if not self._update_timer.isActive():
                    self._update_timer.start()
        else:
            logging.error(f"Failed to update host {host_id}: {query.lastError().text()}")

    def update_host_info(self, host: Host) -> bool:
        """Обновление информации о хосте (имя, ip, группа и т.д.)"""
        query = QSqlQuery()
        query.prepare("""
            UPDATE hosts 
            SET ip = :ip, 
                name = :name, 
                grp = :grp, 
                notifications_enabled = :notifications_enabled
            WHERE id = :id
        """)
        query.bindValue(":ip", host.ip)
        query.bindValue(":name", host.name)
        query.bindValue(":grp", host.group)
        query.bindValue(":notifications_enabled", 1 if host.notifications_enabled else 0)
        query.bindValue(":id", host.id)
        
        if query.exec_():
            self._trigger_update() # Полное обновление для пересортировки
            return True
        else:
            logging.error(f"Ошибка обновления информации хоста {host.id}: {query.lastError().text()}")
            return False

    def _trigger_update(self, host_ids: List[str] = None):
        """Принудительный вызов обновления (сразу)"""
        if host_ids is None:
            self.hosts_updated.emit([]) # Пустой список = полное обновление
        else:
            self.hosts_updated.emit(host_ids)

    def _flush_updates(self):
        """Отправка накопленных обновлений в UI"""
        with QMutexLocker(self._batch_mutex):
            if not self._changed_host_ids:
                return
            
            # Копируем и чистим
            updates = list(self._changed_host_ids)
            self._changed_host_ids.clear()
            self._update_timer.stop()
            
        # Эмитим сигнал (уже без лока)
        self.hosts_updated.emit(updates)

    def get_hosts_by_ids(self, host_ids: List[str]) -> List[Host]:
        """Получение списка хостов по ID"""
        if not host_ids or not self.db_manager.get_db().isOpen():
            return []
            
        hosts = []
        placeholders = ",".join(["?"] * len(host_ids))
        query = QSqlQuery()
        query.prepare(f"SELECT * FROM hosts WHERE id IN ({placeholders})")
        
        for host_id in host_ids:
            query.addBindValue(host_id)
            
        if query.exec_():
            while query.next():
                hosts.append(self._record_to_host(query))
                
        return hosts

    def _record_to_host(self, query: QSqlQuery) -> Host:
        """Helper: QSqlQuery record -> Host object"""
        return Host(
            id=query.value("id"),
            ip=query.value("ip"),
            name=query.value("name"),
            group=query.value("grp"),
            status=query.value("status"),
            offline_since=query.value("offline_since"),
            notifications_enabled=bool(query.value("notifications_enabled"))
        )

    def get_stats(self) -> Dict[str, int]:
        """Получение статистики по статусам"""
        stats = {"ONLINE": 0, "WAITING": 0, "OFFLINE": 0, "MAINTENANCE": 0, "TOTAL": 0}
        
        if not self.db_manager.get_db().isOpen():
            return stats
            
        query = QSqlQuery("SELECT status, COUNT(*) FROM hosts GROUP BY status")
        while query.next():
            status = query.value(0)
            count = query.value(1)
            if status in stats:
                stats[status] = count
            stats["TOTAL"] += count
            
        return stats

