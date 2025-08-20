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
import shutil
import subprocess
import sys


def safe_rmtree(path):  # Cross-platform
    if os.path.exists(path):
        print(f"Removing {path}")
        shutil.rmtree(path)


def main():
    repo_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    os.chdir(repo_root)

    print("Git merge detected. Cleaning and rebuilding docs...")

    # Clean build and autodoc directories
    build_dir = os.path.join(repo_root, "docs", "build")
    autodoc_dir = os.path.join(repo_root, "docs", "source", "autodoc")

    safe_rmtree(build_dir)
    safe_rmtree(autodoc_dir)

    # Regenerate .rst files
    print("Regenerating autodoc .rst files...")
    subprocess.run([sys.executable, "scripts/generate_all_autodoc_rst.py"], check=True)

    # Build docs
    print("Building Sphinx docs...")
    subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", "docs/source", "docs/build"],
        check=True,
    )

    # Open index.html
    index_path = os.path.join(repo_root, "docs", "build", "index.html")
    if sys.platform.startswith("win"):
        os.startfile(index_path)
    elif sys.platform.startswith("darwin"):
        subprocess.run(["open", index_path])
    else:
        subprocess.run(["xdg-open", index_path])


if __name__ == "__main__":
    main()
