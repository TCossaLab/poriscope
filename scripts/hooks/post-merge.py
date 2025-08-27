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
    print(f"Running {path} ...")

    if path.endswith(".py"):
        command = [sys.executable, path]
    elif path.endswith(".sh"):
        command = ["bash", path]
    else:
        print(f"Unsupported file type for hook: {path}")
        return

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {path}: {e}")
        sys.exit(1)


def main():
    # Move to repo root
    repo_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    os.chdir(repo_root)

    # List of post-merge sub-hooks to run
    hook_scripts = [
        "scripts/hooks/post-merge-update_requirements.py",
        "scripts/hooks/post-merge-run_autodoc_pipeline.py",
        "scripts/hooks/post-merge-create_wavelet_dll.py",
        # Add more hooks here (can be .py or .sh)
    ]

    for script in hook_scripts:
        run_script(script)


if __name__ == "__main__":
    main()
