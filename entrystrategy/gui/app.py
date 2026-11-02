"""Pywebview GUI Application for Entry Strategy Matrix."""
import json
import logging
import os
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
    """Applies custom icon & styles to Win32 window for crisp taskbar thumbnail & alt-tab display."""
    if sys.platform != "win32":
        return

    ico_path = str((Path(__file__).parent.parent.parent / "assets" / "icon.ico").resolve())
    if not Path(ico_path).exists():
        logger.debug(f"Icon not found at {ico_path}")
        return

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010
    WM_SETICON = 0x0080
    ICON_BIG = 1
    ICON_SMALL = 0
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_EX_APPWINDOW = 0x00040000
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    hicon_big = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
    hicon_small = ctypes.windll.user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

    SetClassLong = getattr(ctypes.windll.user32, "SetClassLongPtrW", None) or getattr(ctypes.windll.user32, "SetClassLongW", None)

    pid = os.getpid()

    # Retry polling for up to 10 seconds until GUI window is ready
    for attempt in range(25):
        time.sleep(0.3)
        found_hwnds = []

        # 1. Try FindWindowW by title
        h1 = ctypes.windll.user32.FindWindowW(None, "Entry Strategy Matrix")
        if h1:
            found_hwnds.append(h1)

        # 2. Enumerate visible top-level windows for this process
        def enum_cb(hwnd, _):
            p = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                if hwnd not in found_hwnds:
                    found_hwnds.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        if found_hwnds:
            for hwnd in found_hwnds:
                try:
                    # Set window style so Windows Taskbar generates live thumbnail and minimize/restore
                    cur_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, cur_style | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)

                    cur_ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, cur_ex | WS_EX_APPWINDOW)

                    # Send WM_SETICON for taskbar icon and Alt-Tab thumbnail
                    if hicon_big:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                    if hicon_small:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

                    # Set class long so it sticks permanently
                    if SetClassLong and hicon_big:
                        SetClassLong(hwnd, -14, hicon_big)
                    if SetClassLong and hicon_small:
                        SetClassLong(hwnd, -34, hicon_small)

                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
                except Exception as ex:
                    logger.debug(f"Error attaching taskbar thumbnail/icon to hwnd {hwnd}: {ex}")

            logger.info(f"Taskbar thumbnail and icon attached to {len(found_hwnds)} window(s).")
            break


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

    def toggle_simple_mode(self, is_simple: bool) -> bool:
        """Toggles between Full Matrix Window and Mini Simple Mode pinned near taskbar."""
        if not self._window:
            return False

        try:
            if is_simple:
                # Save previous geometry
                self._prev_width = getattr(self._window, "width", 1200)
                self._prev_height = getattr(self._window, "height", 750)
                self._prev_x = getattr(self._window, "x", 100)
                self._prev_y = getattr(self._window, "y", 100)

                target_w = 345
                target_h = 44
                target_x = 100
                target_y = 100

                if sys.platform == "win32":
                    import ctypes.wintypes
                    work_area = ctypes.wintypes.RECT()
                    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0)
                    # Position at bottom-right right above taskbar
                    target_x = max(10, work_area.right - target_w - 20)
                    target_y = max(10, work_area.bottom - target_h - 10)

                self._window.resize(target_w, target_h)
                self._window.move(target_x, target_y)
                self._window.on_top = True

                if sys.platform == "win32":
                    pid = os.getpid()
                    def enum_cb(hwnd, _):
                        p = ctypes.c_ulong()
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                        if p.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                            HWND_TOPMOST = -1
                            SWP_SHOWWINDOW = 0x0040
                            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, target_x, target_y, target_w, target_h, SWP_SHOWWINDOW)
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                return True
            else:
                prev_w = max(1000, getattr(self, "_prev_width", 1200))
                prev_h = max(650, getattr(self, "_prev_height", 750))
                prev_x = max(0, getattr(self, "_prev_x", 100))
                prev_y = max(0, getattr(self, "_prev_y", 100))

                self._window.on_top = False
                self._window.resize(prev_w, prev_h)
                self._window.move(prev_x, prev_y)

                if sys.platform == "win32":
                    pid = os.getpid()
                    def enum_cb(hwnd, _):
                        p = ctypes.c_ulong()
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                        if p.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                            HWND_NOTOPMOST = -2
                            SWP_SHOWWINDOW = 0x0040
                            ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, prev_x, prev_y, prev_w, prev_h, SWP_SHOWWINDOW)
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                return False
        except Exception as e:
            logger.error(f"Error toggling simple mode: {e}")
            return False

    def update_taskbar_title(self, buy_str: str, sell_str: str):
        """Dynamically updates window title so Windows Taskbar previews show live signal totals."""
        if self._window:
            self._window.title = f"{buy_str} | {sell_str} - Entry Strategy Matrix"


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
        min_size=(250, 36),
        js_api=api,
    )
    api.set_window(window)

    # Start pywebview and invoke taskbar thumbnail and icon attachment
    webview.start(_apply_taskbar_icon, debug=False)
