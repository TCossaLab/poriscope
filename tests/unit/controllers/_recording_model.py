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

"""
A stand-in Model for the Step 4a Controller slots, shared by two test modules.

Step 4a replaces the signal bus with ``self.model.call(metaclass, key, method, *args)``,
so a Controller test needs a Model that answers that one method with a canned value and
records what it was asked. ``mocker.Mock()`` cannot do the second half legibly once a
slot makes several calls in sequence, and cannot make one of them raise without making
all of them raise.

Kept out of the test modules themselves so that the two that need it - the promoted
base methods and Metadata's own fetch slots - cannot drift into two versions of the
same double.
"""


class RecordingModel:
    """
    A Model whose ``call`` records its arguments and replays canned answers.

    The answers are keyed by plugin method name and should be written from that
    method's real signature on its ``Meta*`` base rather than from the calling code,
    which is what keeps a test from pinning the shape its caller happens to assume. An
    answer that is an ``Exception`` instance is raised instead of returned, which is
    how the failure paths are driven now that ``call()`` raises rather than swallowing.

    :ivar answers: plugin method name to canned answer, or to an exception to raise
    :ivar calls: every call made, as ``(metaclass, key, method, args)``
    """

    def __init__(self, answers: dict) -> None:
        """
        :param answers: plugin method name to answer, or to an exception to raise
        :type answers: dict
        """
        self.answers = answers
        self.calls: list = []

    def call(self, metaclass: str, key: str, method: str, *args: object) -> object:
        """
        Record one plugin call and return its canned answer.

        :param metaclass: the plugin family
        :type metaclass: str
        :param key: the plugin instance's key
        :type key: str
        :param method: the method being called on it
        :type method: str
        :param args: the positional arguments, spread rather than tupled
        :type args: object
        :return: whatever this method's canned answer is
        :rtype: object
        """
        self.calls.append((metaclass, key, method, args))
        answer = self.answers[method]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def calls_to(self, method: str) -> list:
        """
        Every recorded call to one plugin method, as its argument tuples.

        :param method: the plugin method name
        :type method: str
        :return: one entry per call, each the positional arguments it was given
        :rtype: list
        """
        return [args for _, _, name, args in self.calls if name == method]
