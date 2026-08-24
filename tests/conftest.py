"""Project-wide test fixtures.

Poriscope resolves its config, session and log directories through
``platformdirs.user_data_dir()``, so anything that builds a real ``MainModel``
writes into the developer's actual ``%LOCALAPPDATA%/Poriscope`` profile and can
overwrite their real saved session and tab-action history.

Every place that currently does so already redirects that call for itself -
``tests/e2e/conftest.py``'s autouse ``sandbox_appdata`` covers the whole e2e
tree, and ``tests/unit/models/conftest.py``'s ``main_model`` fixture covers the
model tests. This fixture makes the redirection an inherited default rather
than a convention each area has to remember, so a test added anywhere else
cannot reach real user state. Both existing fixtures still run after this one
and deliberately override it with their own roots, because their assertions
depend on the specific layout they build.
"""

import sys

import pytest


@pytest.fixture(autouse=True)
def sandbox_user_data_dir(monkeypatch, tmp_path):
    """
    Point ``platformdirs.user_data_dir()`` at a per-test temporary directory.

    :param monkeypatch: pytest's monkeypatch fixture.
    :type monkeypatch: pytest.MonkeyPatch
    :param tmp_path: pytest's per-test temporary directory.
    :type tmp_path: pathlib.Path
    """
    appdata_root = tmp_path / "appdata"
    for subdir in ("session", "config", "logs", "user_plugins"):
        (appdata_root / "Poriscope" / subdir).mkdir(parents=True, exist_ok=True)

    def _fake_user_data_dir(*args, **kwargs):
        return str(appdata_root)

    monkeypatch.setattr(
        "poriscope.models.main_model.user_data_dir",
        _fake_user_data_dir,
        raising=True,
    )
    # main_app is the other consumer, but no test imports it today and patching
    # it by string would force that import - and QApplication construction -
    # into every test. Only redirect it if something has already pulled it in.
    if "poriscope.main_app" in sys.modules:
        monkeypatch.setattr(
            "poriscope.main_app.user_data_dir",
            _fake_user_data_dir,
            raising=True,
        )
