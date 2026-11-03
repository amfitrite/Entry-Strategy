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
    config = AppConfig(enable_simulation=False)
    service = EntryStrategyService(config, start_servers=False)
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


def test_matrix_window_api_recent_signals_history():
    """Verify that recent_signals history journal is provided in get_matrix_state."""
    config = AppConfig(enable_simulation=False)
    service = EntryStrategyService(config, start_servers=False)
    api = MatrixWindowAPI(service)

    # Initial state: history empty
    state_str = api.get_matrix_state()
    state = json.loads(state_str)
    assert "recent_signals" in state
    assert isinstance(state["recent_signals"], list)
    assert len(state["recent_signals"]) == 0

    # Trigger manual test signal
    api.trigger_manual_test(1, "BUY")
    state_str2 = api.get_matrix_state()
    state2 = json.loads(state_str2)
    assert len(state2["recent_signals"]) == 1
    sig = state2["recent_signals"][0]
    assert sig["pattern_id"] == 1
    assert sig["direction"] == "BUY"
    assert "execution_price" in sig
    assert "invalidation_price" in sig
    assert "status" in sig

    # Trigger second test signal
    api.trigger_manual_test(13, "SELL")
    state_str3 = api.get_matrix_state()
    state3 = json.loads(state_str3)
    assert len(state3["recent_signals"]) == 2
    assert state3["recent_signals"][0]["pattern_id"] == 13

    # Clear signals resets history
    api.clear_signals()
    state_str4 = api.get_matrix_state()
    state4 = json.loads(state_str4)
    assert len(state4["recent_signals"]) == 0

    service.stop()


def test_ui_template_tier_icons_and_apex_sorting():
    """Verify index.html contains tier icons, top-left apex tier sorting, and grading modal population."""
    import pathlib
    template_path = pathlib.Path(__file__).parent.parent / "entrystrategy" / "gui" / "templates" / "index.html"
    assert template_path.exists(), "index.html template missing"
    html = template_path.read_text(encoding="utf-8")

    # 1. Distinct tier icons exist
    assert "👑" in html, "👑 SSS Crown icon missing"
    assert "💠" in html, "💠 SS Prismatic crystal icon missing"
    assert "💎" in html, "💎 S Diamond icon missing"
    assert "🎖️" in html, "🎖️ A Medal icon missing"
    assert "🎯" in html, "🎯 B Target icon missing"
    assert "⚪" in html, "⚪ C Circle icon missing"
    assert "⛔" in html, "⛔ D Stop disc icon missing"

    # 2. JavaScript helper functions exist
    assert "function getTierIcon(tier)" in html
    assert "function getTierWeight(tier)" in html
    assert "sortByTierApex = true" in html

    # 3. Top-Left Apex priority sort in renderSignals
    assert "getTierWeight(tierB) - getTierWeight(tierA)" in html
    assert "scB - scA" in html

    # 4. Modal grading population
    assert "function populateModalGrading(sig, p)" in html
    assert "modalGradeBadge" in html
    assert "modalCappedNotice" in html
    assert "modalGradeReasonsContainer" in html
    assert "compPatternQuality" in html
    assert "compMarketStructure" in html
    assert "compLocationQuality" in html
    assert "compCandleConfirm" in html
    assert "compExecutionQuality" in html

    # 5. Distinct lifecycle status colors, icons & classes
    assert ".status-pending" in html
    assert ".status-confirmed" in html
    assert ".status-active" in html
    assert ".status-invalidated" in html
    assert ".status-expired" in html
    assert "card-status-pending-confirmation" in html
    assert "card-status-confirmed" in html
    assert "kpiPending" in html
    assert "btnHistFilterPending" in html
    assert "⏳" in html, "⏳ Pending icon missing"
    assert "✔" in html, "✔ Confirmed icon missing"
    assert "🟢" in html, "🟢 Active icon missing"
    assert "✖" in html, "✖ Invalidated icon missing"
    assert "⏱" in html, "⏱ Expired icon missing"


def test_gui_window_geometry_sanitization():
    """Verify that off-screen minimized coordinates (-32000) are never captured or loaded."""
    config = AppConfig(enable_simulation=False)
    service = EntryStrategyService(config, start_servers=False)
    api = MatrixWindowAPI(service)

    # 1. Mock window with minimized coordinates
    mock_win = MockWebviewWindow()
    mock_win.x = -32000
    mock_win.y = -32000
    mock_win.width = 160
    mock_win.height = 30
    api.set_window(mock_win)

    # 2. Query geometry: should NOT return negative off-screen coordinates
    geom = api._collect_window_geometry()
    assert geom.get("x") != -32000
    assert geom.get("y") != -32000

    service.stop()



