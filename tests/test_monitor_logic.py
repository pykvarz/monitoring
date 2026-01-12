
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor_thread import MonitorThread
from models import Host, AppConfig

class TestMonitorLogic(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.offline_timeout = 30 # seconds
        self.mock_config.waiting_timeout = 5 # seconds
        self.mock_config.poll_interval = 2
        self.mock_config.max_workers = 5
        
        # Create instance without calling __init__ fully if possible?
        # No, QThread init is safe usually. 
        self.thread = MonitorThread(self.mock_repo, self.mock_config)

    def test_online_remains_online(self):
        host = Host("1", "127.0.0.1", "Local", status="ONLINE")
        ping_status = "ONLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertIsNone(offline_since)
        self.assertTrue(update)

    def test_online_to_waiting_logic(self):
        # Initial failure
        host = Host("1", "127.0.0.1", "Local", status="ONLINE")
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        # Should set offline_since, but status stays ONLINE (or whatever) until timeout
        self.assertEqual(new_status, "ONLINE")
        self.assertIsNotNone(offline_since)
        self.assertTrue(update)

    def test_waiting_logic(self):
        # 10 seconds later (Waiting phase)
        start_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        host = Host("1", "127.0.0.1", "Local", status="ONLINE", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "WAITING")
        self.assertTrue(update)

    def test_waiting_to_offline(self):
        # 40 seconds later (Offline phase)
        start_time = datetime.now(timezone.utc) - timedelta(seconds=40)
        # Note: Previous status could be WAITING or ONLINE depending on checks
        host = Host("1", "127.0.0.1", "Local", status="WAITING", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "OFFLINE")
        self.assertTrue(update)

    def test_offline_remains_offline(self):
        start_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        host = Host("1", "127.0.0.1", "Local", status="OFFLINE", offline_since=start_time.isoformat())
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "OFFLINE")
        
    def test_offline_to_online(self):
        host = Host("1", "127.0.0.1", "Local", status="OFFLINE", offline_since="some_date")
        ping_status = "ONLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "ONLINE")
        self.assertIsNone(offline_since)
        self.assertTrue(update)

    def test_maintenance_ignores_offline(self):
        host = Host("1", "127.0.0.1", "Local", status="MAINTENANCE")
        ping_status = "OFFLINE"
        now = datetime.now(timezone.utc)
        
        new_status, offline_since, update = self.thread._calculate_status(host, ping_status, now)
        
        self.assertEqual(new_status, "MAINTENANCE")
        self.assertFalse(update)

if __name__ == '__main__':
    unittest.main()
