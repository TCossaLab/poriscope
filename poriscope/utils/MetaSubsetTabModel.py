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
from typing import Dict, Generator, List, Mapping, Optional, Sequence

import pandas as pd

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


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
    """

    logger = logging.getLogger(__name__)

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
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
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
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
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

        :param path: the file to read
        :type path: str
        :return: the filters the file holds, keyed by name
        :rtype: Dict[str, str]
        :raises ValueError: if the file does not hold a JSON object
        """
        with open(path, "r") as handle:
            filters = json.load(handle)

        if not isinstance(filters, dict):
            raise ValueError(f"expected a dictionary, got {type(filters).__name__}")
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
