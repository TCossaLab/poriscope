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


def build_wavelet_dll():
    root_dir = os.path.abspath(os.path.dirname(__file__))
    wavelet_dir = os.path.join(root_dir, "..", "cdlls", "wavelet")
    build_dirs = ["build", os.path.join("build", "obj"), "dist"]

    for d in build_dirs:
        os.makedirs(os.path.join(wavelet_dir, d), exist_ok=True)

    print(f"Building in: {wavelet_dir}")
    mingw_path = r"C:\msys64\mingw64\bin"
    env = os.environ.copy()
    env["PATH"] = mingw_path + os.pathsep + env["PATH"]

    try:
        subprocess.run(
            ["mingw32-make.exe", "all"], check=True, cwd=wavelet_dir, env=env
        )
        print("wavelet.dll built successfully.")
    except subprocess.CalledProcessError as e:
        print("Failed to build wavelet.dll. Check your makefile and environment.")
        print("Error:", e)


if __name__ == "__main__":
    build_wavelet_dll()
