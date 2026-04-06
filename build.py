"""Build script to create standalone app using PyInstaller.

Supports both Windows (.exe) and macOS (.app) builds.
Usage:
    python build.py          # Build for current platform
    python build.py --native # Also compile the C++ native module first
"""

import PyInstaller.__main__
import os
import sys
import platform
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))

# Build native C++ module first if requested
if "--native" in sys.argv:
    print("Building native C++ module...")
    subprocess.check_call(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=script_dir,
    )
    print("Native module built successfully.")

is_macos = platform.system() == "Darwin"
is_windows = platform.system() == "Windows"

# PyInstaller uses ':' as add-data separator on macOS/Linux, ';' on Windows
sep = ":" if not is_windows else ";"

args = [
    os.path.join(script_dir, "main.py"),
    "--name=UE5_CSV_Viewer",
    # macOS .app bundles require --onedir; Windows uses --onefile for a single .exe
    "--onedir" if is_macos else "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    # Exclude unused Qt bindings
    "--exclude-module=PyQt5",
    "--exclude-module=PyQt6",
    "--exclude-module=matplotlib",
    # OpenGL imports
    "--hidden-import=OpenGL",
    "--hidden-import=OpenGL.GL",
    # PySide6 OpenGL
    "--hidden-import=PySide6.QtOpenGL",
    "--hidden-import=PySide6.QtOpenGLWidgets",
    # Bundle csv_parser alongside main
    f"--add-data={os.path.join(script_dir, 'csv_parser.py')}{sep}.",
    # Output paths
    f"--distpath={os.path.join(script_dir, 'dist')}",
    f"--workpath={os.path.join(script_dir, 'build')}",
    f"--specpath={script_dir}",
]

# Platform-specific OpenGL backend
if is_windows:
    args.append("--hidden-import=OpenGL.platform.win32")
elif is_macos:
    args.append("--hidden-import=OpenGL.platform.darwin")

# Bundle the compiled native module if it exists
if is_macos:
    import glob
    native_files = glob.glob(os.path.join(script_dir, "_native_core*.so"))
else:
    import glob
    native_files = glob.glob(os.path.join(script_dir, "_native_core*.pyd"))

if native_files:
    native_path = native_files[0]
    args.append(f"--add-binary={native_path}{sep}.")
    print(f"Bundling native module: {os.path.basename(native_path)}")
else:
    print("Warning: Native module not found. App will use Python fallback.")

# macOS-specific: set bundle identifier and icon placeholder
if is_macos:
    args.append("--osx-bundle-identifier=com.ue5csvviewer.app")

print(f"Building for {platform.system()}...")
PyInstaller.__main__.run(args)

if is_macos:
    print(f"\nDone! macOS app: dist/UE5_CSV_Viewer.app")
    print("You can also find a single executable at: dist/UE5_CSV_Viewer")
elif is_windows:
    print(f"\nDone! Windows exe: dist/UE5_CSV_Viewer.exe")
