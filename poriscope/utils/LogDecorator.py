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
import inspect
import logging
from typing import Any, Callable, Generator, Optional, TypeVar, Union, cast, overload

# Bound to the decorated callable so that these decorators hand back the *same*
# type they were given. Declaring them ``-> Callable`` instead erases the
# signature of every method they wrap, leaving all call sites into it unchecked.
F = TypeVar("F", bound=Callable[..., Any])

#: The attribute :py:func:`register_action` sets on a method to carry its declared name.
ACTION_NAME_ATTR = "_action_name"

#: The declared name of every tab's reset action. Undo finds resets by it, so a tab's
#: ``_reset_actions`` is declared with this constant rather than a literal.
RESET_ACTION = "reset"


@overload
def log(_func: F, *, logger: logging.Logger) -> F: ...


@overload
def log(_func: None = None, *, logger: logging.Logger) -> Callable[[F], F]: ...


def log(
    _func: Optional[F] = None,
    *,
    logger: logging.Logger,
) -> Union[F, Callable[[F], F]]:
    """
    @log(logger): A decorator that logs the entry and exit of a function. Exceptions raised by the decorated function are not caught or logged here; they propagate to the caller unchanged.

    The decorator logs, and only when the decorated module's logger is enabled
    for DEBUG:
    - Entry into the function, qualified by its class name, with the arguments it was called with.
    - The result it returned.

    Nothing is logged at any other level. The check is ``logger.isEnabledFor``,
    so a single module can be turned up to DEBUG on its own without raising the
    level of the whole application, and nothing is formatted until it passes.


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

    :param _func: The function to be decorated. If None, the decorator is returned.
    :type _func: Optional[F]
    :param logger: The logger instance used for logging.
    :type logger: logging.Logger
    :return: The decorated function or the decorator itself.
    :rtype: Union[F, Callable[[F], F]]
    """

    def decorator_log(func: F) -> F:
        def log_call(args: tuple, kwargs: dict) -> str:
            name = getattr(func, "__name__", "?")
            try:
                # The level is consulted before anything is built. This runs on
                # every call into all ~977 decorated methods, so the qualified
                # name and the argument reprs must not be paid for when debug
                # logging is off. `name` is only ever read back by log_return,
                # which is gated the same way, so leaving it unqualified here
                # costs nothing.
                if logger.isEnabledFor(logging.DEBUG):
                    self = args[0]
                    name = f"{self.__class__.__name__}.{func.__name__}"
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
            return name

        def log_return(name: str, result: Any) -> None:
            try:
                if logger.isEnabledFor(logging.DEBUG):
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

        if inspect.isgeneratorfunction(func):
            # calling a generator function only ever constructs the generator
            # object without running any of its body; the entry/exit logging
            # below must instead wrap iteration of the delegated generator via
            # `yield from`, which transparently forwards send()/throw()/close()
            # to it and lets exceptions raised during iteration propagate here.
            @functools.wraps(func)
            def generator_wrapper(
                *args: Any, **kwargs: Any
            ) -> Generator[Any, Any, Any]:
                name = log_call(args, kwargs)
                result = yield from func(*args, **kwargs)
                log_return(name, result)
                return result

            return cast(F, generator_wrapper)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = log_call(args, kwargs)
            result = func(*args, **kwargs)
            log_return(name, result)
            return result

        return cast(F, wrapper)

    if _func is None:
        return decorator_log
    else:
        return decorator_log(_func)


def register_action(name: str) -> Callable[[F], F]:
    """
    @register_action(name): record each call of the decorated method as a named action that a saved history can replay.

    The entry is ``{"action": name, "args": args, "kwargs": kwargs}``, handed to
    ``self.record_action`` once the body has returned, so an action called inside
    another is recorded before it. The name is the declared name, not the Python method
    name, so the method can be renamed or moved without breaking a saved history. It is
    also stored on the wrapper under :py:data:`ACTION_NAME_ATTR`, which is how
    :py:meth:`MetaController.action_registry` finds the method again. A failure to
    record is logged at INFO and never breaks the call; an object with no
    ``record_action`` is simply not recorded.

    :param name: the action's declared name, unique within one tab
    :type name: str
    :return: the decorator
    :rtype: Callable[[F], F]
    """

    # Decorators always nest, because they require a closure.
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(
            self: Any, *args: Any, **kwargs: Any
        ) -> Any:  # self is the first argument for instance methods
            result = func(self, *args, **kwargs)

            record = getattr(self, "record_action", None)
            if callable(record):
                entry = {"action": name, "args": args, "kwargs": kwargs}
                try:
                    record(entry)
                except Exception as e:
                    self.logger.info(f"Unable to log tab action: {str(e)}")
            return result

        setattr(wrapper, ACTION_NAME_ATTR, name)
        return cast(F, wrapper)

    return decorator
