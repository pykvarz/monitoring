#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервисы приложения
"""
import logging

try:
    from ping3 import ping
except ImportError:
    ping = None

try:
    from plyer import notification
except ImportError:
    notification = None

from PyQt5.QtWidgets import QApplication
from typing import List, Union, Optional

from models import AppConfig
from interfaces import INotificationService, IPingService


class NotificationService(INotificationService):
    """Сервис отправки уведомлений (реализация через plyer)"""

    @staticmethod
    def notify_offline_hosts(hosts: List[str], config: AppConfig) -> None:
        """Отправка уведомлений об упавших узлах"""
        if not hosts or not config.notifications_enabled or not notification:
            return

        title = "⚠️ Ошибка уведомления"
        message = "Не удалось сформировать сообщение"

        try:
            if len(hosts) <= 3:
                title = "⚠️ Узел недоступен"
                message = "\n".join(hosts)
            else:
                title = "⚠️ Несколько узлов недоступны"
                message = f"Недоступно устройств: {len(hosts)}"
        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка отправки уведомлений: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Неизвестная ошибка отправки уведомлений: {e}", exc_info=True)

        try:
            if config.sound_enabled:
                QApplication.beep()

            # Уведомление в трее
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )

        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка отправки уведомления: {e}", exc_info=True)
    
    @staticmethod
    def show_notification(title: str, message: str) -> None:
        """Показ системного уведомления"""
        if not notification:
            return
        
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
        except (ImportError, RuntimeError, OSError) as e:
            logging.error(f"Ошибка показа уведомления: {e}", exc_info=True)


class PingService(IPingService):
    """Сервис для выполнения ping-запросов (реализация через ping3)"""

    @staticmethod
    def ping_host(ip: str, timeout: float = 2.0) -> Optional[bool]:
        """Выполнение ping-запроса"""
        if not ping:
            return None

        try:
            return ping(ip, timeout=timeout)
        except (OSError, ValueError, RuntimeError) as e:
            logging.warning(f"Ошибка ping {ip}: {e}")
            return None