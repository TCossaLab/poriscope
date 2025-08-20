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
# Deekshant Wadhwa

import logging
from collections.abc import Sequence
from enum import IntEnum
from types import SimpleNamespace
from typing import Any, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
from kneed import KneeLocator
from numpy.typing import NDArray
from sklearn.ensemble import AdaBoostRegressor
from sklearn.metrics import mean_squared_error
from sklearn.tree import DecisionTreeRegressor
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFitter import MetaEventFitter

Numeric = Union[int, float, np.number]


class P6Flags(IntEnum):
    NEGATIVE = -1
    ZERO = 0
    POSITIVE = 1


class SingleSublevel:
    _p6Flags_sublevelType: P6Flags

    def __init__(
        self, start: int, end: Optional[int] = None, height: Optional[float] = None
    ):
        # end is not included
        self.start: int = start
        self.end: int = end  # type: ignore
        self.height: float = height  # type: ignore

    def update(self, end: int, height: float):
        self.end = end
        self.height = height

    def fetchData(self, event: Sequence, d: bool = False):
        if d:
            plt.plot(event)
            plt.axvline(self.start + 22)
            plt.axvline(self.end)
            # plt.show()
        return event[self.start : self.end]

    @property
    def width(self) -> int:
        return self.end - self.start

    def __str__(self):
        return f"<{self.start} {self.end} {self.height}>"

    def __repr__(self):
        return self.__str__()


class HackyList(list):
    """
    HackyList is a subclass of Python's built-in list that allows arbitrary
    attribute assignment. It exists to support use cases where a list-like
    structure is required but needs to carry additional metadata or
    auxiliary attributes, which native Python lists do not allow.

    This class is used to return a list like object for sublevel edges from
    _locate_sublevel_transitions to return edges and attatch extra information
    along with it i.e. sublevel heights.

    Example usage:
        >>> hl = HackyList([1, 2, 3])
        >>> hl.heights = [1.2, 4.1, 0.1]
        >>> hl.extra = {}
        >>> print(hl, hl.heights, hl.extra)
        [1, 2, 3] [1.2, 4.1, 0.1] {}
    """

    self: Any


class Sublevels:
    def __init__(self):
        self.sublevels = []

    def __str__(self):
        res = ""
        for sublevel in self.sublevels:
            res += str(sublevel)
        return res

    def insert(self, sublevel):
        self.sublevels.append(sublevel)

    def combinedRegion(self, i):
        # Combined region of i and i+1
        return self.sublevels[i].start, self.sublevels[i + 1].end

    def merge(self, i, height):
        # merge i and i+1 | delete i+1
        self.sublevels[i].update(self.sublevels[i + 1].end, height)
        self.sublevels.pop(i + 1)

    @property
    def size(self):
        return sum(i.width for i in self.sublevels)

    @property
    def edges(self):
        return [0] + [i.end for i in self.sublevels]

    @property
    def heights(self):
        return [i.height for i in self.sublevels]

    def denormalize(self, baseline_mean_original, baseline_std_original):
        for sublevel in self.sublevels:
            sublevel.height = (
                sublevel.height * baseline_std_original
            ) + baseline_mean_original

    def filterEmptySublevels(self):
        i = 0
        while i < len(self.sublevels):
            if self.sublevels[i].width <= 0:
                del self.sublevels[i]
            else:
                i += 1

    @property
    def embeded(self) -> List[int]:
        assert len(self.edges) - 1 == len(self.heights)
        edges = HackyList(self.edges)
        edges.self = SimpleNamespace()
        edges.self.sublevels = self
        return edges


def extractContiniousRegions(data: Union[Sequence, NDArray]):
    """
    data: numpy array or list
    returns: widths(list), height(list)
    """
    if len(data) == 0:
        return [0], [0]
    if len(data) == 1:
        return [1], [1]
    if len(data) == 2:
        return [2], [2]
    widths = []
    heights = []
    startAt = 0
    prevDirection = data[1] > data[0]
    i = 1  # Useful if len(data) is 0
    for i in range(1, len(data)):
        currDirection = data[i] > data[i - 1]
        if prevDirection != currDirection:
            endsAt = i - 1
            widths.append(endsAt - startAt + 1)
            heights.append(data[endsAt] - data[startAt])
            startAt = endsAt + 1
        prevDirection = currDirection
    widths.append(i - startAt + 1)
    heights.append(data[-1] - data[startAt])
    assert sum(widths) == len(data)
    return widths, heights


def _check_one_sided_percent_parity(
    sublevel_segment, sublevel_height, oneSidedPercentParity
):
    positive_count = np.sum((sublevel_segment - sublevel_height) > 0)
    negative_count = len(sublevel_segment) - positive_count
    positive_count /= len(sublevel_segment)
    negative_count /= len(sublevel_segment)
    check = np.abs(positive_count - negative_count)
    if check > oneSidedPercentParity:
        # if lopsided
        return False, check
    return True, check


def BigConfidenceBooster(
    data,
    sublevels: Sublevels,
    minDataPointsToBeBoosted: int,
    oneSidedPercentParity: float,  # 0->1
) -> Sublevels:
    for i, sublevel in enumerate(sublevels.sublevels):
        if sublevel.width < minDataPointsToBeBoosted:
            continue
        sublevel_segment = data[sublevel.start : sublevel.end]
        if _check_one_sided_percent_parity(
            sublevel_segment, sublevel.height, oneSidedPercentParity
        )[0]:
            continue
        else:
            t1 = np.mean(sublevel_segment)
            c1 = _check_one_sided_percent_parity(
                sublevel_segment, t1, oneSidedPercentParity
            )
            if c1[0]:
                sublevels.sublevels[i].height = t1
                continue

            t2 = np.mean(sublevel_segment[len(sublevel_segment) // 2 :])
            sublevels.sublevels[i].height = t2
    return sublevels


def exceptional_height_refresh(
    settings,
    event,
    sublevels,
    exceptionalHeightBaseMaxDiffForHeightRefresh,
    heightFunction,
):
    # ToDo: Unfinished (exceptionalHeightBaseMaxDiffForHeightRefresh is boundless)
    for i in range(len(sublevels.sublevels) - 1):
        s = event["raw"][sublevels.sublevels[i].start : sublevels.sublevels[i].end]
        up = np.abs(np.max(s) - sublevels.sublevels[0].height)
        down = np.abs(np.min(s) - sublevels.sublevels[0].height)
        currHeight = np.max((up, down))
        if currHeight > exceptionalHeightBaseMaxDiffForHeightRefresh:
            previousHeight = sublevels.sublevels[i - 1].height if i > 0 else None
            newHeight = heightFunction(settings, s, previousHeight=previousHeight)
            sublevels.sublevels[i].height = newHeight
    return sublevels


def normalHeightRefresh(
    settings, sublevels: Sublevels, raw, heightFunction
) -> Sublevels:
    previousHeight = None
    for sublevel in sublevels.sublevels:
        sublevel.height = heightFunction(
            settings, sublevel.fetchData(raw), previousHeight
        )
        previousHeight = sublevel.height
    return sublevels


def _check_exceptional_sublevel(
    sublevel: SingleSublevel,
    i: int,
    sublevels: Sublevels,
    minDataPointsToBeSubLevel,
    exceptionalPeak_MinHeightStdAboveAndBelow,
    exceptionalPeak_WidthLowerBound,
    exceptionalPeak_BaseDifferenceStdAtleast,
    exceptionalSlope_MinHeightStdOfMinDiff,
    exceptionalSlope_WidthLowerBound,
    baseline_mean,
    baseline_std,
) -> bool:
    """
    Return True if the sublevel is exceptional
    """
    # Sanity initialization (not needed; if any of the bottom to ifs are valid then the first will definitly generate these values)
    prevHeight_nonExceptional = 0.0
    nextHeight_nonExceptional = 0.0

    # ToDo: Check
    if exceptionalPeak_WidthLowerBound > 0 or exceptionalSlope_WidthLowerBound > 0:
        for j in range(i - 1, -1, -1):
            if sublevels.sublevels[j].width > minDataPointsToBeSubLevel:
                prevHeight_nonExceptional = sublevels.sublevels[j].height
                break
        else:
            prevHeight_nonExceptional = baseline_mean
        for j in range(i + 1, len(sublevels.sublevels)):
            if sublevels.sublevels[j].width > minDataPointsToBeSubLevel:
                nextHeight_nonExceptional = sublevels.sublevels[j].height
                break
        else:
            nextHeight_nonExceptional = baseline_mean

    # PEAK exception
    if exceptionalPeak_WidthLowerBound > 0:
        currHeight = sublevels.sublevels[i].height
        hd1 = currHeight - prevHeight_nonExceptional
        hd2 = currHeight - nextHeight_nonExceptional
        exceptionalHeight = exceptionalPeak_MinHeightStdAboveAndBelow * baseline_std
        exceptionalBaseDifferenceStd_atleast_height = (
            exceptionalPeak_BaseDifferenceStdAtleast * baseline_std
        )
        c1 = np.abs(hd1) > exceptionalHeight
        c2 = np.abs(hd2) > exceptionalHeight
        c3 = hd1 * hd2 > 0
        c4 = sublevel.width > exceptionalPeak_WidthLowerBound
        c5 = (
            np.abs(nextHeight_nonExceptional - prevHeight_nonExceptional)
            > exceptionalBaseDifferenceStd_atleast_height
        )
        if c1 and c2 and c3 and c4 and c5:
            return True

    # SLOPE exception
    if exceptionalSlope_WidthLowerBound > 0:
        currHeight = sublevels.sublevels[i].height
        hd1 = currHeight - prevHeight_nonExceptional
        hd2 = currHeight - nextHeight_nonExceptional
        c1 = (
            np.min((np.abs(hd1), np.abs(hd2)))
            > exceptionalSlope_MinHeightStdOfMinDiff * baseline_std
        )
        c2 = sublevel.width > exceptionalSlope_WidthLowerBound
        c3 = hd1 * hd2 < 0
        if c1 and c2 and c3:
            return True
    return False


def debug_plot_sublevels(sublevels: Sublevels, data, name):
    print(name)
    plt.scatter(range(len(data)), data, s=0.1)
    print(sublevels.sublevels)
    x = []
    y = []
    for sublevel in sublevels.sublevels:
        # plt.axvline(sublevel.end,lw=1)
        # plt.axhline(sublevel.height,sublevel.start,sublevel.end,lw=1,c='red')
        x.append(sublevel.start)
        x.append(sublevel.end)
        y.append(sublevel.height)
        y.append(sublevel.height)
    plt.plot(x, y, c="red")
    plt.title(name)
    plt.show()


@inherit_docstrings
class NanoTrees(MetaEventFitter):
    """
    Abstract base class to analyze and flag the start and end times of regions
    of interest in a timeseries for further analysis.
    """

    logger = logging.getLogger(__name__)

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(self, globally_available_plugins=None, standalone=False):
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaEventFinder` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        Your Eventfinder MUST include at least the "MetaReader" key, which can be ensured by calling super().get_empty_settings(globally_available_plugins, standalone) before adding any additional settings keys

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventFinder`, which already has an implementation of this function that ensures that settings will have the required :ref:`MetaReader` key available to users, in most cases you will need to override it to add any other settings required by your subclass. If you need additional settings, which you almost ccertainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Threshold"] = {"Type": float,
                                    "Value": None,
                                    "Min": 0.0,
                                    "Units": "pA"
                                    }
            settings["Min Duration"] = {"Type": float,
                                        "Value": 0.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Max Duration"] = {"Type": float,
                                        "Value": 1000000.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Min Separation"] = {"Type": float,
                                            "Value": 0.0,
                                            "Min": 0.0,
                                            "Units": "us"
                                        }
            return settings

        which will ensure that your have the 3 keys specified above, as well as an additional key, ``"MetaReader"``, as required by eventfinders. In the case of categorical settings, you can also supply the "Options" key in the second level dictionaries.
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Smallest Significant Sublevel"] = {
            "Type": float,
            "Value": 600.0,
            "Min": 0.0,
            "Units": "pA",
        }
        settings["Time Scaling"] = {"Type": float, "Value": 1.1}
        settings["Exceptional Sublevel Sensitivity"] = {
            "Type": float,
            "Value": 0.3,  # % of p4_minDataPointsToBeSubLevel
            "Min": 0.0,  # 0 = disable
        }
        return settings

    @log(logger=logger)
    @override
    def close_resources(self, channel: int | None = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def construct_fitted_event(self, channel, index):
        """
        Construct an array of data corresponding to the fit for the specified event

        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :raises RuntimeError: if fitting is not complete yet
        """
        if self.sublevel_metadata == {}:
            raise RuntimeError("Fitting is not complete, fit events first")
        if self.eventloader is not None:
            samplerate = self.eventloader.get_samplerate(channel)
        else:
            raise AttributeError(
                "Nano Trees cannot operate without a linked MetaEventLoader"
            )
        sublevel_start_indices = [
            int(sublevel_duration * samplerate * 1e-6)
            for sublevel_duration in self.sublevel_metadata[channel][index][
                "sublevel_start_times"
            ]
        ]
        sublevel_end_indices = [
            int(sublevel_duration * samplerate * 1e-6)
            for sublevel_duration in self.sublevel_metadata[channel][index][
                "sublevel_end_times"
            ]
        ]

        sublevel_currents = self.sublevel_metadata[channel][index]["sublevel_current"]
        data = np.zeros(sublevel_end_indices[-1], dtype=np.float64)
        for start, end, current in zip(
            sublevel_start_indices, sublevel_end_indices, sublevel_currents
        ):
            data[start:end] = current
        return data

    # public API, should generally be left alone by subclasses

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        ...

    @log(logger=logger)
    @override
    def _pre_process_events(self, channel: int) -> None:
        """
        :param channel: the channel to preprocess
        :type channel: int
        """
        ...

    def _set_automation_hyperparameters(
        self, smallestSignificantSublevelStd, rise_time
    ) -> dict:
        """
        automate setting most hyperparamters for the fit based on multiples of a few more elements
        """
        settings = {}
        settings["p3_numberOfStdAboveAndBelow"] = smallestSignificantSublevelStd
        settings["p3_confidenceBoost_oneSidedPercentParity"] = 0.5
        settings["p3_confidenceBoost_minDataPointsToBeBoosted"] = 5

        time_scaling = self.settings["Time Scaling"]["Value"]
        p4_minDataPointsToBeSubLevel = int(abs(rise_time * 6 * time_scaling))
        exceptionalWidth = int(
            abs(
                p4_minDataPointsToBeSubLevel
                * self.settings["Exceptional Sublevel Sensitivity"]["Value"]
            )
        )
        settings["p4_minDataPointsToBeSubLevel"] = p4_minDataPointsToBeSubLevel
        settings["p4_numberOfStdAboveAndBelow"] = smallestSignificantSublevelStd
        settings["p4_exceptionalPeak_BaseDifferenceStdAtleast"] = 0.01
        settings["p4_exceptionalPeak_MinHeightStdAboveAndBelow"] = (
            smallestSignificantSublevelStd
        )
        settings["p4_exceptionalPeak_WidthLowerBound"] = exceptionalWidth
        settings["p4_exceptionalSlope_MinHeightStdOfMinDiff"] = (
            smallestSignificantSublevelStd * 1.5
        )
        settings["p4_exceptionalSlope_WidthLowerBound"] = exceptionalWidth

        settings["p5_numberOfStdAboveAndBelow"] = smallestSignificantSublevelStd
        settings["p6_baselineStdThreshold"] = 2.8
        settings["directionalThreshold"] = 0.8
        settings["shortSublevelDefinition"] = p4_minDataPointsToBeSubLevel // 2
        return settings

    def _DNA(self, data: NDArray, padding_before, padding_after, baseline_mean):
        """
        Function stands for Do Not Assume, and serves to calculate widths and height of sublevels without making any assumptions about the shape of the rise time
        """
        padding = np.hstack((data[:padding_before], data[-padding_after:]))
        widths, heights = extractContiniousRegions(padding)
        assert len(widths) == len(heights)
        assert sum(widths) == len(padding)
        # width_threshold = np.percentile(widths, 0.95) #never used, unnecessary
        height_threshold = np.max(np.abs(heights)) / 2
        widths, heights = extractContiniousRegions(data)
        edges = np.cumsum(widths) - 1
        assert edges[-1] + 1 == len(data)
        heights = data[edges].tolist()
        # no_capacitance = np.repeat(data[[edges]], widths) #never used, unnecessary
        # plt.plot(no_capacitance, c="r")
        # plt.scatter(range(len(data)), data, s=1)
        # plt.get_current_fig_manager().window.showMaximized()
        # plt.show()
        filtered_widths = [0]
        filtered_heights = [0]
        i = 0
        while i < len(widths):
            width, height = widths[i], abs(heights[i])
            delete = False
            if (
                filtered_heights[-1] - height_threshold
                <= height
                <= filtered_heights[-1] + height_threshold
            ):
                delete = True
            if delete:
                filtered_widths[-1] += width
                filtered_heights[-1] = filtered_heights[-1] + (
                    width / filtered_widths[-1]
                ) * (height - filtered_heights[-1])
            else:
                filtered_heights.append(height)
                filtered_widths.append(width)
            i += 1
            # filtered_signal = np.repeat(filtered_heights, filtered_widths) #never used
            # plt.plot(filtered_signal)
            # plt.scatter(range(len(data)), data, s=1, c="r")
            # plt.get_current_fig_manager().window.showMaximized()
            # plt.show()
            # print(width, height)
        # filtered_signal = np.repeat(filtered_heights, filtered_widths) #never used, unnecessary
        # assert len(filtered_signal) == len(data)
        # plt.plot(filtered_signal)
        # plt.scatter(range(len(data)), data, s=1)
        # plt.get_current_fig_manager().window.showMaximized()
        # plt.show()
        # exit()
        return filtered_widths, filtered_heights

    @log(logger=logger)
    @override
    def _locate_sublevel_transitions(
        self,
        data,
        samplerate,
        padding_before,
        padding_after,
        baseline_mean,
        baseline_std,
    ):
        """
        Get a list of indices corresponding to the starting point of all sublevels within an event. Will be pre-pended with 0 if 0 is not the first entry.
        Plugin must handle gracefully the case where any of the arguments except data are None, as not all event loaders are guaranteed to return these values.
        Raising an an acceptable handler.

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param padding_before: the number of data points before the estimated start of the event in the chunk
        :type padding_before: Optional[int]
        :param padding_after: the number of data points after the estimated end of the event in the chunk
        :type padding_after: Optional[int]
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]

        :return: a list of integers corresponding to sublevel transitions
        :rtype: List[int]

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset
        :raises AttributeError: if the fitting method cannot operate without provision of specific padding and baseline metadata and cannot rescue itself. This will cause a stop to processing of the dataset.
        """
        baseline_std = np.std(data[:padding_before])
        baseline_mean = np.mean(data[:padding_before])

        ### Normalization
        data = (data - baseline_mean) / baseline_std  # baseline | std=1 | mean=0
        # self._DNA(data,padding_before,padding_after,baseline_mean)

        ### Hyperparameter Automation
        smallestSignificantSublevel = abs(
            self.settings["Smallest Significant Sublevel"]["Value"]
        )
        smallestSignificantSublevelStd = abs(smallestSignificantSublevel) / baseline_std
        rise_time = self.get_rise_time(data)
        settings = self._set_automation_hyperparameters(
            smallestSignificantSublevelStd, rise_time
        )

        # plt.plot(data,label="original")
        p2 = self._ml_automation(data)
        # plt.scatter(range(len(data)), data, s=0.1)
        # plt.axhline(self.settings["p3_numberOfStdAboveAndBelow"]["Value"])
        # plt.plot(p2,label='p2')
        # plt.legend();plt.show()
        p3_sublevels = self._pass3(settings, p2)
        # debug_plot_sublevels(p3_sublevels,data,"p3")
        p4_sublevels = self._pass4(settings, p3_sublevels, p2)
        # debug_plot_sublevels(p4_sublevels,data,"p4")
        p5_sublevels = self._pass5(settings, p4_sublevels, p2)
        # debug_plot_sublevels(p5_sublevels,data,"p5")
        p6_sublevels = self._pass6(settings, p5_sublevels, p2)
        # debug_plot_sublevels(p6_sublevels,data,"p6")
        p7_sublevels = self._pass7(settings, p6_sublevels, data)
        final_sublevels = self._slope_height_adjust(settings, p7_sublevels, p2)
        final_sublevels.denormalize(baseline_mean, baseline_std)
        # if len(final_sublevels.edges)-1!=len(final_sublevels.heights) or final_sublevels.edges==[0,12732]:
        #     debug_plot_sublevels(final_sublevels,data,'final')
        #     breakpoint()
        return final_sublevels.embeded

    def _ml_automation(
        self, data: NDArray, searchStart: int = 3, searchEnd: int = 20, DEBUG=False
    ) -> NDArray:
        """
        automatically estimate parameters needed for optimizing the fit sensitivity
        """
        score = []
        Y = data.copy()
        X = np.array(range(len(Y))).reshape((-1, 1))
        for i in range(searchStart, searchEnd):
            regressor = DecisionTreeRegressor(
                max_leaf_nodes=i,
                min_samples_leaf=4,
                min_samples_split=9,
            )
            regressor.fit(X, Y)
            score.append(mean_squared_error(Y, regressor.predict(X)))
        kneedle = KneeLocator(
            range(searchStart, searchEnd),
            score,
            S=2,
            curve="convex",
            direction="decreasing",
        )
        if kneedle.knee is None:
            kneedle.knee = searchEnd
        max_leaf_nodes = max(4, int(round(kneedle.knee * 1.1)))
        regressor = DecisionTreeRegressor(
            max_leaf_nodes=max_leaf_nodes,
            min_samples_leaf=5,
            min_samples_split=10,
        )
        regressor.fit(X, Y)
        y = regressor.predict(X)
        return y

    def __pass1(self, settings, data, DEBUG=False) -> NDArray:
        """
        Approximate level breakdown using Adaboost to overfit the event
        """
        # Ensemble Adaboost Decession Tree
        Y = data
        X = np.array(range(len(Y))).reshape((-1, 1))
        approxSubLevelEstimate = settings["p1_approxSubLevelEstimate"]
        adaBoostRegressorNEstimators = settings["p1_adaBoostRegressorNEstimators"]
        regressor = AdaBoostRegressor(
            DecisionTreeRegressor(max_depth=approxSubLevelEstimate),
            n_estimators=adaBoostRegressorNEstimators,
        )
        regressor.fit(X, Y)
        y = regressor.predict(X)
        return y

    def __pass2(self, settings, data, DEBUG=False) -> NDArray:
        """
        Refine the estimate from pass1 using decision trees; still overfit intentionally
        """
        # Single Decession Tree
        Y = data
        X = np.array(range(len(Y))).reshape((-1, 1))
        approxSubLevelEstimate = settings["p2_approxSubLevelEstimate"]
        regressor = DecisionTreeRegressor(max_depth=approxSubLevelEstimate)
        regressor.fit(X, Y)
        y = regressor.predict(X)
        return y

    def _pass3(self, settings, data, DEBUG=False) -> Sublevels:
        """
        Merge Similar Heights with Iterative Height Updates
        """
        # Merge Similar Heights with Iterative Height Updates
        numberOfStdAboveAndBelow = settings["p3_numberOfStdAboveAndBelow"]
        minHeightDifferenceToBeSubLevel = (
            numberOfStdAboveAndBelow  # as baseline_std = 1
        )
        sublevels = Sublevels()
        currSublevel = SingleSublevel(0, 0, data[0])
        # get distinct sublevels without constraints
        x = -1
        for x, y in enumerate(data):
            if not np.isclose(
                y, currSublevel.height, 0, min(1, minHeightDifferenceToBeSubLevel)
            ):
                newCurrentHeight = data[x - 1]
                currSublevel.update(x, newCurrentHeight)
                sublevels.insert(currSublevel)
                currSublevel = SingleSublevel(x, x, y)
        if x == -1:
            raise ValueError("Data is empty — no sublevel could be processed.")
        currSublevel.update(x + 1, currSublevel.height)
        sublevels.insert(currSublevel)
        assert len(data) == sum(_.width for _ in sublevels.sublevels)

        # confidence boost
        confidenceBoost_oneSidedPercentParity = settings[
            "p3_confidenceBoost_oneSidedPercentParity"
        ]
        if confidenceBoost_oneSidedPercentParity > 0:
            confidenceBoost_minDataPointsToBeBoosted = settings[
                "p3_confidenceBoost_minDataPointsToBeBoosted"
            ]
            sublevels = BigConfidenceBooster(
                data,
                sublevels,
                confidenceBoost_oneSidedPercentParity,
                confidenceBoost_minDataPointsToBeBoosted,
            )

        # iterative height updates and merging
        while True:
            # Debug after each iteration
            for i in range(len(sublevels.sublevels) - 1):
                # plt.plot(data)
                # plt.axhline(sublevels.sublevels[i].height-minHeightDifferenceToBeSubLevel,ls=":")
                # plt.axhline(sublevels.sublevels[i].height+minHeightDifferenceToBeSubLevel,ls=":")
                # debug_plot_sublevels(sublevels,data,"-")
                start, end = sublevels.combinedRegion(i)  # start of i and end of i+1
                # prevSublevelHeight = sublevels.sublevels[i-1].height if i > 0 else None
                prevSublevelHeight = None
                if (
                    np.abs(
                        sublevels.sublevels[i + 1].height
                        - sublevels.sublevels[i].height
                    )
                    < minHeightDifferenceToBeSubLevel
                ):
                    height = self.l50_max_height(
                        settings, data[start:end], previousHeight=prevSublevelHeight
                    )
                    sublevels.merge(i, height)
                    break
            else:
                break
        # debug_plot_sublevels(sublevels,data,"!")

        # # exceptional height refresh
        # sublevels = exceptional_height_refresh(
        #     event,
        #     sublevels,
        #     exceptionalHeightBaseMaxDiffForHeightRefresh,
        #     heightFunction
        # )

        # Refresh all heights (If issues: fix exceptional_height_refresh)
        # ToDo: Fix why skiping left baseline refres [1:-1] ruins the entire fit.
        for i, sublevel in enumerate(sublevels.sublevels[:-1]):
            previousHeight = sublevels.sublevels[i - 1].height if i > 0 else None
            sublevel_segment = data[sublevel.start : sublevel.end]
            newHeight = self.l50_max_height(
                settings, sublevel_segment, previousHeight=previousHeight
            )
            sublevels.sublevels[i].height = newHeight
        assert len(data) == sum(_.width for _ in sublevels.sublevels)
        return sublevels

    def _pass4(self, settings, sublevels: Sublevels, raw, DEBUG=False) -> Sublevels:
        """
        Split Sublevels with Small Widths with Exceptional Small but Tall Sublevels
        """
        numberOfStdAboveAndBelow = settings["p4_numberOfStdAboveAndBelow"]
        minDataPointsToBeSubLevel = settings["p4_minDataPointsToBeSubLevel"]
        exceptionalPeak_MinHeightStdAboveAndBelow = settings[
            "p4_exceptionalPeak_MinHeightStdAboveAndBelow"
        ]
        exceptionalPeak_WidthLowerBound = settings["p4_exceptionalPeak_WidthLowerBound"]
        exceptionalPeak_BaseDifferenceStdAtleast = settings[
            "p4_exceptionalPeak_BaseDifferenceStdAtleast"
        ]
        exceptionalSlope_MinHeightStdOfMinDiff = settings[
            "p4_exceptionalSlope_MinHeightStdOfMinDiff"
        ]
        exceptionalSlope_WidthLowerBound = settings[
            "p4_exceptionalSlope_WidthLowerBound"
        ]
        baseline_mean = 0
        baseline_std = 1

        while True:
            for i, sublevel in enumerate(sublevels.sublevels):
                if sublevel.width < minDataPointsToBeSubLevel:
                    # Exceptional Sublevel
                    if _check_exceptional_sublevel(
                        sublevel,
                        i,
                        sublevels,
                        minDataPointsToBeSubLevel,
                        exceptionalPeak_MinHeightStdAboveAndBelow,
                        exceptionalPeak_WidthLowerBound,
                        exceptionalPeak_BaseDifferenceStdAtleast,
                        exceptionalSlope_MinHeightStdOfMinDiff,
                        exceptionalSlope_WidthLowerBound,
                        baseline_mean,
                        baseline_std,
                    ):
                        continue

                    # Deletion procedures
                    if i == 0:  # In the beginning
                        sublevels.sublevels[1].start = 0
                        sublevels.sublevels[1].height = self.l50_max_height(
                            settings,
                            raw[
                                sublevels.sublevels[1]
                                .start : sublevels.sublevels[1]
                                .end
                            ],
                        )
                        del sublevels.sublevels[0]
                        break
                    elif i == len(sublevels.sublevels) - 1:  # In the end
                        sublevels.sublevels[-2].end = sublevels.sublevels[-1].end
                        sublevels.sublevels[-2].height = self.l50_max_height(
                            settings,
                            raw[
                                sublevels.sublevels[-2]
                                .start : sublevels.sublevels[-2]
                                .end
                            ],
                        )
                        del sublevels.sublevels[-1]
                        break
                    else:
                        sublevelStd = np.std(raw[sublevel.start : sublevel.end])
                        threshold = numberOfStdAboveAndBelow * sublevelStd
                        up = sublevel.height + threshold
                        down = sublevel.height - threshold
                        j = -1  # Preventing j unbounded error
                        for j in range(sublevel.start, sublevel.end):
                            if raw[j] > up or raw[j] < down:
                                break
                        if j == -1:
                            raise ValueError(
                                f"Loop did not run — likely empty range: start={sublevel.start}, end={sublevel.end}."
                            )
                        sublevels.sublevels[i - 1].end = j
                        sublevels.sublevels[i - 1].height = self.l50_max_height(
                            settings,
                            sublevels.sublevels[i - 1].fetchData(raw),
                            sublevels.sublevels[i - 2].height,
                        )
                        sublevels.sublevels[i + 1].start = j
                        sublevels.sublevels[i + 1].height = self.l50_max_height(
                            settings,
                            sublevels.sublevels[i + 1].fetchData(raw),
                            sublevels.sublevels[i - 1].height,
                        )
                        del sublevels.sublevels[i]
                        break
            else:
                break
        return sublevels

    def _pass5(self, settings, sublevels: Sublevels, raw, DEBUG=False) -> Sublevels:
        """
        Repeat Merge Similar Heights
        """
        numberOfStdAboveAndBelow = settings["p5_numberOfStdAboveAndBelow"]
        baseline_std = 1
        minHeightDifferenceToBeSubLevel = numberOfStdAboveAndBelow * baseline_std
        while True:
            if len(sublevels.sublevels) < 3:
                break
            for i, sublevel in enumerate(sublevels.sublevels[:-1]):
                nextSublevel = sublevels.sublevels[i + 1]
                if (
                    np.abs(sublevel.height - nextSublevel.height)
                    < minHeightDifferenceToBeSubLevel
                ):
                    # Weighted average of the two sublevels
                    newHeight = (
                        sublevel.height * sublevel.width
                        + nextSublevel.height * nextSublevel.width
                    )
                    newHeight /= sublevel.width + nextSublevel.width
                    sublevels.merge(i, newHeight)
                    break
            else:
                break
        # refresh heights
        sublevels = normalHeightRefresh(settings, sublevels, raw, self.l50_max_height)
        return sublevels

    def _pass6(self, settings, sublevels: Sublevels, raw, DEBUG=False) -> Sublevels:
        """
        # Clear Baseline in case there are noisy sublevel transitions flagged in the baseline
        """
        baseline_height = 0
        baseline_std = 1
        baseline_std_threshold_original = abs(1.5 * baseline_std)
        # left_baseline_index = self._nt_padding_before
        # right_baseline_index = len(raw) - self._nt_padding_after

        # _p6Flags_sublevelType: 0 Baseline | 1 Up | -1 Down
        previousDirection: P6Flags = P6Flags.ZERO
        startingIndex: list[int] = []
        regionSize: list[int] = []
        # Set any sublevel with threshold to baseline_height
        for i, sublevel in enumerate(sublevels.sublevels):
            if (
                baseline_height - baseline_std_threshold_original
                <= sublevel.height
                <= baseline_height + baseline_std_threshold_original
            ):
                sublevel.height = 0
                sublevel._p6Flags_sublevelType = P6Flags.ZERO
            elif sublevel.height > baseline_height:
                sublevel._p6Flags_sublevelType = P6Flags.POSITIVE
            else:
                sublevel._p6Flags_sublevelType = P6Flags.NEGATIVE

            if sublevel._p6Flags_sublevelType == P6Flags.ZERO:  # baseline
                ...  # do nothing | this will ensure next insertion is non continious
            elif sublevel._p6Flags_sublevelType == previousDirection:
                if not startingIndex:
                    raise Exception(
                        "Matching direction cant be with empty region and non baseline."
                    )
                regionSize[-1] += sublevel.width
            else:
                startingIndex.append(i)
                regionSize.append(sublevel.width)

            previousDirection = sublevel._p6Flags_sublevelType

        newSublevels = Sublevels()
        if not regionSize:
            # Nothing Found
            newSublevels.insert(SingleSublevel(0, len(raw), 0))
            return newSublevels
        MaxRegionSizeIndex = np.argmax(regionSize)
        MaxStartingIndex = startingIndex[
            MaxRegionSizeIndex
        ]  # Index of first sublevel in the region of max size
        # Left Baseline
        newSublevels.insert(
            SingleSublevel(0, sublevels.sublevels[MaxStartingIndex].start, 0)
        )
        direction = sublevels.sublevels[MaxStartingIndex]._p6Flags_sublevelType
        # Insert other sublevels with same direction
        for i in range(MaxStartingIndex, len(sublevels.sublevels)):
            if sublevels.sublevels[i]._p6Flags_sublevelType != direction:
                break
            newSublevels.insert(sublevels.sublevels[i])
        # Right Baseline
        newSublevels.insert(SingleSublevel(newSublevels.sublevels[-1].end, len(raw), 0))
        newSublevels.filterEmptySublevels()
        return newSublevels

    # def __pass6(self, sublevels: Sublevels, raw, DEBUG=False) -> Sublevels:  # UNUSED
    #     # Clear Baseline <Template: baseline,sublevels...,baseline>
    #     # Event Finder estimates are bad
    #     baseline_height = 0
    #     new_sublevels = Sublevels()
    #     if len(sublevels.sublevels) <= 2:
    #         new_sublevels.insert(SingleSublevel(0, len(raw), baseline_height))
    #         return new_sublevels

    #     new_sublevels.insert(
    #         SingleSublevel(0, self._nt_padding_before, baseline_height)
    #     )  # Left baseline
    #     if len(sublevels.sublevels) == 3:
    #         new_sublevels.insert(
    #             SingleSublevel(
    #                 self._nt_padding_before,
    #                 len(raw) - self._nt_padding_after,
    #                 sublevels.sublevels[1].height,
    #             )
    #         )
    #     else:
    #         new_sublevels.insert(
    #             SingleSublevel(
    #                 self._nt_padding_before,
    #                 sublevels.sublevels[1].end,
    #                 sublevels.sublevels[1].height,
    #             )
    #         )
    #         for sublevel in sublevels.sublevels[2:-2]:
    #             new_sublevels.insert(sublevel)
    #         new_sublevels.insert(
    #             SingleSublevel(
    #                 sublevels.sublevels[-2].start,
    #                 len(raw) - self._nt_padding_after,
    #                 sublevels.sublevels[-2].height,
    #             )
    #         )
    #     new_sublevels.insert(
    #         SingleSublevel(len(raw) - self._nt_padding_after, len(raw), baseline_height)
    #     )  # Right baseline
    #     return new_sublevels

    def _pass7(self, settings, sublevels: Sublevels, raw, DEBUG=False) -> Sublevels:
        """
        # Backtrack (Crude Implementation: Faster) to refine the estimate of sublevel changepoints
        """
        for x, sublevel in enumerate(sublevels.sublevels[:-1]):
            if sublevel.end < 2:
                continue  # Avoid underflow

            direction = raw[sublevel.end - 1] > raw[sublevel.end - 2]

            i = sublevel.end - 1
            while i > sublevel.start:
                currDirection = raw[i] > raw[i - 1]
                if direction != currDirection:
                    break
                i -= 1
            sublevel.end = i
            sublevels.sublevels[x + 1].start = i
            if DEBUG:
                print(x)
                debug_plot_sublevels(sublevels, raw, "end")

        sublevels.filterEmptySublevels()
        # Height Update
        sublevels = normalHeightRefresh(settings, sublevels, raw, self.l50_max_height)
        return sublevels

    def _slope_height_adjust(
        self, settings, sublevels: Sublevels, raw, DEBUG=False
    ) -> Sublevels:
        """
        adjust the height estimate for slope-type sublevels
        """
        for i, sublevel in enumerate(sublevels.sublevels[1:-1]):
            prevHeight = sublevels.sublevels[i - 1].height
            currHeight = sublevel.height
            nextHeight = sublevels.sublevels[i + 1].height

            if (
                prevHeight <= currHeight <= nextHeight
                or prevHeight >= currHeight >= nextHeight
            ):
                sublevel.height = self.l50_max_height(settings, sublevel.fetchData(raw))
        return sublevels

    def l50_max_height(self, settings, sublevel, previousHeight=None) -> float:
        """
        # Height Function used to estimate the current level within short sublevels
        """
        shortSublevelDefinition = settings["shortSublevelDefinition"]
        if (len(sublevel) < shortSublevelDefinition) and (previousHeight is not None):
            temp = sublevel.copy() - previousHeight
            direction = np.sum(temp)
            if direction < 0:
                return np.min(sublevel)
            else:
                return np.max(sublevel)
        else:
            return np.mean(sublevel[len(sublevel) // 2 :])

    def get_skip_region(self, data, quantile=0.95):
        """
        estimate region to skip when averaging from the system rise time
        """
        widths, _ = extractContiniousRegions(data)
        rise_time = np.quantile(
            widths, quantile, overwrite_input=True, method="closest_observation"
        )
        # rise_time *= 2
        # rise_time = np.max(widths)
        rise_time = int(rise_time)
        return rise_time

    def get_rise_time(self, data):
        """
        estimte the system rise time
        """
        widths, _ = extractContiniousRegions(data)
        rise_time = np.median(widths, overwrite_input=True)
        rise_time = int(rise_time)
        return rise_time

    @log(logger=logger)
    @override
    def _populate_sublevel_metadata(  # type: ignore
        self, data, samplerate, baseline_mean, baseline_std, sublevel_starts
    ):
        """
        Build a dict of lists of sublevel metadata with whatever arbitrary keys you want to consider in your event fitter. Every list must have exactly the same length as the sublevel_starts list. Note that 'index' is already handled in the base class

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_starts: the list of sublevel start indices located in self._locate_sublevel_transitions()
        :type sublevel_starts: HackyList

        :return: a dict of lists of sublevel metadata values, one list entry per sublevel for each piece of metadata
        :rtype: Dict[str, npt.NDArray[Numeric]]
        """
        sublevel_metadata = {}
        rise_time = self.get_skip_region(data, 0.95)
        # print(rise_time)
        dt_us = 1.0 / samplerate * 1e6
        aC_pC = 1e-6

        # ToDo: int(sublevel_starts[i]+rise_time):int(sublevel_starts[i+1]) Can return an empty slice if rise time extends too long. Needs better rejection handling logic.
        # average the current over the sublevel, ignoring the rise time
        sublevel_metadata["sublevel_current"] = np.array(
            sublevel_starts.self.sublevels.heights
        )  # detect current levels during detected sub-events

        # get the standard deviation over the sublevel, ignoring the rise time
        sublevel_metadata["sublevel_stdev"] = np.array(
            [
                np.nanstd(i.fetchData(data, d=False)[rise_time:])
                for i in sublevel_starts.self.sublevels.sublevels
            ]
        )
        # print(sublevel_metadata["sublevel_stdev"])
        # #get the difference from the local baseline
        event_baseline = 0.5 * (
            sublevel_metadata["sublevel_current"][0]
            + sublevel_metadata["sublevel_current"][-1]
        )
        sublevel_metadata["sublevel_blockage"] = (
            event_baseline - sublevel_metadata["sublevel_current"]
        ) * np.sign(event_baseline)

        # #get durations between sublevel start times
        sublevel_metadata["sublevel_duration"] = np.array(
            [
                (i.end - i.start) * dt_us
                for i in sublevel_starts.self.sublevels.sublevels
            ],
            dtype=np.float64,
        )

        # get sublevel start times
        sublevel_metadata["sublevel_start_times"] = np.array(
            [i.start * dt_us for i in sublevel_starts.self.sublevels.sublevels],
            dtype=np.float64,
        )

        # get sublevel end times
        sublevel_metadata["sublevel_end_times"] = np.array(
            [i.end * dt_us for i in sublevel_starts.self.sublevels.sublevels],
            dtype=np.float64,
        )

        # #get the maximal deviation from the event baseline for each sublevel
        sublevel_metadata["sublevel_max_deviation"] = np.array(
            [
                np.max(np.absolute(i.fetchData(data) - event_baseline))
                for i in sublevel_starts.self.sublevels.sublevels
            ],
            dtype=np.float64,
        )

        # get the ecd using raw data for each sublevel
        sublevel_metadata["sublevel_raw_ecd"] = np.array(
            [
                np.sum(
                    np.sign(event_baseline)
                    * dt_us
                    * aC_pC
                    * (event_baseline - np.array(i.fetchData(data)[rise_time:]))
                )
                for i in sublevel_starts.self.sublevels.sublevels
            ],
            dtype=np.float64,
        )

        # #get the ecd using fitted data for each sublevel
        sublevel_metadata["sublevel_fitted_ecd"] = (
            sublevel_metadata["sublevel_blockage"]
            * sublevel_metadata["sublevel_duration"]
            * aC_pC
        )
        # pprint(sublevel_metadata);exit()
        return sublevel_metadata

    @log(logger=logger)
    @override
    def _populate_event_metadata(
        self, data, samplerate, baseline_mean, baseline_std, sublevel_metadata
    ):
        """
        Assemble a list of metadata to save in the event database later. Note that keys 'start_time_s' and 'index' are already handled in the base class and should not be touched here.

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_metadata: the dict of sublevel metadata built by self._populate_sublevel_metadata()
        :type sublevel_metadata: Dict[str, List[Numeric]]

        :return: a dict of event metadata values
        :rtype: Dict[str, float]
        """
        event_metadata = {}
        event_metadata["duration"] = np.sum(
            sublevel_metadata["sublevel_duration"][1:-1]
        )
        event_metadata["fitted_ecd"] = np.sum(
            sublevel_metadata["sublevel_fitted_ecd"][1:-1]
        )
        event_metadata["raw_ecd"] = np.sum(sublevel_metadata["sublevel_raw_ecd"][1:-1])
        event_metadata["max_blockage"] = np.max(
            sublevel_metadata["sublevel_blockage"][1:-1]
        )
        event_metadata["min_blockage"] = np.min(
            sublevel_metadata["sublevel_blockage"][1:-1]
        )
        event_metadata["max_deviation"] = np.max(
            sublevel_metadata["sublevel_max_deviation"][1:-1]
        )
        event_metadata["max_blockage_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][np.argmax(sublevel_metadata["sublevel_blockage"][1:-1])]
        event_metadata["min_blockage_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][np.argmin(sublevel_metadata["sublevel_blockage"][1:-1])]
        event_metadata["max_deviation_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][np.argmax(sublevel_metadata["sublevel_max_deviation"][1:-1])]
        return event_metadata

    @log(logger=logger)
    @override
    def _post_process_events(self, channel: int) -> None:
        """
        :param channel: the index of the channel to postprocess
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def _define_event_metadata_types(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        metadata_types = {}
        metadata_types["duration"] = float
        metadata_types["fitted_ecd"] = float
        metadata_types["raw_ecd"] = float
        metadata_types["max_blockage"] = float
        metadata_types["min_blockage"] = float
        metadata_types["max_deviation"] = float
        metadata_types["max_blockage_duration"] = float
        metadata_types["min_blockage_duration"] = float
        metadata_types["max_deviation_duration"] = float
        return metadata_types

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_types(self):
        """
        Build a dict of sublevel metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool. Note that this is the type of entries in the associated list,
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        metadata_types = {}
        metadata_types["sublevel_current"] = float
        metadata_types["sublevel_stdev"] = float
        metadata_types["sublevel_blockage"] = float
        metadata_types["sublevel_duration"] = float
        metadata_types["sublevel_start_times"] = float
        metadata_types["sublevel_end_times"] = float
        metadata_types["sublevel_max_deviation"] = float
        metadata_types["sublevel_raw_ecd"] = float
        metadata_types["sublevel_fitted_ecd"] = float
        return metadata_types

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        metadata_units = {}
        metadata_units["duration"] = "us"
        metadata_units["fitted_ecd"] = "pC"
        metadata_units["raw_ecd"] = "pC"
        metadata_units["max_blockage"] = "pA"
        metadata_units["min_blockage"] = "pA"
        metadata_units["max_deviation"] = "pA"
        metadata_units["max_blockage_duration"] = "us"
        metadata_units["min_blockage_duration"] = "us"
        metadata_units["max_deviation_duration"] = "us"
        return metadata_units

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_units(self):
        """
        Build a dict of sublevel metadata units , or None if unitless. Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting.
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Optional[str]]
        """
        metadata_units = {}
        metadata_units["sublevel_current"] = "pA"
        metadata_units["sublevel_stdev"] = "pA"
        metadata_units["sublevel_blockage"] = "pA"
        metadata_units["sublevel_duration"] = "us"
        metadata_units["sublevel_start_times"] = "us"
        metadata_units["sublevel_end_times"] = "us"
        metadata_units["sublevel_max_deviation"] = "pA"
        metadata_units["sublevel_raw_ecd"] = "pC"
        metadata_units["sublevel_fitted_ecd"] = "pC"
        return metadata_units

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass
