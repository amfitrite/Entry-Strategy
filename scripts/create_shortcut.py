"""Creates desktop shortcut with custom icon and pythonw target."""
import os
import sys
from pathlib import Path
from win32com.client import Dispatch


def make_shortcut():
    desktop_dir = Path(os.environ.get("USERPROFILE", "C:/Users/Ruji Tongki")) / "Desktop"
    if not desktop_dir.exists():
        desktop_dir = Path("C:/Users/Ruji Tongki/Desktop")

    shortcut_path = desktop_dir / "Entry Strategy Matrix.lnk"

    pythonw_exe = Path(sys.executable).parent / "pythonw.exe"
    if not pythonw_exe.exists():
        pythonw_exe = Path("C:/Users/Ruji Tongki/AppData/Local/Python/pythoncore-3.14-64/pythonw.exe")

    project_dir = Path("D:/Entry Strategy").resolve()
    target_script = project_dir / "run_app.py"
    icon_path = project_dir / "assets" / "icon.ico"

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(pythonw_exe)
    shortcut.Arguments = f'"{target_script}"'
    shortcut.WorkingDirectory = str(project_dir)
    shortcut.IconLocation = f"{icon_path},0"
    shortcut.Description = "Entry Strategy Matrix - 40 Agnostic Trading Strategy Families (Port 5558)"
    shortcut.save()

    print(f"Desktop shortcut created successfully at: {shortcut_path}")
    print(f"Target: {pythonw_exe} {target_script}")
    print(f"Icon: {icon_path}")


if __name__ == "__main__":
    make_shortcut()
