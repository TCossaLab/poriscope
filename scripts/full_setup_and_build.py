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
import platform
import shutil
import subprocess
import sys

from PySide6.QtWidgets import QApplication, QFileDialog

DLL_PATH = os.path.abspath("poriscope/cdlls/wavelet/dist/wavelet.dll")
CORRECT_PYTHON = shutil.which("python")


def prompt_user_for_folder(title="Select a folder", start_path="~/"):
    QApplication.instance() or QApplication([])

    if platform.system() == "Windows":
        import ctypes

        ctypes.windll.user32.SetForegroundWindow(
            ctypes.windll.kernel32.GetConsoleWindow()
        )

    folder = QFileDialog.getExistingDirectory(
        None,
        title,
        os.path.expanduser(start_path),
        QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
    )

    if not folder:
        print("[FATAL] No folder selected. Exiting.")
        sys.exit(1)

    return folder


# Windows-only: MSYS2 detection
def find_msys2_path():
    if platform.system() != "Windows":
        return None

    default_path = r"C:\msys64"
    if os.path.isdir(default_path):
        print(f"[INFO] MSYS2 found at default location: {default_path}")
        return default_path

    bash_path = shutil.which("bash.exe")
    if bash_path and "msys" in bash_path.lower():
        msys2_root = os.path.abspath(os.path.join(bash_path, "..", ".."))
        if os.path.isdir(msys2_root):
            print(f"[INFO] MSYS2 detected via bash in PATH: {msys2_root}")
            return msys2_root

    print("[WARNING] MSYS2 not detected automatically.")
    return prompt_user_for_folder("Select your MSYS2 installation folder", "C:/")


def abort_if_wrong_python():
    python_path = sys.executable
    print(f"[INFO] Running with Python: {python_path}")
    if platform.system() == "Windows" and "msys64" in python_path.lower():
        print(
            "[ERROR] This script is running under MSYS2's Python. Use your system Python instead."
        )
        sys.exit(1)


# Windows-only: Toolchain check
def check_mingw_toolchain(make_exe_path):
    if platform.system() != "Windows":
        return

    if not os.path.exists(make_exe_path):
        print("[ERROR] mingw32-make.exe not found.")
        print(f"[ERROR] Expected at: {make_exe_path}")
        print("[HINT] Please install the MinGW toolchain using MSYS2.")
        sys.exit(1)
    print(f"[INFO] mingw32-make.exe found at: {make_exe_path}")


# Windows-only: Install MSYS2 packages
def run_msys2_commands(msys_bash):
    if platform.system() != "Windows":
        return

    print("[INFO] Updating MSYS2 and installing toolchain...")
    cmds = [
        "pacman -Syuu --noconfirm",
        "pacman -Su --noconfirm",
        "pacman -S mingw-w64-x86_64-gcc mingw-w64-x86_64-make --noconfirm",
    ]
    for cmd in cmds:
        print(f"[MSYS2] Running: {cmd}")
        subprocess.run([msys_bash, "-lc", cmd], check=True)
    print("[INFO] Toolchain setup complete.")


# DLL Build
def build_wavelet(extra_path=None):
    if os.path.exists(DLL_PATH):
        print("[INFO] wavelet.dll already exists. Skipping build.")
        return

    print("[INFO] Building wavelet DLL...")
    env = os.environ.copy()
    if extra_path:
        env["PATH"] = extra_path + os.pathsep + env["PATH"]

    if CORRECT_PYTHON is not None:
        print(f"[INFO] Using Python to build DLL: {CORRECT_PYTHON}")
        subprocess.run([CORRECT_PYTHON, "build_wavelet.py"], check=True, env=env)
        print("[INFO] DLL built successfully.")
    else:
        print("[ERROR] unable to find python.")


def main():
    abort_if_wrong_python()

    msys2_path = find_msys2_path() if platform.system() == "Windows" else None
    mingw_bin = os.path.join(msys2_path, "mingw64", "bin") if msys2_path else None
    msys_bash = (
        os.path.join(msys2_path, "usr", "bin", "bash.exe") if msys2_path else None
    )
    make_exe = os.path.join(mingw_bin, "mingw32-make.exe") if mingw_bin else None

    run_msys2_commands(msys_bash)
    check_mingw_toolchain(make_exe)
    build_wavelet(mingw_bin if platform.system() == "Windows" else None)


if __name__ == "__main__":
    main()
