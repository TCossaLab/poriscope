# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Alejandra Carolina González González

import os
import subprocess
import platform
import sys
import shutil


def build_wavelet_library():
    root_dir = os.path.abspath(os.path.dirname(__file__))
    wavelet_dir = os.path.abspath(os.path.join(root_dir, "..", "poriscope", "cdlls", "wavelet"))
    build_dirs = ["build", os.path.join("build", "obj"), "dist"]

    for d in build_dirs:
        os.makedirs(os.path.join(wavelet_dir, d), exist_ok=True)

    print(f"[INFO] Building wavelet in: {wavelet_dir}")
    env = os.environ.copy()
    system = platform.system()

    if system == "Windows":
        # Native Windows build using mingw32-make.exe
        mingw_path = r"C:\msys64\mingw64\bin"
        make_exe = os.path.join(mingw_path, "mingw32-make.exe")
        if not os.path.exists(make_exe):
            print("[ERROR] mingw32-make.exe not found. Please install MinGW via MSYS2.")
            sys.exit(1)
        env["PATH"] = mingw_path + os.pathsep + env["PATH"]
        subprocess.run([make_exe, "clean"], cwd=wavelet_dir, env=env)
        subprocess.run([make_exe, "all"], check=True, cwd=wavelet_dir, env=env)

    elif system == "Linux":
        # Cross-compile for Windows on Linux using mingw-w64
        if shutil.which("x86_64-w64-mingw32-gcc") is None:
            print("[ERROR] mingw-w64 is not installed. Run: sudo apt install mingw-w64")
            sys.exit(1)
        subprocess.run(["make", "clean"], cwd=wavelet_dir)
        subprocess.run(["make", "CROSS=true"], check=True, cwd=wavelet_dir)

    elif system == "Darwin":
        # macOS build, generates .dylib instead of .so or .dll
        subprocess.run(["make", "clean"], cwd=wavelet_dir)
        subprocess.run(["make"], check=True, cwd=wavelet_dir)

    else:
        print(f"[ERROR] Unsupported platform: {system}")
        sys.exit(1)

    print("[INFO] wavelet library built successfully.")


if __name__ == "__main__":
    build_wavelet_library()
