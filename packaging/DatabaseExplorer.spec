# PyInstaller recipe for DatabaseExplorer.exe. Build with packaging\build.ps1.
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "backend" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    datas=[(str(ROOT / "frontend" / "dist"), "frontend_dist")],  # the built React app
    hiddenimports=["waitress", "app"],
    excludes=["tkinter", "PIL", "PyInstaller"],  # build-time tools, not needed in the app
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DatabaseExplorer",
    icon=str(ROOT / "packaging" / "icon.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=True,  # the window shows the address and closing it stops the app
    upx=False,     # compressed .exe files trigger more antivirus false alarms
    debug=False,
    strip=False,
)
