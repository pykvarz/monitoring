#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExportImportManager - Управление импортом/экспортом данных в Excel
"""

from typing import List, Set, Tuple
from datetime import datetime
import logging
from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import QMutexLocker, QMutex
from models import Host
from storage import StorageManager
from excel_service import ExcelService


class ExportImportManager:
    """Менеджер импорта и экспорта данных"""

    def __init__(self, parent: QWidget, storage: StorageManager):
        """
        Инициализация менеджера импорта/экспорта
        
        Args:
            parent: Родительский виджет для диалогов
            storage: Менеджер хранения данных
        """
        self._parent = parent
        self._storage = storage

    def import_from_excel(self, hosts: List[Host], hosts_mutex: QMutex,
                          update_callback: callable) -> bool:
        """
        Импорт узлов из Excel файла
        
        Args:
            hosts: Текущий список хостов (будет изменен)
            hosts_mutex: Мьютекс для безопасного доступа к списку
            update_callback: Callback для обновления UI после импорта
            
        Returns:
            True если импорт был выполнен, False если отменен
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self._parent, 
            "Выберите Excel файл для импорта", 
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if not file_path:
            return False

        try:
            # Получаем существующие IP под блокировкой
            with QMutexLocker(hosts_mutex):
                existing_ips = {h.ip for h in hosts}
            
            new_hosts, skipped_count, errors = ExcelService.import_hosts(file_path, existing_ips)
            
            if new_hosts:
                with QMutexLocker(hosts_mutex):
                    hosts.extend(new_hosts)
                    self._storage.save_hosts(hosts)

                # Вызываем callback для обновления UI
                if update_callback:
                    update_callback()

            # Формируем сообщение о результатах
            message = f"✅ Импортировано: {len(new_hosts)}\n"
            if skipped_count > 0:
                message += f"⚠️ Пропущено: {skipped_count}\n"
                if errors:
                    message += "\nОшибки:\n" + "\n".join(errors[:10])
                    if len(errors) > 10:
                        message += f"\n... и ещё {len(errors) - 10} ошибок"

            QMessageBox.information(self._parent, "Импорт завершён", message)
            return True

        except Exception as e:
            logging.error(f"Ошибка импорта из {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self._parent, 
                "Ошибка импорта", 
                f"Не удалось импортировать файл:\n{str(e)}"
            )
            return False

    def export_to_excel(self, hosts: List[Host], hosts_mutex: QMutex) -> bool:
        """
        Экспорт узлов в Excel файл
        
        Args:
            hosts: Список хостов для экспорта
            hosts_mutex: Мьютекс для безопасного доступа к списку
            
        Returns:
            True если экспорт был выполнен, False если отменен
        """
        with QMutexLocker(hosts_mutex):
            if not hosts:
                QMessageBox.information(self._parent, "Информация", "Нет узлов для экспорта")
                return False
            hosts_to_export = list(hosts)

        # Формируем имя файла с временной меткой
        default_filename = f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent, 
            "Сохранить как Excel файл",
            default_filename,
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return False

        try:
            ExcelService.export_hosts(file_path, hosts_to_export)
            QMessageBox.information(
                self._parent, 
                "Экспорт завершён",
                f"✅ Экспортировано узлов: {len(hosts_to_export)}\n\nФайл сохранён: {file_path}"
            )
            return True
        except Exception as e:
            logging.error(f"Ошибка экспорта в {file_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self._parent, 
                "Ошибка экспорта", 
                f"Не удалось экспортировать файл:\n{str(e)}"
            )
            return False
