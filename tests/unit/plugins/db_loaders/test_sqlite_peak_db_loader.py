"""
Tests for ``SQLitePeakDBLoader.get_plot_features``'s nothing-to-plot branches.

The loader is built with ``object.__new__`` and its database collaborators are
replaced by stand-ins returning what the real ones return in each case: the column
lookups a list of names, ``validate_filter_query`` a ``(valid, debug)`` pair, and
``query_database_directly`` a DataFrame, empty when nothing matched; it raises
when the query could not be run.
"""

import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLitePeakDBLoader import SQLitePeakDBLoader

NOTHING = (None, None, None, None, None, None)


def _loader(result: pd.DataFrame) -> SQLitePeakDBLoader:
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


def test_a_failed_query_is_raised_not_reported_as_an_empty_result() -> None:
    """
    A query that could not run raises, for the Metadata tab to report per event.

    Answering "nothing to plot" would read as an event with no features.
    """
    loader = _loader(pd.DataFrame())
    loader.query_database_directly.side_effect = ValueError("no such column: nope")

    with pytest.raises(ValueError, match="no such column: nope"):
        loader.get_plot_features(1, 0, 0)
    assert not _logged_empty_dataframe(loader)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
