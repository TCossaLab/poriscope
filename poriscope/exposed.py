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

# ----------------------
# --- Plugins ---
# ----------------------

# --- Data Readers ---
from poriscope.plugins.datareaders.ABF2Reader import ABF2Reader
from poriscope.plugins.datareaders.BinaryReader1X import BinaryReader1X
from poriscope.plugins.datareaders.ChimeraReader20240101 import ChimeraReader20240101
from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.datareaders.ChimeraReaderVC100 import ChimeraReaderVC100
from poriscope.plugins.datareaders.SingleBinaryDecoder import SingleBinaryDecoder

# --- Data Writers ---
from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter

# --- DB Loaders ---
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader

# --- DB Writers ---
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter

# --- Event Finders ---
from poriscope.plugins.eventfinders.BoundedBlockageFinder import BoundedBlockageFinder
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder

# --- Event Fitters ---
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventfitters.IntraCUSUM import IntraCUSUM
from poriscope.plugins.eventfitters.NanoTrees import NanoTrees
from poriscope.plugins.eventfitters.PeakFinder import PeakFinder

# --- Event Loaders ---
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader

# --- Filters ---
from poriscope.plugins.filters.BesselFilter import BesselFilter
from poriscope.plugins.filters.WaveletFilter import WaveletFilter

# --- Base Classes ---
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.utils.BaseValidator import BaseValidator

# --- Core Utilities ---
from poriscope.utils.EventWorker import Worker

# --- Meta Interfaces ---
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaFilter import MetaFilter
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaReader import MetaReader
from poriscope.utils.MetaView import MetaView
from poriscope.utils.MetaWriter import MetaWriter
from poriscope.utils.QObjectABCMeta import QObjectABCMeta

# --- Qt Utilities ---
from poriscope.utils.QtHandler import QtHandler
from poriscope.utils.QWidgetABCMeta import QWidgetABCMeta

# ----------------------
# --- Metaclasses ---
# ----------------------


# from poriscope.utils.JsonDefaultSerializer import JsonDefaultSerializer
# from poriscope.utils.LogDecorator import LogDecorator


__all__ = [
    # --- Data Readers ---
    "ABF2Reader",
    "BinaryReader1X",
    "ChimeraReader20240101",
    "ChimeraReader20240501",
    "ChimeraReaderVC100",
    "SingleBinaryDecoder",
    # --- Data Writers ---
    "SQLiteEventWriter",
    # --- DB Writers ---
    "SQLiteDBWriter",
    # --- DB Loaders ---
    "SQLiteDBLoader",
    # --- Event Finders ---
    "BoundedBlockageFinder",
    "ClassicBlockageFinder",
    # --- Event Fitters ---
    "CUSUM",
    "IntraCUSUM",
    "NanoTrees",
    "PeakFinder",
    # --- Event Loaders ---
    "SQLiteEventLoader",
    # --- Filters ---
    "BesselFilter",
    "WaveletFilter",
    # --- Meta Interfaces ---
    "MetaController",
    "MetaDatabaseLoader",
    "MetaDatabaseWriter",
    "MetaEventFinder",
    "MetaEventFitter",
    "MetaEventLoader",
    "MetaFilter",
    "MetaModel",
    "MetaReader",
    "MetaView",
    "MetaWriter",
    # --- Base Classes ---
    "BaseDataPlugin",
    "BaseLineEdit",
    "BaseValidator",
    # --- Qt Utilities ---
    "QtHandler",
    "QWidgetABCMeta",
    "QObjectABCMeta",
    # --- Core Utilities ---
    "Worker",
]
