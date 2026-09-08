import logging

from poriscope.constants import __VERSION__

__all__ = ["__VERSION__"]

# Re-export exposed aliases after install
try:
    from .exposed import *  # noqa: F403
except ImportError as exc:
    # Kept non-fatal so `pip install` cannot break on a half-installed dependency set,
    # but a partial import must never be silent again: swallowing this is what turned a
    # one-line "libEGL.so.1: cannot open shared object file" failure in the docs CI into
    # several hundred unrelated Sphinx warnings, because the process was left with half
    # of PySide6 imported and the rest missing.
    logging.getLogger(__name__).warning(
        "poriscope.exposed only partially imported - some re-exports are missing: %s",
        exc,
    )
