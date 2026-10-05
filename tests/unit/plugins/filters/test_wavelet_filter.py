"""
Tests for the wavelet library ``WaveletFilter`` ships and how it finds one.

The library is built by CI and committed under ``poriscope/cdlls/wavelet/dist/``, and
the wheel ships whatever is there. Nothing checked what those files are, so a Linux
ELF shipped for years under the macOS name ``wavelet.dylib`` and could never load.
"""

import platform
from pathlib import Path

import pytest

from poriscope.plugins.filters.WaveletFilter import WaveletFilter

DIST = Path(__file__).resolve().parents[4] / "poriscope" / "cdlls" / "wavelet" / "dist"

#: The file format each shipped library must be, by the bytes it starts with.
MAGIC = {
    "wavelet.dll": b"MZ",  # a Windows PE image
    "wavelet.so": b"\x7fELF",  # a Linux ELF shared object
}


@pytest.mark.parametrize(("name", "magic"), sorted(MAGIC.items()))
def test_each_shipped_library_is_the_format_its_platform_loads(
    name: str, magic: bytes
) -> None:
    """A library named for a platform is that platform's binary format."""
    with open(DIST / name, "rb") as f:
        assert f.read(len(magic)) == magic


def test_no_library_is_shipped_for_an_unbuilt_platform() -> None:
    """
    Only the libraries CI builds natively are shipped.

    There is no macOS build, so there is no ``.dylib``: one cross-built on Linux is an
    ELF file that macOS cannot load.
    """
    shipped = sorted(p.name for p in DIST.iterdir() if p.name.startswith("wavelet"))
    assert shipped == sorted(MAGIC)


def test_macos_without_a_built_library_says_how_to_get_one(monkeypatch) -> None:
    """
    On macOS the filter reports the missing library and the override that fixes it.

    It used to find the shipped Linux ELF and fail inside ``dlopen`` with an error
    naming neither the cause nor the remedy.
    """
    monkeypatch.delenv("PORISCOPE_WAVELET_PATH", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    wavelet = object.__new__(WaveletFilter)

    with pytest.raises(FileNotFoundError, match="PORISCOPE_WAVELET_PATH"):
        wavelet._finalize_initialization()
