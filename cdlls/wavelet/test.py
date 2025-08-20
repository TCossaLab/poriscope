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


import ctypes
import os

import matplotlib.pyplot as pl
import numpy as np
from numpy.ctypeslib import ndpointer

# Get the absolute path to wavelet.dll
dll_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "cdlls", "wavelet", "dist", "wavelet.dll"
    )
)

# Optionally register the DLL directory (Python 3.8+)
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(os.path.dirname(dll_path))

# Load the DLL
wavelib = ctypes.cdll.LoadLibrary(dll_path)
fun = wavelib.filter_signal_wt
fun.restype = None
fun.argtypes = [
    ndpointer(ctypes.c_double, flags="C_CONTIGUOUS"),
    ctypes.c_int,
    ctypes.c_char_p,
]

wname = "bior1.5".encode("utf-8")
data = np.random.rand(10000) - 0.5
padlen = 100
data = np.pad(data, padlen, mode="edge")
data[int(len(data) / 2 - len(data) / 5) : int(len(data) / 2 + len(data) / 5)] += 1
fun(data, len(data), wname)
pl.plot(data[padlen:-padlen])
pl.show()
