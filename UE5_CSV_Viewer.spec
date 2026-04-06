# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/jacopopugioni/Desktop/Code/UE5_CSV_Viewer/main.py'],
    pathex=[],
    binaries=[('/Users/jacopopugioni/Desktop/Code/UE5_CSV_Viewer/_native_core.cpython-39-darwin.so', '.')],
    datas=[('/Users/jacopopugioni/Desktop/Code/UE5_CSV_Viewer/csv_parser.py', '.')],
    hiddenimports=['OpenGL', 'OpenGL.GL', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'OpenGL.platform.darwin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UE5_CSV_Viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UE5_CSV_Viewer',
)
app = BUNDLE(
    coll,
    name='UE5_CSV_Viewer.app',
    icon=None,
    bundle_identifier='com.ue5csvviewer.app',
)
