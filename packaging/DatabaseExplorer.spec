# PyInstaller recipe for the Database Explorer app folder. Build with packaging\build.ps1,
# which then wraps the folder into the installer (installer.iss).
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "backend" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    datas=[(str(ROOT / "frontend" / "dist"), "frontend_dist")],  # the built React app
    hiddenimports=["waitress", "app", "lifecycle"],
    excludes=["tkinter", "PIL", "PyInstaller"],  # build-time tools, not needed in the app
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # folder build: starts faster than a single self-unpacking .exe
    name="DatabaseExplorer",
    icon=str(ROOT / "packaging" / "icon.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,  # no black window; errors are shown as dialogs and logged
    upx=False,      # compressed files trigger more antivirus false alarms
    debug=False,
    strip=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DatabaseExplorer", upx=False, strip=False)
