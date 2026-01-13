#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно приложения (SQLite Architecture)
"""
import sys
import logging
import subprocess
from datetime import datetime
from typing import List, Dict
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QDialog, QMenu, QInputDialog, QFrame
)
from PyQt5.QtCore import QMutex, QTimer, Qt, pyqtSlot, QMutexLocker, QPoint, QModelIndex

# Модели и сервисы
from models import Host, AppConfig, HostStatus, validate_ip_or_hostname
from services import NotificationService
from monitor_thread import MonitorThread

# Dependency Injection
from di_container import DIContainer, setup_container
from interfaces import IStorageRepository, INotificationService
from database import DatabaseManager
from data_manager import DataManager
from core.host_repository import HostRepository

# UI компоненты
from dialogs import SettingsDialog
from ui_components import UIComponents
from host_manager import HostManager
from table_model import CenteredIconDelegate

# Менеджеры
from filter_manager import FilterManager
from theme_manager import ThemeManager
from dashboard_manager import DashboardManager
from export_import_manager import ExportImportManager
from context_menu_manager import ContextMenuManager
from table_settings_manager import TableSettingsManager

# Builders
from menu_builder import MenuBuilder

# Константы и стили
from constants import (
    get_menu_style, SCAN_LABEL_STYLE_ACTIVE, SCAN_LABEL_STYLE_FINISHED,
    get_main_style, get_table_style, get_dashboard_style
)


class MainWindow(QMainWindow):
    """
    Главное окно приложения Network Monitor.
    Архитектура: UI <-> DataManager <-> SQLite
    """

    def __init__(self, container: DIContainer = None):
        super().__init__()
        
        # === Dependency Injection ===
        if container is None:
            container = setup_container()
        self._container = container
        
        # Use Repository as Single Source of Truth
        self._repository = container.resolve(HostRepository)
        self._db_manager = container.resolve(DatabaseManager)
        self._storage = container.resolve(IStorageRepository)
        self._config = self._storage.load_config()
        
        # UI компоненты
        self._table = None
        self._table_model = None
        self._search_edit = None
        self._group_filter = None
        self._status_filter = None
        self._reset_filters_btn = None
        self._toolbar_layout = None
        self._filters_layout = None
        self._dashboard_frame = None
        self._dashboard_labels: Dict[str, QLabel] = {}
        
        # Менеджеры
        self._filter_manager: FilterManager = None
        self._theme_manager: ThemeManager = None
        self._dashboard_manager: DashboardManager = None
        self._export_import_manager: ExportImportManager = None
        self._context_menu_manager: ContextMenuManager = None
        self._table_settings_manager: TableSettingsManager = None
        
        # Состояние
        self._is_scanning = False
        self._last_scan_time: datetime = None
        self._groups: List[str] = []
        
        # Поток мониторинга
        self._monitor_thread: MonitorThread = None
        
        # === Инициализация ===
        self._init_ui()
        self._init_managers()
        self._init_monitor_thread()
        
        # Подключение сигналов Repository
        self._repository.hosts_updated.connect(self._on_hosts_updated)
        
        self._load_initial_data()

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    def _load_initial_data(self) -> None:
        """Загрузка начальных данных и миграция"""
        # 1. Попытка миграции с JSON
        if self._storage.migrate_to_db(self._db_manager):
            QMessageBox.information(self, "Миграция", "Данные успешно перенесены в новую базу данных (SQLite).")
            
        # 2. Загрузка данных в таблицу
        self._refresh_table(full_reload=True)
        self._update_status_bar()

    def _init_ui(self) -> None:
        """Инициализация интерфейса"""
        self.setWindowTitle("Network Monitor")
        self.setGeometry(100, 100, 1400, 800)
        
        theme = getattr(self._config, 'theme', 'light')
        self.setStyleSheet(get_main_style(theme))
        
        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QVBoxLayout(central)
        self._main_layout.setSpacing(10)
        self._main_layout.setContentsMargins(10, 10, 10, 10)

        # === Dashboard + Поиск + Фильтры (в одной строке) ===
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        # Dashboard слева
        self._dashboard_frame, self._dashboard_labels = UIComponents.create_dashboard(theme)
        for label in self._dashboard_labels.values():
            label.clicked.connect(self._on_dashboard_clicked)
        
        # Извлекаем внутренний layout из dashboard frame
        dashboard_inner_layout = self._dashboard_frame.layout()
        
        # Добавляем dashboard labels в общий layout
        for label in self._dashboard_labels.values():
            top_layout.addWidget(label)
        
        # Растяжка между dashboard и фильтрами
        top_layout.addStretch()
        
        # Фильтры справа
        search_result = UIComponents.create_search_bar(self, [], theme)
        self._group_filter = search_result[2]
        self._search_edit = search_result[1]
        
        # Добавляем фильтры в общий layout
        top_layout.addWidget(self._group_filter)
        top_layout.addWidget(self._search_edit)
        
        # Оборачиваем в frame для стиля
        top_frame = QFrame()
        top_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        top_frame.setStyleSheet(get_dashboard_style(theme))
        top_frame.setLayout(top_layout)
        
        self._main_layout.addWidget(top_frame)
        
        # === Меню ===
        MenuBuilder.create_menu_bar(self, theme)

        # === Таблица ===
        self._table, self._table_model = UIComponents.create_table(self, theme)
        self._table.setItemDelegateForColumn(0, CenteredIconDelegate(self._table))
        self._connect_table_signals()
        self._main_layout.addWidget(self._table)

        # === Статус бар ===
        self._status_label = QLabel("Инициализация...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._scan_label = QLabel("")
        self._scan_label.setAlignment(Qt.AlignCenter)
        self.statusBar().addWidget(self._status_label, 1)
        self.statusBar().addPermanentWidget(self._scan_label)

    def _init_managers(self) -> None:
        """Инициализация менеджеров"""
        # Filter Manager - поиск + группы (без статуса)
        self._filter_manager = FilterManager(
            self._search_edit, 
            self._group_filter,  # Теперь есть фильтр групп
            None,  # status_filter отключен
            self._table, 
            self._table_model
        )
        
        # Table Settings Manager
        self._table_settings_manager = TableSettingsManager(
            self._table, self._config, self._storage
        )
        self._table_settings_manager.restore_settings()
        
        # Theme Manager
        self._theme_manager = ThemeManager(
            self, self._config, self._storage, 
            self._table, self._table_model
        )
        # Dashboard уже встроен в top_frame, передаем None
        self._theme_manager.set_ui_components(
            None,  # dashboard_frame теперь часть top_frame
            self._dashboard_labels,
            None,  # toolbar удален
            None,  # filters удалены
            refresh_callback=lambda: self._dashboard_manager.force_refresh()
        )
        
        # Dashboard Manager
        self._dashboard_manager = DashboardManager(self._dashboard_labels, self._config)
        
        # Export/Import Manager
        self._export_import_manager = ExportImportManager(self, self._repository)
        
        # Context Menu Manager
        self._context_menu_manager = ContextMenuManager(
            self, self._table, self._table_model,
            self._groups, 
            lambda: self._theme_manager.get_current_theme(),
            self._repository
        )
        self._connect_context_menus()
        
        # btn_bulk удален из UI
        # btn_bulk = self.findChild(QPushButton, "btn_bulk")
        # if btn_bulk:
        #     btn_bulk.clicked.connect(lambda: self._context_menu_manager.show_bulk_menu(btn_bulk))
        
        self._theme_manager.set_window_icon(self._theme_manager.get_current_theme())

    def _init_monitor_thread(self) -> None:
        """Инициализация потока мониторинга с Repository"""
        self._monitor_thread = MonitorThread(self._repository, self._config)
        self._monitor_thread.hosts_offline.connect(self._on_hosts_offline)
        self._monitor_thread.scan_started.connect(self._on_scan_started)
        self._monitor_thread.scan_finished.connect(self._on_scan_finished)
        self._monitor_thread.host_status_changed.connect(self._repository.update_status)
        self._monitor_thread.error_occurred.connect(lambda e: logging.error(f"MonitorThread Error: {e}"))
        self._monitor_thread.start()

    # ==================== DATA HANDLING ====================

    @pyqtSlot(list)
    def _on_hosts_updated(self, host_ids: List[str]):
        """
        Обработка сигнала об обновлении данных от Repository.
        """
        if not host_ids:
            # Полное обновление (удаление, добавление)
            self._refresh_table(full_reload=True)
        else:
            # Частичное обновление
            updated_hosts = self._repository.get_hosts_by_ids(host_ids)
            self._table_model.update_hosts(updated_hosts)
            
            # Обновление статистики (легкое)
            self._update_dashboard_stats()

    def _refresh_table(self, full_reload: bool = False):
        """Полная перезагрузка данных таблицы"""
        hosts = self._repository.get_all()
        self._table_model.set_hosts(hosts)
        
        # Обновляем группы
        new_groups = sorted(list(set(h.group for h in hosts)))
        # Добавляем кастомные
        if hasattr(self._config, 'custom_groups'):
            new_groups = sorted(list(set(new_groups + self._config.custom_groups)))
            
        self._groups = new_groups or ["Default"]
        
        # Обновляем фильтр групп
        if self._filter_manager:
            self._filter_manager.update_group_filter(self._groups)
        
        self._context_menu_manager.update_groups(self._groups)
        
        # Статистика
        self._update_dashboard_stats()

    def _update_dashboard_stats(self):
        """Обновление дашборда запросом в БД"""
        stats = self._repository.get_stats()
        self._dashboard_manager.update_stats(stats)
        self._update_status_bar(stats.get("TOTAL", 0))

    # ==================== МОНИТОРИНГ ====================

    @pyqtSlot()
    def _on_scan_started(self):
        self._is_scanning = True
        self._scan_label.setText("🔄 Проверка...")
        self._scan_label.setStyleSheet(SCAN_LABEL_STYLE_ACTIVE)

    @pyqtSlot()
    def _on_scan_finished(self):
        self._is_scanning = False
        self._last_scan_time = datetime.now()
        self._scan_label.setText("✓")
        self._scan_label.setStyleSheet(SCAN_LABEL_STYLE_FINISHED)
        self._update_status_bar()

    @pyqtSlot(list)
    def _on_hosts_offline(self, offline_hosts: List[str]):
        NotificationService.notify_offline_hosts(offline_hosts, self._config)

    def _update_status_bar(self, total: int = None):
        if total is None:
            stats = self._repository.get_stats()
            total = stats.get("TOTAL", 0)
            
        msg = f"Узлов: {total} | Мониторинг активен"
        if self._last_scan_time:
            msg += f" | Последняя проверка: {self._last_scan_time.strftime('%H:%M:%S')}"
            
        self._status_label.setText(msg)

    # ==================== TABLE SETTINGS ====================

    def _connect_table_signals(self) -> None:
        """Подключение сигналов таблицы"""
        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
    
    def _connect_context_menus(self) -> None:
        """Подключение контекстных меню"""
        header = self._table.horizontalHeader()
        header.customContextMenuRequested.connect(
            lambda pos: self._context_menu_manager.show_header_context_menu(pos, self._config)
        )
        self._table.customContextMenuRequested.connect(
            self._context_menu_manager.show_host_context_menu
        )

    # ==================== USER ACTIONS ====================

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        HostManager.edit_host(self, index.row(), self._table_model, self._groups, self._repository)

    def _on_dashboard_clicked(self, key: str):
        """Dashboard клики - фильтрация"""
        if key == 'total':
            # Показываем ВСЕ узлы
            if self._filter_manager:
                self._filter_manager.reset_filters()
            # Явно показываем все строки
            for row in range(self._table_model.rowCount()):
                self._table.setRowHidden(row, False)
        else:
            status_map = {'online': 'ONLINE', 'waiting': 'WAITING', 'offline': 'OFFLINE', 'maintenance': 'MAINTENANCE'}
            target = status_map.get(key)
            if target:
                for row in range(self._table_model.rowCount()):
                    host = self._table_model.get_host(row)
                    self._table.setRowHidden(row, host.status != target if host else True)

    def _add_host(self) -> None:
        HostManager.add_host(self, self._groups, self._repository)

    def _add_group(self) -> None:
        group_name, ok = QInputDialog.getText(self, "Новая группа", "Введите название группы:", text="")
        if ok and group_name.strip():
            group_name = group_name.strip()
            if group_name not in self._groups:
                self._config.custom_groups.append(group_name)
                self._storage.save_config(self._config)
                self._refresh_table() # Обновит группы
                QMessageBox.information(self, "Успех", f"Группа '{group_name}' создана")
            else:
                QMessageBox.warning(self, "Ошибка", "Группа с таким названием уже существует")

    def _delete_selected(self) -> None:
        HostManager.delete_selected(self, self._table_model, self._repository)

    def _import_from_excel(self):
        self._export_import_manager.import_from_excel()

    def _export_to_excel(self):
        hosts = self._repository.get_all()
        # Export filtered list or all? Currently passing all from repo.
        # But if table filters are active, user might expect filtered export?
        # HostManager has filtered logic? 
        # Typically Export ALL is safer default unless "Export View" asked.
        self._export_import_manager.export_to_excel(hosts)

    def _toggle_theme(self):
        if self._theme_manager: self._theme_manager.toggle_theme()

    def _open_settings(self):
        dialog = SettingsDialog(self, self._config)
        if dialog.exec_() == QDialog.Accepted:
            self._config = dialog.get_config()
            if self._storage.save_config(self._config):
                self._monitor_thread.update_config(self._config)
                self.statusBar().showMessage("Настройки сохранены", 3000)

    def _force_scan(self):
        if not self._is_scanning:
            self._monitor_thread.force_scan()
            self.statusBar().showMessage("Принудительная проверка запущена...", 3000)

    def update_hidden_columns_config(self):
        """Обновление конфигурации скрытых колонок (делегирование в TableSettingsManager)"""
        if self._table_settings_manager:
            self._table_settings_manager.update_hidden_columns()
    
    def _show_about_dialog(self):
        """Показать диалог 'О программе'"""
        QMessageBox.about(
            self,
            "О программе",
            "<h3>Network Monitor</h3>"
            "<p>Версия: 3.0 (SQLite Architecture)</p>"
            "<p>Приложение для мониторинга сетевых узлов</p>"
            "<p>© 2024</p>"
        )

    def closeEvent(self, event):
        logging.info("Application closing...")
        if self._monitor_thread:
            self._monitor_thread.stop()
        if hasattr(self, '_db_manager'):
            self._db_manager.close()
        event.accept()

