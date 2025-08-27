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

import functools
import logging

from PySide6.QtCore import Signal


def log(_func=None, *, logger, debug_only=False):
    """
    @log(logger): A decorator that logs the entry, exit, and exceptions of a function.

    :param _func: The function to be decorated. If None, the decorator is returned.
    :type _func: callable, optional
    :param logger: The logger instance used for logging.
    :type logger: logging.Logger
    :param debug_only: a flag to indicate whether the decorator is only to run in debug mode, default False
    :type debug_only: bool
    :return: The decorated function or the decorator itself.
    :rtype: callable

    The decorator logs:
    - Entry into the function with the function name.
    - Arguments passed to the function if the logging level is DEBUG.
    - The result returned by the function if the logging level is DEBUG.
    - Exit from the function with the function name.


    Example usage:

    At the level of the class definition, define a logger exactly as follows:

    .. code-block:: python

      import logging
      from poriscope.utils.LogDecotrator import log
      class SomePlugin(MetaPlugin):
          logger = logging.getLogger(__name__)
          @log(logger=logger)
          def __init__(self):
              ...

    Once this is done, you can decorate any member functions you want logged to the logfile like so:

    .. code-block:: python

      @log(logger=logger)
      def my_function(self, ...):
          pass

    All member methods of plugins should be decorated with this logger. Calls to the logger inside functions proceed normally.

    .. code-block:: python

      @log(logger=logger)
      def my_function(self, ...):
          self.logger.info('This message is informational')

    """

    def decorator_log(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                self = args[0]
                name = f"{self.__class__.__name__}.{func.__name__}"
                if logger.root.level == logging.DEBUG:
                    args_repr = [repr(a) for a in args]
                    kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                    signature = ", ".join(args_repr + kwargs_repr)
                    logger.debug(f"{name} called with args ({signature})")
            except Exception as e:
                if (
                    not hasattr(logger.root, "ignore_exceptions")
                    or logger.root.ignore_exceptions is False
                ):
                    logger.exception(
                        f"Ignoring exception raised by logger: {str(e)}. No more logger exceptions will be shown, logs from this point may be corrupt or incomplete."
                    )
                    setattr(logger.root, "ignore_exceptions", True)
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                raise e
            else:
                try:
                    if logger.root.level == logging.DEBUG:
                        logger.debug(f"{name} returned ({result})")
                except Exception as e:
                    if (
                        not hasattr(logger.root, "ignore_exceptions")
                        or logger.root.ignore_exceptions is False
                    ):
                        logger.exception(
                            f"Ignoring exception raised by logger: {str(e)}. No more logger exceptions will be shown, logs from this point may be corrupt or incomplete."
                        )
                        setattr(logger.root, "ignore_exceptions", True)
            return result

        return wrapper

    if _func is None:
        return decorator_log
    else:
        return decorator_log(_func)


def register_action():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(
            self, *args, **kwargs
        ):  # self is the first argument for instance methods
            result = func(self, *args, **kwargs)

            signal_attr = getattr(self, "update_tab_action_history", None)
            if signal_attr and isinstance(signal_attr, Signal):
                history = {"function": func.__name__, "args": args, "kwargs": kwargs}
                try:
                    signal_attr.emit(history, False)
                except Exception as e:
                    self.logger.info(f"Unable to log tab action: {str(e)}")
            return result

        return wrapper

    return decorator
