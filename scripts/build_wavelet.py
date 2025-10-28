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
import shutil
import glob


def try_make(target, cwd, env=None):
    print(f"[INFO] Trying to build target: {target}")
    try:
        subprocess.run(["make", target], check=True, cwd=cwd, env=env)
    except subprocess.CalledProcessError:
        print(f"[WARNING] Failed to build target: {target}")


def _ext_for_system(system: str) -> str | None:
    """Return desired binary extension for the current OS."""
    return {"Windows": ".dll", "Linux": ".so", "Darwin": ".dylib"}.get(system)


def _candidate_names(ext: str):
    """Common output names from Makefiles/toolchains."""
    base = ["wavelet", "libwavelet"]
    return [f"{b}{ext}" for b in base]


def _wavelet_exists(wavelet_dir: str, system: str) -> bool:
    """
    Check for a built wavelet binary in typical output folders.
    Looks in:
      - wavelet_dir
      - wavelet_dir/dist
      - wavelet_dir/build
      - any nested subdirs (recursive) as a fallback
    """
    ext = _ext_for_system(system)
    if not ext:
        return False

    names = set(_candidate_names(ext))
    search_dirs = [
        wavelet_dir,
        os.path.join(wavelet_dir, "dist"),
        os.path.join(wavelet_dir, "build"),
    ]

    # Direct checks in common dirs
    for d in search_dirs:
        for name in names:
            if os.path.isfile(os.path.join(d, name)):
                return True

    # Fallback: recursive glob for any *wavelet*.<ext> under wavelet_dir
    pattern = os.path.join(wavelet_dir, f"**/*wavelet*{ext}")
    for p in glob.glob(pattern, recursive=True):
        if os.path.isfile(p):
            return True

    return False


def build_wavelet_library():
    root_dir = os.path.abspath(os.path.dirname(__file__))
    wavelet_dir = os.path.abspath(os.path.join(root_dir, "..", "poriscope", "cdlls", "wavelet"))
    print(f"[INFO] Building wavelet in: {wavelet_dir}")

    if not os.path.isdir(wavelet_dir):
        print(f"[ERROR] Wavelet directory not found: {wavelet_dir}")
        return

    system = platform.system()

    # Skip build if the corresponding binary already exists
    if _wavelet_exists(wavelet_dir, system):
        print("wavelet extension already present")
        return

    env = os.environ.copy()

    if system == "Windows":
        mingw_path = r"C:\msys64\mingw64\bin"
        make_exe = os.path.join(mingw_path, "mingw32-make.exe")
        if not os.path.exists(make_exe):
            print("[ERROR] mingw32-make.exe not found. Install MSYS2 with MinGW.")
            return
        env["PATH"] = mingw_path + os.pathsep + env["PATH"]
        subprocess.run([make_exe, "clean"], cwd=wavelet_dir, env=env)
        subprocess.run([make_exe, "dll"], check=True, cwd=wavelet_dir, env=env)

    elif system == "Linux":
        subprocess.run(["make", "clean"], cwd=wavelet_dir)

        if shutil.which("x86_64-w64-mingw32-gcc"):
            try_make("dll", cwd=wavelet_dir)
        else:
            print("[INFO] mingw-w64 not found. Skipping .dll build.")

        if shutil.which("gcc"):
            try_make("so", cwd=wavelet_dir)
        else:
            print("[WARNING] gcc not found. Skipping .so build.")

        if shutil.which("clang"):
            try_make("dylib", cwd=wavelet_dir)
        else:
            print("[INFO] clang not found. Skipping .dylib build.")

    elif system == "Darwin":
        subprocess.run(["make", "clean"], cwd=wavelet_dir)
        try_make("dylib", cwd=wavelet_dir)

    else:
        print(f"[ERROR] Unsupported platform: {system}")
        return

    print("[INFO] Build process completed.")


if __name__ == "__main__":
    build_wavelet_library()
