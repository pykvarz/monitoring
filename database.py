#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер базы данных SQLite.
Отвечает за подключение, создание таблиц и выполнение прямых запросов.
Оптимизирован для высокой производительности (WAL mode).
"""

import logging
import os
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

class DatabaseManager:
    def __init__(self, db_name="hosts.db"):
        self.db_name = db_name
        self._connected = False
        self._init_connection()
        self._optimize_db()
        self._create_tables()

    def _init_connection(self):
        """Инициализация соединения с БД"""
        if QSqlDatabase.contains("qt_sql_default_connection"):
            self.db = QSqlDatabase.database("qt_sql_default_connection")
        else:
            self.db = QSqlDatabase.addDatabase("QSQLITE")
            self.db.setDatabaseName(self.db_name)

        if not self.db.open():
            logging.critical(f"Не удалось открыть базу данных: {self.db.lastError().text()}")
            self._connected = False
        else:
            logging.info(f"База данных {self.db_name} успешно подключена")
            self._connected = True

    def _optimize_db(self):
        """Применение оптимизаций SQLite для производительности"""
        if not self._connected:
            return

        query = QSqlQuery()
        
        # Write-Ahead Logging - значительно ускоряет запись и позволяет параллельное чтение
        if not query.exec_("PRAGMA journal_mode = WAL"):
            logging.warning("Не удалось включить режим WAL")
            
        # Synchronous NORMAL - безопасный компромисс между скоростью и надежностью 
        # (в режиме WAL это безопасно)
        if not query.exec_("PRAGMA synchronous = NORMAL"):
            logging.warning("Не удалось установить synchronous = NORMAL")
            
        # Хранение временных таблиц в памяти
        query.exec_("PRAGMA temp_store = MEMORY")
        
        # Увеличение размера кэша страниц (по умолчанию обычно 2000, ставим 10000)
        query.exec_("PRAGMA cache_size = 10000")

        logging.info("Оптимизации базы данных применены")

    def _create_tables(self):
        """Создание структуры таблиц"""
        if not self._connected:
            return

        query = QSqlQuery()
        
        # Таблица хостов
        # Используем status_idx для быстрого поиска по статусу
        hosts_table = """
        CREATE TABLE IF NOT EXISTS hosts (
            id TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            name TEXT,
            grp TEXT DEFAULT 'Default',
            icon TEXT,
            status TEXT DEFAULT 'UNKNOWN',
            last_seen TEXT,
            offline_since TEXT,
            notifications_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        if not query.exec_(hosts_table):
            logging.error(f"Ошибка создания таблицы hosts: {query.lastError().text()}")

        # Индексы для hosts
        query.exec_("CREATE INDEX IF NOT EXISTS idx_hosts_status ON hosts(status)")
        query.exec_("CREATE INDEX IF NOT EXISTS idx_hosts_grp ON hosts(grp)")

        # Таблица настроек (Key-Value хранилище)
        settings_table = """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
        if not query.exec_(settings_table):
            logging.error(f"Ошибка создания таблицы settings: {query.lastError().text()}")
            
        logging.info("Структура таблиц проверена/создана")

    def get_db(self) -> QSqlDatabase:
        return self.db

    def close(self):
        if self.db.isOpen():
            self.db.close()
