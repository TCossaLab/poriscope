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


def install_pre_commit(repo_root: str) -> None:
    print("Installing pre-commit...")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pre-commit"], check=True
        )
    except subprocess.CalledProcessError:
        print("Failed to install pre-commit")
        return

    # Uninstall any existing hook to avoid config path issues
    subprocess.run(["pre-commit", "uninstall"], cwd=repo_root)

    # Install pre-commit with default root config
    subprocess.run(["pre-commit", "install"], cwd=repo_root)
    print("pre-commit installed and Git hook activated")


def install_post_merge_hook(repo_root: str) -> None:
    print("Installing Git hook: post-merge")

    # Define the source path of the post-merge hook script
    hook_src = os.path.join(repo_root, "scripts", "hooks", "post-merge.py")
    # Define the destination path for the Git hook (inside the .git/hooks directory)
    hook_dst = os.path.join(repo_root, ".git", "hooks", "post-merge")

    # Check if the source hook script exists
    if not os.path.exists(hook_src):
        print("Hook source not found:", hook_src)
        return

    # Copy the hook script to the Git hooks directory
    shutil.copy(hook_src, hook_dst)
    # Ensure the copied hook script is executable
    os.chmod(hook_dst, 0o755)
    print("post-merge hook installed")


def main() -> None:
    repo_root: str = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    install_post_merge_hook(repo_root)
    install_pre_commit(repo_root)


if __name__ == "__main__":
    main()
