# PyInstaller spec — build the AgnoSpeech Workbench into one executable.
#
#   cd workbench
#   pip install -e ../agnospeech-lib pyinstaller pywebview
#   pyinstaller build/workbench.spec
#
# Output: dist/agnospeech-workbench  (a single-file native executable; .exe on Windows)

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Paths in a .spec resolve relative to the spec file, so anchor to the project root.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(ROOT, "web"), "web")]
binaries = []
hiddenimports = collect_submodules("agnospeech") + collect_submodules("agnospeech_workbench")

# Heavy scientific deps need explicit collection.
for pkg in ("sklearn", "scipy", "numpy", "pandas"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# pywebview is optional; include it if present so the bundled app gets a window.
try:
    d, b, h = collect_all("webview")
    datas += d; binaries += b; hiddenimports += h
except Exception:
    pass


a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="agnospeech-workbench",
    console=False,
    onefile=True,
    upx=False,
)
