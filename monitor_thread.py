#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Поток мониторинга (Optimized).
Работает в связке с DataManager.
"""

from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import time

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, pyqtSlot, QMutexLocker

from models import Host, AppConfig, format_offline_time
from services import PingService
from data_manager import DataManager

class MonitorThread(QThread):
    """
    Поток для мониторинга узлов.
    
    Изменения v2.0 (SQLite Optimization):
    - Не хранит копию хостов.
    - Получает список хостов из DataManager каждый цикл (или реже).
    - Результаты пишет в DataManager (который сам буферизует обновления UI).
    - Убраны лишние сигналы обновления UI для каждого хоста.
    """

    # Сигналы
    hosts_offline = pyqtSignal(list)  # Для уведомлений
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, data_manager: DataManager, config: AppConfig):
        super().__init__()
        self._data_manager = data_manager
        self._config = config
        self._running = True
        self._executor: ThreadPoolExecutor = None
        self._force_scan_flag = False
        self._update_executor()

    def _update_executor(self) -> None:
        """Обновление пула потоков"""
        if self._executor:
            try:
                import sys
                if sys.version_info >= (3, 9):
                    self._executor.shutdown(wait=False, cancel_futures=True)
                else:
                    self._executor.shutdown(wait=False)
            except (RuntimeError, TypeError):
                pass
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_workers)

    def update_config(self, config: AppConfig) -> None:
        """Обновление конфигурации"""
        old_max_workers = self._config.max_workers
        self._config = config
        if config.max_workers != old_max_workers:
            self._update_executor()

    def force_scan(self) -> None:
        self._force_scan_flag = True

    def stop(self) -> None:
        self._running = False
        if self._executor:
            try:
                self._executor.shutdown(wait=True)
            except RuntimeError:
                pass
        self.wait()

    def _check_host(self, host: Host) -> Tuple[str, str, Optional[str]]:
        """Проверка одного узла"""
        try:
            if host.status == "MAINTENANCE":
                return (host.id, "MAINTENANCE", None)

            result = PingService.ping_host(host.ip, timeout=2.0)
            status = "ONLINE" if result else "OFFLINE"
            return (host.id, status, None)
        except Exception as e:
            return (host.id, "OFFLINE", str(e))

    def run(self) -> None:
        """Основной цикл (Data-Driven)"""
        while self._running:
            try:
                # 1. Получаем актуальный список хостов из БД
                # Это быстро (SELECT *), даже для 1000 хостов
                hosts = self._data_manager.get_all_hosts()

                if not hosts:
                    self.msleep(1000)
                    continue

                self.scan_started.emit()

                # 2. Запускаем параллельный пинг
                futures: Dict[Future, Host] = {}
                for host in hosts:
                    if not self._running:
                        break
                    future = self._executor.submit(self._check_host, host)
                    futures[future] = host

                newly_offline = []
                current_time = datetime.now(timezone.utc)

                # 3. Обрабатываем результаты по мере поступления
                for future in as_completed(futures):
                    if not self._running:
                        break

                    host = futures[future]
                    try:
                        host_id, ping_status, error = future.result()
                        
                        # Логика смены статуса
                        new_status = host.status
                        offline_since = host.offline_since
                        should_update = False
                        
                        if ping_status == "ONLINE":
                            if host.status != "ONLINE":
                                new_status = "ONLINE"
                                offline_since = None
                                should_update = True
                            # Всегда обновляем last_seen в БД (DataManager это оптимизирует или мы можем реже это делать)
                            # Для "1000 узлов без лагов" мы можем обновлять last_seen ТОЛЬКО если статус меняется 
                            # или раз в N минут. Но ТЗ просит "мониторинг".
                            # DataManager.update_host_status обновляет last_seen.
                            if not should_update:
                                # Чтобы не спамить БД записью каждой успешной проверки, 
                                # можно обновлять last_seen только раз в цикл
                                should_update = True 

                        else: # OFFLINE / WAITING / MAINTENANCE
                             if host.status == "MAINTENANCE":
                                 continue
                                 
                             # Если уже OFFLINE, проверяем тайминг или просто обновляем счетчик?
                             # В этой упрощенной версии доверимся логике:
                             # Если пинг провалился -> считаем OFFLINE (или WAITING по таймауту)
                             
                             if host.offline_since is None:
                                 offline_since = current_time.isoformat()
                                 # Тут статус еще может быть ONLINE (первый сбой), 
                                 # либо сразу ставим WAITING/OFFLINE в зависимости от логики?
                                 # В оригинале была логика waiting_timeout.
                                 # Давайте упростим: если упал - ставим оффлайн дату.
                                 # Статус сменим только если прошло время.
                                 should_update = True
                             
                             # Проверяем таймауты
                             if offline_since:
                                 try:
                                     start_dt = datetime.fromisoformat(offline_since)
                                     if start_dt.tzinfo is None:
                                         start_dt = start_dt.replace(tzinfo=timezone.utc)
                                     duration = (current_time - start_dt).total_seconds()
                                     
                                     calculated_status = host.status
                                     if duration >= self._config.offline_timeout:
                                         calculated_status = "OFFLINE"
                                     elif duration >= self._config.waiting_timeout:
                                         calculated_status = "WAITING"
                                     
                                     if calculated_status != host.status:
                                         new_status = calculated_status
                                         should_update = True
                                         
                                         if new_status == "OFFLINE" and host.notifications_enabled:
                                             newly_offline.append(host.name)
                                             
                                 except ValueError:
                                     offline_since = current_time.isoformat()
                                     should_update = True

                        if should_update:
                            self._data_manager.update_host_status(host_id, new_status, offline_since)

                    except Exception as e:
                        # self.error_occurred.emit(f"Error checking {host.name}: {e}")
                        pass

                if newly_offline:
                    self.hosts_offline.emit(newly_offline)

                self.scan_finished.emit()

                # Пауза
                elapsed_wait = 0
                while elapsed_wait < self._config.poll_interval * 1000 and self._running:
                    self.msleep(100)
                    elapsed_wait += 100
                    if self._force_scan_flag:
                        self._force_scan_flag = False
                        break

            except Exception as e:
                self.error_occurred.emit(f"Global monitor loop error: {e}")
                self.msleep(5000)
