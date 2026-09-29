# PyInstaller spec for the portable Windows build.
# Build on a Windows machine (inside the project's venv) with:
#   pyinstaller Fillicity.spec
# Output: dist/Fillicity/Fillicity.exe (portable folder, no installer needed)

block_cipher = None

a = Analysis(
    ["fillicity.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pyautogui",
        "pyscreeze",
        "mss",
        "PIL",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fillicity",
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Fillicity",
)
