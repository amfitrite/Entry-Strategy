"""Pywebview GUI Application for Entry Strategy Matrix with Robust Win32 & DPI Integration."""
import json
import logging
import os
import sys
import ctypes
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import webview

from entrystrategy.service import EntryStrategyService

logger = logging.getLogger("EntryStrategy.GUI")

if sys.platform == "win32":
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    try:
        myappid = "EntryStrategy.PatternMatrix.v1.0"
        shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        logger.debug(f"Could not set AppUserModelID: {e}")

    # Correct 64-bit and 32-bit Win32 Callback Definitions
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL,
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPARAM,
    )
    user32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.wintypes.LPARAM]
    user32.EnumWindows.restype = ctypes.wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
    user32.IsWindowVisible.restype = ctypes.wintypes.BOOL
    user32.FindWindowW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR]
    user32.FindWindowW.restype = ctypes.wintypes.HWND
    user32.SetWindowPos.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.wintypes.UINT,
    ]
    user32.SetWindowPos.restype = ctypes.wintypes.BOOL

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork", ctypes.wintypes.RECT),
            ("dwFlags", ctypes.wintypes.DWORD),
        ]


def _get_app_hwnd(window_title: str) -> Optional[int]:
    """Finds the top-level visible window HWND for current process on Windows."""
    if sys.platform != "win32":
        return None

    # 1. Direct title lookup
    h1 = user32.FindWindowW(None, window_title)
    if h1 and user32.IsWindowVisible(h1):
        return h1

    # 2. Process-specific window enumeration with 64-bit safe callback
    pid = os.getpid()
    found_hwnds = []

    def enum_cb(hwnd, _):
        p = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            found_hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return found_hwnds[0] if found_hwnds else None


def _get_monitor_work_area_and_dpi(hwnd: int) -> Tuple[Tuple[int, int, int, int], float]:
    """Retrieves work area (left, top, right, bottom) of the monitor containing hwnd and its DPI scale."""
    work_rect = None
    scale_factor = 1.0

    if sys.platform == "win32" and hwnd:
        MONITOR_DEFAULTTONEAREST = 2
        hMonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if hMonitor:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                work_rect = (mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom)

        # Get DPI
        dpi = 96
        try:
            get_dpi_for_window = getattr(user32, "GetDpiForWindow", None)
            if get_dpi_for_window:
                dpi = get_dpi_for_window(hwnd)
            else:
                get_dpi_for_system = getattr(user32, "GetDpiForSystem", None)
                if get_dpi_for_system:
                    dpi = get_dpi_for_system()
        except Exception:
            dpi = 96
        scale_factor = max(1.0, dpi / 96.0)

    if not work_rect and sys.platform == "win32":
        # Fallback to system SPI_GETWORKAREA
        wa = ctypes.wintypes.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0)
        work_rect = (wa.left, wa.top, wa.right, wa.bottom)
    elif not work_rect:
        work_rect = (0, 0, 1920, 1080)

    return work_rect, scale_factor


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

    hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
    hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    SetClassLong = getattr(user32, "SetClassLongPtrW", None) or getattr(user32, "SetClassLongW", None)

    for _ in range(25):
        time.sleep(0.3)
        hwnd = _get_app_hwnd("Entry Strategy Matrix")
        if hwnd:
            try:
                cur_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                user32.SetWindowLongW(hwnd, GWL_STYLE, cur_style | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)

                cur_ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, cur_ex | WS_EX_APPWINDOW)

                if hicon_big:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                if hicon_small:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

                if SetClassLong and hicon_big:
                    SetClassLong(hwnd, -14, hicon_big)
                if SetClassLong and hicon_small:
                    SetClassLong(hwnd, -34, hicon_small)

                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
                logger.info(f"Taskbar thumbnail and icon attached cleanly to hwnd {hwnd}.")
            except Exception as ex:
                logger.debug(f"Error attaching taskbar thumbnail to hwnd {hwnd}: {ex}")
            break


class MatrixWindowAPI:
    """JS API bridge exposed to the pywebview frontend."""
    def __init__(self, service: EntryStrategyService):
        self._service = service
        self._window: Optional[webview.Window] = None
        self._is_simple_mode = False
        self._prev_rect: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
        self._last_title_str: Optional[str] = None

    def set_window(self, window: webview.Window):
        self._window = window

    # Window Controls
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
        """Cleanly stops backend services and exits process without leaving zombie python processes."""
        try:
            self._service.stop()
        except Exception:
            pass
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        # Force clean process termination
        os._exit(0)

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

    def toggle_simple_mode(self, requested_state: bool) -> str:
        """Toggles between Full Matrix Window and Mini Simple Mode pinned near taskbar.
        Returns a verified JSON confirmation so frontend DOM only updates on confirmed success.
        """
        if not self._window:
            return json.dumps({"success": False, "is_simple": self._is_simple_mode, "error": "No window"})

        try:
            hwnd = _get_app_hwnd(self._window.title)

            if requested_state:
                # Entering Simple Mode: Record EXACT user geometry before shrinking
                cur_w = int(getattr(self._window, "width", 1200))
                cur_h = int(getattr(self._window, "height", 750))
                cur_x = int(getattr(self._window, "x", 100))
                cur_y = int(getattr(self._window, "y", 100))
                self._prev_rect = (cur_x, cur_y, cur_w, cur_h)

                # Query specific monitor work area & DPI scaling for the monitor holding this window
                (w_left, w_top, w_right, w_bottom), scale = _get_monitor_work_area_and_dpi(hwnd)

                target_w = int(350 * scale)
                target_h = int(46 * scale)

                # Dock near bottom right, right above the taskbar of THAT monitor
                target_x = max(w_left + 10, w_right - target_w - int(16 * scale))
                target_y = max(w_top + 10, w_bottom - target_h - int(10 * scale))

                self._window.resize(target_w, target_h)
                self._window.move(target_x, target_y)
                self._window.on_top = True

                if sys.platform == "win32" and hwnd:
                    HWND_TOPMOST = -1
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, target_x, target_y, target_w, target_h, SWP_SHOWWINDOW)

                self._is_simple_mode = True
                return json.dumps({"success": True, "is_simple": True})

            else:
                # Restoring Full Window: Restore exact saved geometry without artificial clamping
                if self._prev_rect:
                    rx, ry, rw, rh = self._prev_rect
                else:
                    rx, ry, rw, rh = 100, 100, 1200, 750

                self._window.on_top = False
                self._window.resize(max(400, rw), max(300, rh))
                self._window.move(rx, ry)

                if sys.platform == "win32" and hwnd:
                    HWND_NOTOPMOST = -2
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, rx, ry, rw, rh, SWP_SHOWWINDOW)

                self._is_simple_mode = False
                return json.dumps({"success": True, "is_simple": False})

        except Exception as e:
            logger.error(f"Error toggling simple mode: {e}")
            return json.dumps({"success": False, "is_simple": self._is_simple_mode, "error": str(e)})

    def update_taskbar_title(self, buy_str: str, sell_str: str):
        """Dynamically updates window title only when text changes, avoiding event spam."""
        if not self._window:
            return
        new_title = f"{buy_str} | {sell_str} - Entry Strategy Matrix"
        if self._last_title_str != new_title:
            self._last_title_str = new_title
            self._window.title = new_title


def launch_gui(service: Optional[EntryStrategyService] = None):
    """Launches single-window frameless app with clean termination handling."""
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

    def on_window_closed():
        try:
            entry_service.stop()
        except Exception:
            pass
        os._exit(0)

    window.events.closed += on_window_closed

    # Start pywebview and invoke taskbar thumbnail and icon attachment
    webview.start(_apply_taskbar_icon, debug=False)
