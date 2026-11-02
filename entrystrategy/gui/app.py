"""Pywebview GUI Application for Entry Strategy Matrix."""
import json
import logging
import sys
import ctypes
import threading
import time
from pathlib import Path
from typing import Optional
import webview

from entrystrategy.service import EntryStrategyService

logger = logging.getLogger("EntryStrategy.GUI")

if sys.platform == "win32":
    try:
        myappid = "EntryStrategy.PatternMatrix.v1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        logger.debug(f"Could not set AppUserModelID: {e}")


def _apply_taskbar_icon():
    """Applies custom icon to Win32 window for crisp taskbar & alt-tab display."""
    if sys.platform != "win32":
        return
    try:
        time.sleep(0.5)
        hwnd = ctypes.windll.user32.FindWindowW(None, "Entry Strategy Matrix")
        if hwnd:
            ico_path = str(Path(__file__).parent.parent.parent / "assets" / "icon.ico")
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            hicon_big = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
            hicon_small = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            WM_SETICON = 0x0080
            if hicon_big:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)
    except Exception as e:
        logger.debug(f"Taskbar icon notice: {e}")


class MatrixWindowAPI:
    """JS API bridge exposed to the pywebview frontend."""
    def __init__(self, service: EntryStrategyService):
        self._service = service
        self._window: Optional[webview.Window] = None

    def set_window(self, window: webview.Window):
        self._window = window

    # Window Controls (Frameless Title Bar)
    def minimize_window(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self):
        if self._window:
            try:
                self._window.maximize()
            except Exception:
                pass

    def close_window(self):
        if self._window:
            self._service.stop()
            self._window.destroy()

    # Data API
    def get_matrix_state(self) -> str:
        state = self._service.get_matrix_state()
        return json.dumps(state)

    def trigger_manual_test(self, pattern_id: int, direction_str: str) -> str:
        res = self._service.trigger_pattern_manual_test(pattern_id, direction_str)
        return json.dumps(res)

    def clear_signals(self) -> str:
        res = self._service.clear_signals()
        return json.dumps(res)


def launch_gui(service: Optional[EntryStrategyService] = None):
    """Launches single-window frameless app."""
    entry_service = service or EntryStrategyService()
    api = MatrixWindowAPI(entry_service)

    html_file = Path(__file__).parent / "templates" / "index.html"

    window = webview.create_window(
        title=entry_service.config.window_title,
        url=str(html_file.resolve()),
        width=entry_service.config.window_width,
        height=entry_service.config.window_height,
        frameless=entry_service.config.frameless,
        resizable=True,
        min_size=(1000, 600),
        js_api=api,
    )
    api.set_window(window)

    threading.Thread(target=_apply_taskbar_icon, daemon=True).start()

    # Start pywebview event loop
    webview.start(debug=False)
