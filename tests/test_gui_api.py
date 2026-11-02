"""Unit Tests for MatrixWindowAPI and Simple Mode backend contract."""
import json
import pytest
from entrystrategy.gui.app import MatrixWindowAPI
from entrystrategy.service import EntryStrategyService
from entrystrategy.config import AppConfig


class MockWebviewWindow:
    def __init__(self):
        self.title = "Entry Strategy Matrix"
        self.width = 1200
        self.height = 750
        self.x = 100
        self.y = 100
        self.on_top = False
        self.minimized = False
        self.destroyed = False

    def resize(self, w: int, h: int):
        self.width = w
        self.height = h

    def move(self, x: int, y: int):
        self.x = x
        self.y = y

    def minimize(self):
        self.minimized = True

    def destroy(self):
        self.destroyed = True


def test_matrix_window_api_toggle_simple_mode():
    config = AppConfig(enable_simulation=False, bridge_port=5578)
    service = EntryStrategyService(config)
    api = MatrixWindowAPI(service)
    mock_win = MockWebviewWindow()
    api.set_window(mock_win)

    # 1. Toggle Simple Mode to True
    res_str = api.toggle_simple_mode(True)
    res = json.loads(res_str)
    assert res["success"] is True
    assert res["is_simple"] is True
    assert mock_win.on_top is True
    assert mock_win.width <= 500  # Compact mini size
    assert mock_win.height <= 80

    # 2. Toggle Simple Mode to False (Restore)
    res_restore_str = api.toggle_simple_mode(False)
    res_restore = json.loads(res_restore_str)
    assert res_restore["success"] is True
    assert res_restore["is_simple"] is False
    assert mock_win.on_top is False
    assert mock_win.width == 1200  # Restored exact user geometry
    assert mock_win.height == 750
    assert mock_win.x == 100
    assert mock_win.y == 100

    # 3. Test title update caching
    api.update_taskbar_title("▲ BUY: 5 (Tot: 100)", "▼ SELL: 3 (Tot: 90)")
    assert "▲ BUY: 5" in mock_win.title
    assert "▼ SELL: 3" in mock_win.title

    service.stop()
