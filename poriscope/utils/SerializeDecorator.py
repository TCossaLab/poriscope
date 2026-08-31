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
from typing import Any, Callable, Generator, TypeVar, cast

# Bound to the decorated callable so the decorator hands back the same type it was
# given, rather than erasing the signature of every call site into it.
F = TypeVar("F", bound=Callable[..., Any])


def serialize_channels(_func: F) -> F:
    """
    Serialize a data plugin's generator method across channels, if that plugin declares it must be.

    Applied to the generator methods that the channel-management system drives, one generator per channel. The decorated method runs inside :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.serialize_channel_operations`, which takes *that plugin instance's* lock when :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.force_serial_channel_operations` returns ``True`` and does nothing otherwise.

    The lock is held for the **whole run** of the generator, not per iteration: the wrapper suspends at ``yield from`` while still inside the ``with`` block, so the lock is acquired on the first advance and released when the generator is exhausted, closed, or raises. That is the same span the worker used to lock, so serialization behaviour is unchanged - what changes is *whose* lock it is.

    This is a decorator rather than a public/private method split for two reasons: the split moves nothing but forces the public method to drop its ``:raises:`` documentation (pydoclint DOC502 - a thin ``yield from`` wrapper raises nothing itself), and ``functools.wraps`` keeps ``__wrapped__`` intact so ``inspect.signature`` still resolves the real signature, which the signal dispatcher in ``MainController`` depends on.

    Note the nested wrapper: decorators require a closure, the same reason ``LogDecorator`` is the standing exception to this codebase's no-nested-functions rule.

    Example, applied outermost so the lock brackets the logged operation:

    .. code-block:: python

      @serialize_channels
      @log(logger=logger)
      def commit_events(self, channel: int) -> Generator[float, Optional[bool], None]:
          ...

    :param _func: The generator method to guard.
    :type _func: F
    :return: The method, wrapped so that it runs under the plugin's serialization guard.
    :rtype: F
    :raises TypeError: If applied to something that is not a generator function, since the wrapper delegates with ``yield from``.
    """
    if not inspect.isgeneratorfunction(_func):
        raise TypeError(
            f"serialize_channels can only decorate a generator function; "
            f"{getattr(_func, '__name__', _func)} is not one"
        )

    @functools.wraps(_func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Generator[Any, Any, Any]:
        with self.serialize_channel_operations():
            result = yield from _func(self, *args, **kwargs)
        return result

    return cast(F, wrapper)
