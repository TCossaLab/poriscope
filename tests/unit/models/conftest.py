import logging
import pytest

@pytest.fixture
def main_model(tmp_path, monkeypatch):
    # Make platformdirs.user_data_dir() point to tmp_path
    monkeypatch.setattr(
        "poriscope.models.main_model.user_data_dir",
        lambda *a, **k: str(tmp_path),
        raising=False,
    )

    # Create expected Poriscope dirs
    (tmp_path / "Poriscope" / "session").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Poriscope" / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Poriscope" / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Poriscope" / "user_plugins").mkdir(parents=True, exist_ok=True)

    from poriscope.models.main_model import MainModel
    app_config = {
        "Parent Folder": str(tmp_path),
        "User Plugin Folder": str(tmp_path / "Poriscope" / "user_plugins"),
        "Log Level": logging.WARNING,
    }
    return MainModel(app_config)
