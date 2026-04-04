"""Build script to create standalone .exe using PyInstaller."""

import PyInstaller.__main__
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(script_dir, "main.py"),
    "--name=UE5_CSV_Viewer",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--exclude-module=PyQt5",
    "--exclude-module=PyQt6",
    "--exclude-module=matplotlib",
    "--hidden-import=OpenGL",
    "--hidden-import=OpenGL.GL",
    "--hidden-import=OpenGL.platform.win32",
    "--hidden-import=PySide6.QtOpenGL",
    "--hidden-import=PySide6.QtOpenGLWidgets",
    f"--add-data={os.path.join(script_dir, 'csv_parser.py')};.",
    f"--distpath={os.path.join(script_dir, 'dist')}",
    f"--workpath={os.path.join(script_dir, 'build')}",
    f"--specpath={script_dir}",
])
