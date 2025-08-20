#!/usr/bin/env python3

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
import sys


def run_script(path):
    print(f"[HOOK] Running: {os.path.basename(path)}")
    result = subprocess.run([sys.executable, path], cwd=os.path.dirname(path))
    if result.returncode != 0:
        print(
            f"[ERROR] {os.path.basename(path)} failed with return code {result.returncode}."
        )
        sys.exit(result.returncode)
    else:
        print(f"[HOOK] {os.path.basename(path)} completed successfully.")


def main():
    repo_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    build_script = os.path.join(repo_root, "scripts", "build_wavelet.py")
    full_setup_script = os.path.join(repo_root, "scripts", "full_setup_and_build.py")
    mingw_make = os.path.join(r"C:\msys64\mingw64\bin", "mingw32-make.exe")

    if os.path.exists(mingw_make):
        run_script(build_script)
    else:
        print("[HOOK] mingw32-make.exe not found, running full setup instead...")
        run_script(full_setup_script)


if __name__ == "__main__":
    main()
