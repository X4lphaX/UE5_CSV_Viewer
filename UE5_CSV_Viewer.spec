# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Code\\UE5_CSV_Viewer\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Code\\UE5_CSV_Viewer\\csv_parser.py', '.')],
    hiddenimports=['OpenGL', 'OpenGL.GL', 'OpenGL.platform.win32', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets'],
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
    a.binaries,
    a.datas,
    [],
    name='UE5_CSV_Viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
