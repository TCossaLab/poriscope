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


def inherit_docstrings(cls):
    """Class decorator: copy docstrings from base classes if missing.

    If a method has no docstring, this searches the MRO (excluding self)
    for the first method with the same name that *does* have a docstring,
    and copies it.
    """
    for name, func in cls.__dict__.items():
        if not callable(func):
            continue
        if func.__doc__:
            continue
        for parent in cls.__mro__[1:]:  # Skip cls itself
            parent_func = getattr(parent, name, None)
            if not parent_func:
                continue
            doc = getattr(parent_func, "__doc__", None)
            if doc:
                func.__doc__ = doc
                break
    return cls
