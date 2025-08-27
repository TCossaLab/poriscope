from poriscope.constants import __VERSION__

__all__ = ["__VERSION__"]

# Re-export exposed aliases after install
try:
    from .exposed import *  # noqa: F403
except ImportError:
    # Silent fail during `pip install` when dependencies aren't ready
    pass
