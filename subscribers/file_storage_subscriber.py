#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FileStorageSubscriber - Подписчик для асинхронного сохранения на диск

Оптимизации:
- Батч-сохранение (каждые 30 секунд вместо при каждом изменении)
- Отслеживание только изменённых хостов (dirty tracking)
- Атомарная запись через временный файл
- Принудительное сохранение при выходе
"""

import logging
import json
from pathlib import Path
from typing import Set, List
from PyQt5.QtCore import QObject, QTimer, QMutex, QMutexLocker

from core.host_repository import HostRepository
from models import Host


class FileStorageSubscriber(QObject):
    """
    Подписчик для асинхронного сохранения хостов на диск
    
    Стратегии:
    - Батчинг: Сохранение каждые 30 секунд
    - Dirty tracking: Отмечаем только изменённые хосты
    - Атомарная запись: Используем временный файл
    """
    
    def __init__(self, repository: HostRepository, storage_path: Path):
        super().__init__()
        self._repository = repository
        self._storage_path = Path(storage_path)
        self._dirty_ids: Set[str] = set()
        self._mutex = QMutex()
        
        # Подписка на события
        repository.host_added.connect(self._mark_dirty)
        repository.host_updated.connect(lambda id, old, new: self._mark_dirty(id))
        repository.host_deleted.connect(lambda id, host: self._mark_dirty(id))
        repository.hosts_batch_updated.connect(self._mark_batch_dirty)
        
        # Таймер батч-сохранения (30 секунд)
        self._save_timer = QTimer()
        self._save_timer.setInterval(30000)  # 30 сек
        self._save_timer.timeout.connect(self._batch_save)
        self._save_timer.start()
        
        logging.info(f"FileStorageSubscriber initialized (save interval: 30s, path: {storage_path})")
    
    def _mark_dirty(self, host_id: str):
        """
        Отметить хост как изменённый
        
        Args:
            host_id: ID изменённого хоста
        """
        with QMutexLocker(self._mutex):
            self._dirty_ids.add(host_id)
    
    def _mark_batch_dirty(self, changes: List[tuple]):
        """
        Отметить множество хостов как изменённые
        
        Args:
            changes: [(host_id, old_status, new_status), ...]
        """
        with QMutexLocker(self._mutex):
            for host_id, _, _ in changes:
                self._dirty_ids.add(host_id)
    
    def _batch_save(self):
        """
        Батч-сохранение изменённых хостов
        
        Алгоритм:
        1. Получить список грязных ID
        2. Загрузить все хосты из репозитория
        3. Сохранить на диск
        4. Очистить dirty tracking
        """
        with QMutexLocker(self._mutex):
            if not self._dirty_ids:
                return
            dirty_count = len(self._dirty_ids)
            self._dirty_ids.clear()
        
        try:
            # Получаем все хосты из репозитория
            hosts = self._repository.get_all()
            
            # Сохраняем атомарно
            self._atomic_save(hosts)
            
            logging.info(f"Batch saved {len(hosts)} hosts ({dirty_count} were modified)")
            
        except Exception as e:
            logging.error(f"Batch save failed: {e}", exc_info=True)
            # Не возвращаем в dirty - попробуем в следующий раз
    
    def _atomic_save(self, hosts: List[Host]):
        """
        Атомарное сохранение через временный файл
        
        Алгоритм:
        1. Записываем в .tmp файл
        2. Атомарно заменяем основной файл
        3. Если ошибка - удаляем .tmp
        
        Args:
            hosts: Список хостов для сохранения
        """
        temp_path = self._storage_path.with_suffix('.tmp')
        
        try:
            # Записываем во временный файл
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump([h.to_dict() for h in hosts], f, indent=2, ensure_ascii=False)
            
            # Атомарная замена (на Windows может потребоваться удаление старого файла)
            if self._storage_path.exists():
                self._storage_path.unlink()
            temp_path.rename(self._storage_path)
            
            logging.debug(f"Atomic save completed: {self._storage_path}")
            
        except Exception as e:
            # Удаляем временный файл при ошибке
            temp_path.unlink(missing_ok=True)
            raise e
    
    def force_save(self):
        """
        Принудительное сохранение (при выходе из приложения)
        
        Вызывается MainWindow.closeEvent()
        """
        logging.info("Force save triggered")
        
        # Останавливаем таймер
        self._save_timer.stop()
        
        # Сохраняем немедленно
        self._batch_save()
    
    def get_dirty_count(self) -> int:
        """
        Получить количество несохранённых изменений
        
        Returns:
            Количество изменённых хостов
        """
        with QMutexLocker(self._mutex):
            return len(self._dirty_ids)
