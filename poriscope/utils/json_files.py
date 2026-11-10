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
# Kyle Briggs
# Alejandra Carolina González González

"""
Writing a JSON file the user keeps, so that a failed write never damages the one already there.

Shared by every model that saves such a file - the session and a tab's saved actions - so
they all get the same protection.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Union

#: How many times a write retries a rename Windows briefly refuses.
REPLACE_ATTEMPTS = 5


def write_json_atomically(
    data: Any, save_file: Union[str, Path], attempts: int = REPLACE_ATTEMPTS
) -> None:
    """
    Write ``data`` as JSON so that a failure leaves the previous file untouched.

    It is written to a temporary file beside ``save_file`` and moved over it only
    once complete. Opening the target for writing first truncated it, so a value
    that could not be serialised left the session file cut off mid-entry.

    The move is retried briefly on ``PermissionError``: on Windows a file that was
    just written is held open for a moment by scanners such as Defender, and the
    rename is refused - 14 of 300 rapid saves in the temp folder - which would
    otherwise be reported as autosave having stopped.

    :param data: the JSON-serialisable content
    :type data: Any
    :param save_file: the file to write
    :type save_file: Union[str, Path]
    :param attempts: how many times to try the rename before giving up
    :type attempts: int
    :raises PermissionError: if the rename is still refused after every retry
    :raises Exception: whatever writing or serialising raised; the temporary file
        is removed first
    """
    target = Path(save_file)
    temporary = target.with_name(target.name + ".tmp")
    try:
        with open(temporary, "w") as jf:
            json.dump(data, jf, indent=4)
        for attempt in range(attempts):
            try:
                os.replace(temporary, target)
                break
            except PermissionError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
