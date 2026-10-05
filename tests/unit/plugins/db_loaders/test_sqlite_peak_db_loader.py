"""
Tests for ``SQLitePeakDBLoader.get_plot_features``'s nothing-to-plot branches.

The loader is built with ``object.__new__`` and its database collaborators are
replaced by stand-ins returning what the real ones return in each case: the column
lookups a list of names, ``validate_filter_query`` a ``(valid, debug)`` pair, and
``query_database_directly`` a DataFrame, empty when nothing matched, or ``None``
when the query could not be run - a failure it has already logged itself.
"""

import logging
from typing import Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLitePeakDBLoader import SQLitePeakDBLoader

NOTHING = (None, None, None, None, None, None)


def _loader(result: Optional[pd.DataFrame]) -> SQLitePeakDBLoader:
    loader = object.__new__(SQLitePeakDBLoader)
    loader.logger = MagicMock(spec=logging.Logger)
    loader.get_column_names_by_table = MagicMock(return_value=[])
    loader.validate_filter_query = MagicMock(return_value=(True, None))
    loader.query_database_directly = MagicMock(return_value=result)
    return loader


def _logged_empty_dataframe(loader: SQLitePeakDBLoader) -> bool:
    return any(
        "Empty dataframe" in str(call.args[0])
        for call in loader.logger.info.call_args_list
    )


def test_an_empty_result_is_reported_as_nothing_to_plot() -> None:
    loader = _loader(pd.DataFrame())

    assert loader.get_plot_features(1, 0, 0) == NOTHING
    assert _logged_empty_dataframe(loader)


def test_a_failed_query_is_not_reported_as_an_empty_result() -> None:
    """
    A query that could not run returns nothing to plot without claiming it was empty.

    ``query_database_directly`` has already logged the failure at its own level, so
    reporting "Empty dataframe" here as well told the log something untrue.
    """
    loader = _loader(None)

    assert loader.get_plot_features(1, 0, 0) == NOTHING
    assert not _logged_empty_dataframe(loader)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
