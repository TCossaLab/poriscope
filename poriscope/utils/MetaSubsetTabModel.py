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

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import pandas as pd

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel

#: One dataset on an overlaid figure: (loader, experiment, channel, filter SQL, filter name).
DatasetKey = Tuple[
    Optional[str], Optional[str], Optional[int], Optional[str], Optional[str]
]


class FigureKind(Enum):
    """What the figure holds, so the next overlay can tell whether it can add to it."""

    EMPTY_2D = "empty 2d"
    EMPTY_3D = "empty 3d"
    OVERLAY_2D = "overlay 2d"
    OVERLAY_3D = "overlay 3d"
    EVENT_GRID = "event grid"

    @classmethod
    def empty(cls, axis_type: str) -> "FigureKind":
        """
        The empty figure of one projection.

        :param axis_type: Either '2d' or '3d'
        :type axis_type: str
        :return: the empty kind of that projection
        :rtype: FigureKind
        """
        return cls.EMPTY_3D if axis_type == "3d" else cls.EMPTY_2D

    @classmethod
    def overlay(cls, axis_type: str) -> "FigureKind":
        """
        The overlaid figure of one projection.

        :param axis_type: Either '2d' or '3d'
        :type axis_type: str
        :return: the overlay kind of that projection
        :rtype: FigureKind
        """
        return cls.OVERLAY_3D if axis_type == "3d" else cls.OVERLAY_2D

    def accepts(self, axis_type: str) -> bool:
        """
        Can a plot of this projection be drawn onto this figure without clearing it?

        :param axis_type: Either '2d' or '3d', the projection the plot needs
        :type axis_type: str
        :return: True for an empty or overlaid figure of that projection
        :rtype: bool
        """
        return self in (FigureKind.empty(axis_type), FigureKind.overlay(axis_type))


@dataclass
class OverlayState:
    """
    What an overlaid figure holds, kept by the Model so the Controller decides from it.

    The options the figure was drawn with, the datasets on it, and what the accumulating
    plot types redraw each time one is added: each dataset's values and label, and the
    limits the datasets share. A reset replaces it with an empty one.

    :ivar figure: what the figure holds
    :ivar plot_type: the plot type drawn, or None on an empty figure
    :ivar columns: the columns drawn
    :ivar logs: the columns' log-scale flags
    :ivar bins: the bins list the figure was drawn with
    :ivar sizes: does bins refer to a bin width
    :ivar datasets: the datasets on the figure
    :ivar values: per accumulated dataset, newest last: its raw column for the
        histogram, density and categorical plots, or its (bin centres, counts) for the
        all-points histograms. Two shapes, not one: a single element type would be
        cleaner, and is a change of its own.
    :ivar labels: per accumulated dataset, its label, index-aligned with values
    :ivar hist_min: the shared lower limit, or None before the first dataset
    :ivar hist_max: the shared upper limit, or None before the first dataset
    """

    figure: FigureKind = FigureKind.EMPTY_2D
    plot_type: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    logs: List[bool] = field(default_factory=list)
    bins: Optional[List[Union[int, float]]] = None
    sizes: Optional[bool] = None
    datasets: Set[DatasetKey] = field(default_factory=set)
    values: List[Any] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    hist_min: Optional[float] = None
    hist_max: Optional[float] = None


class MetaSubsetTabModel(MetaModel):
    """
    Shared base for the Models of the two database-backed analysis tabs.

    ``MetadataModel`` and ``ProteinModel`` both back a tab whose data comes from a
    ``MetaDatabaseLoader``: the user picks an experiment and channels, writes a subset
    filter, and plots the rows that come back. This base holds the half of that work
    that is the same in both, so there is one copy to fix - the events-table lookups
    behind an event plot, and the subset filter file's JSON.

    It is the Model half of the ``MetaSubsetTab*`` family, alongside
    ``MetaSubsetTabController``, ``MetaSubsetTabView`` and ``MetaSubsetTabControls``.
    Its methods live here rather than on ``MetaModel`` because the three analysis tabs
    that read a timeseries rather than a database - RawData, EventAnalysis and
    Clustering - have no events table to query and no filter file to write, and
    inheriting the API would say they did.

    A subclass still owes ``MetaModel`` its ``_init``.

    :ivar logger: the module logger the shared methods below log under
    :ivar overlay: what the overlaid figure holds
    """

    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs: Any) -> None:
        """
        Start with an empty 2-D figure, before the subclass's ``_init`` runs.

        :param \\**kwargs: Additional parameters to set as attributes on the instance
        :type \\**kwargs: Any
        """
        self.overlay = OverlayState()
        super().__init__(**kwargs)

    @log(logger=logger)
    def clear_overlay(self, axis_type: str) -> None:
        """
        Forget what the figure held: it is now an empty figure of this projection.

        :param axis_type: Either '2d' or '3d', the projection of the fresh axes
        :type axis_type: str
        """
        self.overlay = OverlayState(figure=FigureKind.empty(axis_type))

    @log(logger=logger)
    def clear_overlay_for_event_grid(self) -> None:
        """
        Forget what the figure held: it now holds a grid of events, which no overlay adds to.
        """
        self.overlay = OverlayState(figure=FigureKind.EVENT_GRID)

    @log(logger=logger)
    def add_overlay_dataset(
        self,
        key: DatasetKey,
        figure: FigureKind,
        plot_type: str,
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        columns: List[str],
        logs: List[bool],
    ) -> None:
        """
        Note one dataset as drawn, with the options the figure is now drawn with.

        :param key: the dataset drawn
        :type key: DatasetKey
        :param figure: what the figure holds now
        :type figure: FigureKind
        :param plot_type: the plot type drawn
        :type plot_type: str
        :param bins: the bins list the figure was drawn with
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param columns: the columns drawn
        :type columns: List[str]
        :param logs: the columns' log-scale flags
        :type logs: List[bool]
        """
        state = self.overlay
        state.figure = figure
        state.plot_type = plot_type
        state.bins = bins
        state.sizes = sizes
        state.columns = columns
        state.logs = logs
        state.datasets.add(key)

    @log(logger=logger)
    def accumulate_overlay_values(
        self,
        values: Any,
        label: str,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> List[str]:
        """
        Add the newest dataset to what the overlaid figure redraws, once it is drawable.

        :param values: the newest dataset's values, in the shape its plot type keeps
        :type values: Any
        :param label: the newest dataset's label
        :type label: str
        :param hist_min: the shared lower limit, widened by this dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit, widened by this dataset
        :type hist_max: Optional[float]
        :return: every accumulated dataset's label, newest last
        :rtype: List[str]
        """
        state = self.overlay
        state.values.append(values)
        state.labels.append(label)
        state.hist_min = hist_min
        state.hist_max = hist_max
        return list(state.labels)

    @log(logger=logger)
    def resolve_event_ids(
        self,
        loader: str,
        event_ids: Sequence[int],
        exp_id: Optional[int],
        channel: Optional[int],
    ) -> Optional[pd.DataFrame]:
        """
        Look up the database ids of these ``event_id`` values, within scope.

        **The scope is why this query exists at all.** ``event_id`` is unique only
        within an experiment and channel, so an unscoped match returns whichever
        channel's row happens to share the number. The caller stops rather than
        widening the query when it cannot resolve an experiment; that guard stays
        there, because it is the half that has something to tell the user.

        The projection is ``id`` alone. An event plot's requested order is restored
        in the View from the ``event_id`` the loader itself reports on each event, so
        naming the column here as well buys nothing.

        ``DECISIONS.md`` (2026-08-25) accepts the f-string interpolation: the database
        is a local file owned by the user running the app.

        :param loader: the database loader's plugin key
        :type loader: str
        :param event_ids: the event_id values to resolve
        :type event_ids: Sequence[int]
        :param exp_id: the experiment's database id, or None to leave it out of scope
        :type exp_id: Optional[int]
        :param channel: the channel to scope to, or None for all channels
        :type channel: Optional[int]
        :return: the matching rows, or None if the loader had nothing to say
        :rtype: Optional[pd.DataFrame]
        """
        id_list = ",".join(str(eid) for eid in event_ids)
        where_parts = [f"event_id IN ({id_list})"]

        if exp_id is not None:
            where_parts.append(f"experiment_id = {exp_id}")
        if channel is not None:
            where_parts.append(f"channel_id = {channel}")

        query = f"SELECT id FROM events WHERE {' AND '.join(where_parts)}"
        result: Optional[pd.DataFrame] = self.call(
            "MetaDatabaseLoader", loader, "query_database_directly", query
        )
        return result

    @log(logger=logger)
    def load_events_by_id(
        self,
        loader: str,
        db_ids: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
    ) -> Optional[Generator]:
        """
        Load exactly the rows named by their database ids.

        The ``e.id IN (...)`` clause is a WHERE-clause body, which is what
        ``load_event_data`` takes - it splices it in after its own ``WHERE``, so a
        complete ``SELECT`` cannot be passed here.

        :param loader: the database loader's plugin key
        :type loader: str
        :param db_ids: the comma-separated primary keys to load
        :type db_ids: str
        :param experiments_and_channels: the scope handed on to the loader
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a generator over the matching events, or None
        :rtype: Optional[Generator]
        """
        generator: Optional[Generator] = self.call(
            "MetaDatabaseLoader",
            loader,
            "load_event_data",
            f"e.id IN ({db_ids})",
            experiments_and_channels,
        )
        return generator

    @log(logger=logger)
    def load_filters(self, path: str) -> Dict[str, str]:
        """
        Read a saved set of subset filters back off disk.

        The file is a plain JSON object of filter name to filter text, which is what
        :meth:`save_filters` writes. Anything else is refused rather than half
        accepted: a list or a scalar would iterate into something, and the caller
        would be left holding filters it never asked for.

        **Every value has to be a string, and that check is load-bearing.** A saved
        session is a JSON object too, so the container check alone let one through,
        and its entries then split two ways: a value that is falsy - an empty dict,
        ``null`` - builds a query with no ``WHERE`` clause at all, which validates
        cleanly and commits as ``<name>_assisted`` with no body, while a non-empty
        one raises ``TypeError`` out of the query builder and raises a modal. Half
        the file arrives as filters nobody wrote and half as dialogs, which is
        exactly the outcome the all-or-nothing rule exists to prevent. An empty
        *string* stays legal, because the add-filter dialog requires a name and not
        a body, so a file this application wrote can contain one.

        :param path: the file to read
        :type path: str
        :return: the filters the file holds, keyed by name
        :rtype: Dict[str, str]
        :raises ValueError: if the file does not hold a JSON object of filter text
        """
        with open(path, "r") as handle:
            filters = json.load(handle)

        if not isinstance(filters, dict):
            raise ValueError(f"expected a dictionary, got {type(filters).__name__}")

        for name, text in filters.items():
            if not isinstance(text, str):
                raise ValueError(
                    f"{name!r} holds a {type(text).__name__} rather than filter text, "
                    "so this is not a subset filter file"
                )
        return filters

    @log(logger=logger)
    def save_filters(self, path: str, filters: Mapping[str, str]) -> None:
        """
        Write a set of subset filters to disk as JSON.

        Indented, because the file is meant to be readable and hand-editable - a
        filter is a WHERE clause somebody wrote.

        :param path: the file to write
        :type path: str
        :param filters: the filters to write, keyed by name
        :type filters: Mapping[str, str]
        :return: None
        :rtype: None
        """
        with open(path, "w") as handle:
            json.dump(dict(filters), handle, indent=4)
