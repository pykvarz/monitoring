#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель таблицы хостов (QAbstractTableModel)
"""

from typing import List, Any, Optional
from PyQt5.QtGui import QColor, QBrush, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex, QVariant, QTimer, QByteArray, QRect, QSize
from models import Host, HostStatus, format_offline_time
from datetime import datetime, timezone

class CenteredIconDelegate(QStyledItemDelegate):
    """Делегат для центрирования иконки в ячейке"""
    def paint(self, painter, option, index):
        # Инициализируем стиль
        self.initStyleOption(option, index)
        
        # Отрисовка стандартного фона (выделение, фокус и т.д.)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        else:
            super().paint(painter, option, index)
            
        if index.column() == 0:
            # Получаем иконку
            icon = index.data(Qt.UserRole + 1)
            if isinstance(icon, QIcon) and not icon.isNull():
                size = 20
                rect = option.rect
                x = rect.x() + (rect.width() - size) // 2
                y = rect.y() + (rect.height() - size) // 2
                
                # Рисуем иконку
                icon.paint(painter, x, y, size, size)

class HostTableModel(QAbstractTableModel):
    """
    Высокопроизномительная модель таблицы данных
    """
    COLUMNS = ["Статус", "Название", "IP адрес", "Адрес", "Группа", "Время offline"]

    def __init__(self, parent=None, theme="light"):
        super().__init__(parent)
        self._hosts: List[Host] = []
        self._icon_cache = {}
        self._theme = theme

    def set_theme(self, theme: str):
        """Обновление темы и сброс кэша иконок при необходимости"""
        if self._theme != theme:
            self._theme = theme
            self._icon_cache = {} # Сбрасываем кэш, так как иконки могут зависеть от темы
            self.layoutChanged.emit()

    def _get_icon(self, status: str) -> QIcon:
        """Получение иконки из кэша или создание новой"""
        if status in self._icon_cache:
            return self._icon_cache[status]
        
        svg_data = HostStatus[status].svg
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        icon = QIcon(pixmap)
        self._icon_cache[status] = icon
        return icon
    
    def set_hosts(self, hosts: List[Host]):
        """Установка нового списка хостов"""
        self.beginResetModel()
        self._hosts = list(hosts)
        # Создаем мапу для быстрого поиска индекса по ID
        self._host_map = {h.id: i for i, h in enumerate(self._hosts)}
        self.endResetModel()

    def update_hosts(self, updated_hosts: List[Host]):
        """Точечное обновление узлов без перерисовки всей таблицы"""
        if not updated_hosts:
            return

        for host in updated_hosts:
            if host.id in self._host_map:
                idx = self._host_map[host.id]
                self._hosts[idx] = host
                
                # Обновляем всю строку
                start_index = self.index(idx, 0)
                end_index = self.index(idx, self.columnCount() - 1)
                self.dataChanged.emit(start_index, end_index)
            else:
                pass


    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._hosts)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return QVariant()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._hosts)):
            return QVariant()

        host = self._hosts[index.row()]
        col = index.column()

        # DecorationRole (Иконка) - НЕ ВОЗВРАЩАЕМ стандартно, чтобы не рисовалась слева
        if role == Qt.DecorationRole:
            return QVariant()

        # Кастомная роль для нашего делегата
        if role == Qt.UserRole + 1:
            if col == 0:
                return self._get_icon(host.status)
            return QVariant()

        if role == Qt.DisplayRole:
            if col == 0:
                return ""
            elif col == 1:
                prefix = "" if host.notifications_enabled else "🔕 "
                return f"{prefix}{host.name}"
            elif col == 2:
                return host.ip
            elif col == 3:
                return host.address
            elif col == 4:
                return host.group
            elif col == 5:
                if host.status == "OFFLINE" and host.offline_since:
                    try:
                        utc_now = datetime.now(timezone.utc)
                        offline_since = datetime.fromisoformat(host.offline_since)
                        if offline_since.tzinfo is None:
                            offline_since = offline_since.replace(tzinfo=timezone.utc)
                        duration = utc_now - offline_since
                        return format_offline_time(duration)
                    except ValueError:
                        pass
                return ""

        elif role == Qt.BackgroundRole:
            # Красим ВСЮ строку в цвет статуса
            color_code = HostStatus[host.status].color
            color = QColor(color_code)
            
            # Настройка прозрачности в зависимости от темы
            # В темной теме строка должна быть темнее, но с оттенком цвета
            # В светлой - пастельный оттенок
            if self._theme == "dark":
                color.setAlpha(80)  # Более насыщенный для темной темы
            else:
                color.setAlpha(50)  # Немного ярче для светлой
            
            return QBrush(color)

        elif role == Qt.TextAlignmentRole:
            # Выравнивание по центру для определенных колонок
            if col == 0 or col == 1 or col == 2 or col == 3 or col == 4 or col == 5:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.ForegroundRole:
            # В темной теме подсвечиваем текст времени простоя для offline хостов
            if self._theme == "dark" and host.status == "OFFLINE":
                if col == 5:
                    return QBrush(QColor("#ff6b6b")) # Светло-красный для контраста
                elif col == 1:
                    return QBrush(QColor("#ff6b6b"))

        elif role == Qt.ToolTipRole:
            if col == 0:
                return HostStatus[host.status].title
            elif col == 1:
                return "Уведомления включены" if host.notifications_enabled else "Уведомления отключены"

        return QVariant()

    def get_host(self, row: int) -> Optional[Host]:
        """Получение хоста по индексу строки"""
        if 0 <= row < len(self._hosts):
            return self._hosts[row]
        return None
    
    def sort(self, column: int, order: Qt.SortOrder):
        """Сортировка данных в таблице"""
        self.layoutAboutToBeChanged.emit()
        
        def get_sort_key(host: Host):
            if column == 0:
                order_priority = {"ONLINE": 0, "WAITING": 1, "OFFLINE": 2, "MAINTENANCE": 3}
                return order_priority.get(host.status, 9)
            elif column == 1: return host.name.lower()
            elif column == 2: 
                try:
                    return [int(part) for part in host.ip.split('.')]
                except Exception:
                    return host.ip
            elif column == 3: return host.address.lower()
            elif column == 4: return host.group.lower()
            elif column == 5: 
                if host.offline_since:
                    return host.offline_since
                return ""
            return ""

        reverse = (order == Qt.DescendingOrder)
        self._hosts.sort(key=get_sort_key, reverse=reverse)
        
        self.layoutChanged.emit()
    
    def update_host_status(self, host_id: str, status: str, offline_since: str, offline_time: str) -> bool:
        """Обновление статуса хоста в модели"""
        for row, host in enumerate(self._hosts):
            if host.id == host_id:
                host.status = status
                if offline_since:
                    host.offline_since = offline_since
                
                start_index = self.index(row, 0)
                end_index = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(start_index, end_index)
                return True
        return False
    
    def get_selected_rows(self) -> List[int]:
        """Получить список выбранных строк"""
        if not hasattr(self, '_parent_table') or not self._parent_table:
            return []
        
        selection_model = self._parent_table.selectionModel()
        if not selection_model:
            return []
        
        selected_indexes = selection_model.selectedRows()
        return [index.row() for index in selected_indexes]
    
    def set_parent_table(self, table) -> None:
        """Установить родительскую таблицу для получения выделения"""
        self._parent_table = table