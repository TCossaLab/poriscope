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
# Alejandra Carolina González González
# Kyle Briggs

import itertools
import logging
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    Tuple,
    override,
)

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit
from scipy.stats import iqr, t

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel


@inherit_docstrings
class MetadataModel(MetaSubsetTabModel):
    """
    Subclass of MetaSubsetTabModel for handling metadata-related processing and storage.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
    def _auto_bins_1d(self, data: npt.NDArray[np.float64]) -> int:
        """
        Choose a bin count for a 1-D histogram by the Freedman-Diaconis rule.

        Shared verbatim by the density, histogram and capture-rate paths, which used
        three byte-identical copies of it in ``MetadataView``.

        **The exponent is 1/(2 + D), where D is the number of dimensions being
        binned** - so 1/3 here and 1/4 in :meth:`_auto_bins_2d`. That is the
        Freedman-Diaconis rule generalised to D dimensions, and the difference
        between the two methods is deliberate rather than drift. Do not unify them.

        ``OverflowError`` is **not** caught here because the three callers do not
        agree on what to do about it - two fall back to 100 bins and one to the same
        expression used when the interquartile range is zero - and unifying *that*
        would be a behaviour change rather than a move. The caller catches it.

        An ``OverflowError`` from ``int()`` on an infinite ratio propagates out
        rather than being handled - there is no ``raise`` here to document, but the
        caller's ``try`` is load-bearing.

        :param data: the values to be binned
        :type data: npt.NDArray[np.float64]
        :return: the number of bins
        :rtype: int
        """
        if iqr(data) > 0:
            return int(
                (np.max(data) - np.min(data)) * len(data) ** (1.0 / 3.0) / (iqr(data))
            )
        return int(3.332 * np.log10(len(data)))

    @log(logger=logger)
    def _auto_bins_2d(self, data: npt.NDArray[np.float64], count: int) -> int:
        """
        Choose one axis's bin count for a 2-D heatmap.

        Deliberately separate from :meth:`_auto_bins_1d`, and for a stated reason:
        **the exponent is 1/(2 + D) for D binning dimensions**, so a heatmap's two
        dimensions give a fourth root where a histogram's one gives a cube root.
        Freedman-Diaconis generalised to D dimensions. The two methods must not be
        collapsed into one.

        The degenerate fallback also differs - the square root of the sample size
        rather than Sturges' expression - and that one is simply how each path was
        written. It is preserved as-is, so this move changes no output.

        ``count`` is the sample size to raise to the fourth power, and is passed
        rather than taken from ``data`` because the heatmap's y-axis calculation uses
        the *x* array's length. Both arrays are always the same length there - the
        filter that precedes it masks them jointly - so it is inert, and it is
        reproduced rather than quietly corrected.

        :param data: the values to be binned on this axis
        :type data: npt.NDArray[np.float64]
        :param count: the sample size used in the fourth-root term
        :type count: int
        :return: the number of bins
        :rtype: int
        """
        if iqr(data) > 0:
            return int(
                (np.max(data) - np.min(data)) * count ** (1.0 / 4.0) / (iqr(data))
            )
        return int(np.sqrt(len(data)))

    @log(logger=logger)
    def calculate_heatmap(
        self,
        xdata: npt.NDArray[np.float64],
        ydata: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
    ) -> Tuple[
        npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
    ]:
        """
        Bin two columns into a 2-D histogram and return it log2-scaled.

        The arrays arrive already filtered and log-scaled: that step is still
        ``MetaView``'s, and stays there until all eight of its call sites can be
        converted together, so this method is handed exactly what the View's own
        filter produced.

        Empty bins come back as ``-1`` rather than ``-inf``, which is what lets the
        caller's colourbar label them as a count of zero.

        :param xdata: the filtered x values
        :type xdata: npt.NDArray[np.float64]
        :param ydata: the filtered y values
        :type ydata: npt.NDArray[np.float64]
        :param bins: number of bins (if sizes is False) or size of bins (if sizes is True); a list from the controls, or None to estimate
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or counts (False)
        :type sizes: bool
        :return: bin-center x values, bin-center y values, and the log2-scaled 2-D histogram counts
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
        :raises ValueError: if bins is an invalid entry when sizes is False
        """
        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = bins[0]
                    ybins = bins[1]
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = bins[0]
                    ybins = bins[0]
                else:
                    raise ValueError(f"Invalid bin entry: {bins}")
            elif sizes is True:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[1])
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[0])
                else:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
                if xbins <= 1 or ybins <= 1:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
        if bins is None:
            try:
                xbins = self._auto_bins_2d(xdata, len(xdata))
            except OverflowError:
                xbins = int(np.sqrt(len(xdata)))
            try:
                ybins = self._auto_bins_2d(ydata, len(xdata))
            except OverflowError:
                ybins = int(np.sqrt(len(ydata)))

        z, x, y = np.histogram2d(xdata, ydata, bins=[int(xbins), int(ybins)])
        logged_z = np.empty_like(z)
        for i in range(z.shape[0]):
            for j in range(z.shape[1]):
                logged_z[i, j] = np.log2(z[i, j]) if z[i, j] > 0 else -1

        x = x[:-1] + np.diff(x) / 2.0
        y = y[:-1] + np.diff(y) / 2.0

        return x, y, logged_z.T

    @log(logger=logger)
    def _resolve_1d_bins(
        self,
        data: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> int:
        """
        Decide a 1-D bin count from the user's request, falling back to the data.

        ``bins`` is a count when ``sizes`` is False and a bin *width* when it is True,
        in which case the span comes from the shared histogram limits rather than from
        this dataset - that is what keeps overlaid datasets on the same bin edges. A
        width that yields one bin or fewer is discarded and the automatic rule used
        instead, which is the behaviour the density path had.

        :param data: the filtered values to be binned
        :type data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin size (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit across overlaid datasets, if known
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit across overlaid datasets, if known
        :type hist_max: Optional[float]
        :return: the number of bins
        :rtype: int
        """
        numbins = 0
        if bins is not None:
            if sizes is False:
                return int(bins)
            try:
                if hist_max is not None and hist_min is not None:
                    numbins = int((hist_max - hist_min) / bins)
                else:
                    bins = None
                    numbins = 0
            except TypeError:
                bins = None
                numbins = 0
            if numbins <= 1:
                bins = None
        if bins is None:
            try:
                numbins = self._auto_bins_1d(data)
            except OverflowError:
                numbins = 100
        return numbins

    @log(logger=logger)
    def kernel_density(
        self,
        data: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Estimate one dataset's kernel density, evaluated across its own range.

        The evaluated curve comes back with the positions, rather than the estimator
        itself, so the View needs no scipy to draw it. The View used to call the
        estimator three times on the same points - once to plot, once to shade, once
        to cache - and gets one array now.

        :param data: the filtered values
        :type data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin size (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit across overlaid datasets, if known
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit across overlaid datasets, if known
        :type hist_max: Optional[float]
        :return: the positions the density was evaluated at, and the density there
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        numbins = self._resolve_1d_bins(data, bins, sizes, hist_min, hist_max)
        density = stats.kde.gaussian_kde(data.T)
        x = np.linspace(np.min(data), np.max(data), numbins)
        return x, density(x)

    @log(logger=logger)
    def logscale_and_filter_datasets(
        self, datasets: Sequence[npt.NDArray[Any]], logscale: bool
    ) -> List[npt.NDArray[np.float64]]:
        """
        Filter and log-scale each overlaid dataset on its own.

        The columns *within* one plot are filtered together, because a row dropped
        for one axis has to go for all of them. Overlaid datasets are different
        subsets of different lengths, so each is filtered by itself - handing them
        to :meth:`logscale_and_filter_columns` together would mask them against one
        another and fail on the first pair whose lengths differ.

        :param datasets: one raw column array per overlaid dataset
        :type datasets: Sequence[npt.NDArray[Any]]
        :param logscale: log-scale the values before they are binned?
        :type logscale: bool
        :return: the surviving values, one array per dataset and in the same order
        :rtype: List[npt.NDArray[np.float64]]
        """
        return [
            self.logscale_and_filter_columns(dataset, log_flags=[logscale])[0]
            for dataset in datasets
        ]

    @log(logger=logger)
    def widen_shared_limits(
        self,
        values: npt.NDArray[np.float64],
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> Tuple[float, float]:
        """
        Stretch the limits the overlay is binned against to take one more dataset.

        The limits describe the *filtered* values, which is what is drawn, and they
        only ever widen: a dataset lying inside the range already accumulated leaves
        it alone, so every overlaid subset stays on comparable bins.

        :param values: the newest dataset's filtered values
        :type values: npt.NDArray[np.float64]
        :param hist_min: the lower limit so far, or None for the first dataset
        :type hist_min: Optional[float]
        :param hist_max: the upper limit so far, or None for the first dataset
        :type hist_max: Optional[float]
        :return: the widened lower and upper limits
        :rtype: Tuple[float, float]
        """
        low = float(np.min(values))
        high = float(np.max(values))
        if hist_min is None or low < hist_min:
            hist_min = low
        if hist_max is None or high > hist_max:
            hist_max = high
        return hist_min, hist_max

    @log(logger=logger)
    def kernel_densities(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]:
        """
        Estimate the kernel density of every overlaid dataset in one call.

        The density plot redraws every accumulated dataset on each update, so the
        loop runs here rather than round-tripping per dataset and parking each
        answer on the widget.

        :param datasets: one filtered array per overlaid dataset
        :type datasets: Sequence[npt.NDArray[np.float64]]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin size (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit across overlaid datasets, if known
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit across overlaid datasets, if known
        :type hist_max: Optional[float]
        :return: one (positions, density) pair per dataset, index-aligned with them
        :rtype: List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        """
        return [
            self.kernel_density(data, bins, sizes, hist_min, hist_max)
            for data in datasets
        ]

    @log(logger=logger)
    def histogram_bin_edges(
        self,
        all_data: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        hist_min: float,
        hist_max: float,
    ) -> Tuple[
        npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
    ]:
        """
        Choose one set of bin edges for every overlaid histogram dataset.

        The count is decided from all the overlaid data at once and the edges span
        the shared limits, which is what puts every dataset on the same bins and lets
        them be compared.

        The histogram path used to coerce the bin width with ``float()`` inside a
        bare ``except Exception`` where the density path divided directly inside an
        ``except TypeError``. The two differ only for a width of zero or a
        non-numeric one, and the controls refuse both - ``validate_inputs`` disables
        the plot button on ``bin_value <= 0`` or a value ``float()`` rejects - so
        :meth:`_resolve_1d_bins` serves both and no behaviour changes.

        :param all_data: every overlaid dataset's filtered values, concatenated
        :type all_data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin size (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit across overlaid datasets
        :type hist_min: float
        :param hist_max: the shared upper limit across overlaid datasets
        :type hist_max: float
        :return: the bin edges, the bin centers, and the bin widths
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        numbins = self._resolve_1d_bins(all_data, bins, sizes, hist_min, hist_max)

        # A single bin is not a histogram, and zero would make linspace degenerate.
        if numbins < 2:
            numbins = 2

        bin_edges = np.linspace(hist_min, hist_max, numbins + 1)
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        widths = np.diff(bin_edges)
        return bin_edges, bincenters, widths

    @log(logger=logger)
    def overlaid_histograms(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        bins: Any,
        sizes: bool,
        hist_min: float,
        hist_max: float,
        norm: bool,
    ) -> Tuple[
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        List[npt.NDArray[np.float64]],
    ]:
        """
        Bin every overlaid dataset onto one shared set of edges, and count them.

        The bin decision was already here; Step 4's closeout brought the counting down
        to join it. Tallying values into bins is aggregation, and the counts are
        exported with the plot, so the widget should not be doing it - the comment that
        used to say the counting "stays with the drawing" was reasoning from which
        import it needed rather than from whose responsibility it is.

        The edges come from all the overlaid data at once, which is what puts every
        dataset on comparable bins; the counts are then per dataset so each draws its
        own bars.

        :param datasets: one filtered array per overlaid dataset
        :type datasets: Sequence[npt.NDArray[np.float64]]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit across overlaid datasets
        :type hist_min: float
        :param hist_max: the shared upper limit across overlaid datasets
        :type hist_max: float
        :param norm: express each dataset as a fraction of itself rather than a count
        :type norm: bool
        :return: the bin edges, the bin centers, the bin widths, and one count array per dataset
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64], List[npt.NDArray[np.float64]]]
        """
        all_data = np.concatenate(list(datasets)) if len(datasets) > 1 else datasets[0]
        bin_edges, bincenters, widths = self.histogram_bin_edges(
            all_data, bins, sizes, hist_min, hist_max
        )

        counts: List[npt.NDArray[np.float64]] = []
        for data in datasets:
            val, _ = np.histogram(data, bins=bin_edges)
            val = val.astype(float)
            if norm:
                total = np.sum(val)
                if total > 0:
                    val /= total
            counts.append(val)
        return bin_edges, bincenters, widths, counts

    @log(logger=logger)
    def _log_exp_pdf(
        self,
        logt: npt.NDArray[np.float64],
        rate: float,
        amplitude: float,
    ) -> npt.NDArray[np.float64]:
        """
        An exponential inter-event time distribution, in log-time coordinates.

        The model ``curve_fit`` is handed. Capture is Poisson, so inter-event times
        are exponential; binning their base-10 logarithm carries a Jacobian of
        ``ln(10) * 10**logt``, which is why that factor appears here rather than in
        the caller.

        :param logt: the base-10 logarithm of the inter-event times
        :type logt: npt.NDArray[np.float64]
        :param rate: the capture rate in Hz
        :type rate: float
        :param amplitude: the scale factor fitting the distribution to the counts
        :type amplitude: float
        :return: the modelled counts at each logt
        :rtype: npt.NDArray[np.float64]
        """
        return amplitude * np.exp(-rate * 10.0**logt) * 10.0**logt * np.log(10)

    @log(logger=logger)
    def categorical_counts(
        self, datasets: Sequence[npt.NDArray[Any]]
    ) -> List[Tuple[List[str], npt.NDArray[np.float64]]]:
        """
        Tally how often each category occurs, for every overlaid dataset at once.

        Moved off ``MetadataView`` in Step 4's closeout. Counting occurrences is
        aggregation rather than drawing, and the tallies are exported with the plot.
        The loop is here rather than a round trip per dataset, for the reason
        :meth:`kernel_densities` records: the bar chart redraws every accumulated
        dataset on each update.

        **Missing values are counted as their own category** rather than being allowed
        to reach ``np.unique``, which sorts and so raises "'<' not supported between
        instances of 'NoneType' and 'str'" on a column holding SQL NULLs. A float
        column does not raise but labels the bar "nan", which tells the user no more
        than "null" does and does not match what they see elsewhere. Counting them
        separately also keeps the real categories in the order they had before, which
        stringifying everything up front would not: "10" sorts before "2".

        **The bars come back largest first**, so the tallest is drawn on the left.
        The order is decided from the total across *every* overlaid dataset rather
        than per dataset, because matplotlib takes a category axis's order from the
        first series drawn: ordering each dataset by its own counts would leave only
        the first one looking sorted. Ties keep the order the tally gave them, which
        is the numeric order for a numeric column.

        :param datasets: one array of raw column values per overlaid dataset
        :type datasets: Sequence[npt.NDArray[Any]]
        :return: per dataset, its category names and their counts as floats
        :rtype: List[Tuple[List[str], npt.NDArray[np.float64]]]
        """
        results: List[Tuple[List[str], npt.NDArray[np.float64]]] = []
        for values in datasets:
            series = pd.Series(values)
            missing = int(series.isna().sum())
            present = series.dropna().to_numpy()

            unique_vals, counts = np.unique(present, return_counts=True)
            val = counts.astype(float)

            # Strings so matplotlib aligns them as discrete categories.
            categories = [str(uv) for uv in unique_vals]

            if missing:
                categories.append("null")
                val = np.append(val, float(missing))

            results.append((categories, val))

        totals: Dict[str, float] = {}
        for categories, val in results:
            for category, count in zip(categories, val, strict=True):
                totals[category] = totals.get(category, 0.0) + float(count)

        # sorted() is stable and `totals` is in first-seen order, so a tie between
        # two categories leaves them as the tally had them.
        rank = {
            category: position
            for position, category in enumerate(
                sorted(totals, key=lambda name: -totals[name])
            )
        }

        ordered: List[Tuple[List[str], npt.NDArray[np.float64]]] = []
        for categories, val in results:
            order = np.argsort([rank[name] for name in categories], kind="stable")
            ordered.append(([categories[i] for i in order], val[order]))
        return ordered

    @log(logger=logger)
    def interevent_log_times(
        self, times: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """
        Turn a column of event times into the log10 inter-event times to fit.

        Capture is Poisson, so the quantity the capture-rate fit is about is the gap
        between consecutive events rather than the times themselves; the fit then works
        in log-time, which is why :meth:`_log_exp_pdf` carries a Jacobian. Sorting first
        makes the gaps meaningful for a column that arrived in any order.

        Non-positive intervals are dropped because ``log10`` has nothing to say about
        them - two events sharing a timestamp produce a zero gap.

        :param times: the event times, in any order
        :type times: npt.NDArray[np.float64]
        :return: the base-10 logarithm of the positive inter-event times
        :rtype: npt.NDArray[np.float64]
        """
        intervals = np.diff(np.sort(times))
        return np.log10(intervals[intervals > 0])

    @log(logger=logger)
    def fit_capture_rate(
        self, data: npt.NDArray[np.float64], bins: Any, sizes: bool = False
    ) -> Tuple[
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        float,
        float,
    ]:
        """
        Bin log inter-event times, fit an exponential to them, and report the rate.

        The bin edges come back so the View can draw the histogram on exactly the
        edges the fit was made against, rather than on its own binning of the same
        request. The counts come back for the same reason.

        This path answers an overflow in the automatic bin rule with Sturges'
        expression rather than the 100 bins the density and histogram paths use,
        which is why it does not share :meth:`_resolve_1d_bins`.

        :param data: the base-10 logarithm of the inter-event times
        :type data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate one
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :return: bin edges, bin centers, counts, the fitted curve, the rate in Hz, and its error
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64], float, float]
        """
        if bins is not None and sizes:
            # A width in the data's own units, which are log10 seconds - so a width
            # in decades. There are no shared histogram limits on this path, because
            # the inter-event times are derived here rather than carried between
            # overlaid datasets, so the span is this data's own.
            span = float(np.max(data) - np.min(data))
            numbins = int(span / bins) if bins else 0
            if numbins <= 1:
                bins = None

        if bins is None:
            try:
                numbins = self._auto_bins_1d(data)
            except OverflowError:
                numbins = int(3.332 * np.log10(len(data)))
        elif not sizes:
            numbins = int(bins)

        counts, bin_edges = np.histogram(data, bins=numbins)
        val = counts.astype(float)
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0

        rate_guess = 1.0 / (10 ** bincenters[np.argmax(val)])
        amp_guess = np.max(val) / (np.log(10) / (rate_guess * np.exp(1)))
        p0 = [rate_guess, amp_guess]

        popt, pcov = curve_fit(self._log_exp_pdf, bincenters, val, p0=p0)
        rate = popt[0]
        amp = popt[1]
        error = -t.isf(0.975, len(val)) * np.sqrt(np.diag(pcov))[0]

        fit = self._log_exp_pdf(bincenters, rate, amp)
        return bin_edges, bincenters, val, fit, float(rate), float(error)



    @log(logger=logger)
    def _rectify_event_current(
        self,
        timeseries: npt.NDArray[np.float64],
        padding_before: int,
    ) -> npt.NDArray[np.float64]:
        """
        Subtract an event's own baseline from it and orient the blockage positive.

        The baseline is the median of the samples preceding the event, and
        multiplying through by its sign makes a negative-baseline trace read the
        same way as a positive-baseline one, so events recorded at either polarity
        can share a histogram or an overlay.

        :param timeseries: one event's raw or filtered samples
        :type timeseries: npt.NDArray[np.float64]
        :param padding_before: how many leading samples are pre-event baseline
        :type padding_before: int
        :return: the baseline-subtracted, sign-corrected samples
        :rtype: npt.NDArray[np.float64]
        """
        baseline = np.median(timeseries[:padding_before])
        return np.sign(baseline) * timeseries - np.sign(baseline) * baseline

    @log(logger=logger)
    def _event_timeseries(
        self, event: Dict[str, Any], plot_type: str
    ) -> Tuple[npt.NDArray[np.float64], int]:
        """
        Pick the raw or the filtered samples of one event, with its padding.

        Which of the two an event-data plot wants is encoded in its name, and the
        padding the loader reports is in microseconds while every consumer here
        counts samples.

        :param event: one event's payload as the loader yields it
        :type event: Dict[str, Any]
        :param plot_type: the event-data plot type being drawn
        :type plot_type: str
        :return: the chosen samples and the pre-event padding in samples
        :rtype: Tuple[npt.NDArray[np.float64], int]
        :raises ValueError: if plot_type names neither the raw nor the filtered trace
        """
        if plot_type in [
            "Raw All Points Histogram",
            "Normalized Raw All Points Histogram",
            "Raw Event Overlay",
        ]:
            timeseries = event["raw_data"]
        elif plot_type in [
            "Filtered All Points Histogram",
            "Normalized Filtered All Points Histogram",
            "Filtered Event Overlay",
        ]:
            timeseries = event["filtered_data"]
        else:
            raise ValueError(f"Unknown plot_type {plot_type!r}")

        padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
        return timeseries, padding_before

    @log(logger=logger)
    def build_all_points_histogram(
        self,
        event_generator: Generator,
        plot_type: str,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], float, float]:
        """
        Tally every sample of every event in a subset into one shared histogram.

        The generator is walked twice, because the bins cannot be chosen until the
        extremes across all the events are known: the first pass takes the limits and
        the second counts into the edges they decide. The limits widen the shared ones
        the caller is already holding, so overlaid subsets stay on comparable bins.

        :param event_generator: the events of one subset, as the loader yields them
        :type event_generator: Generator
        :param plot_type: the all-points histogram variant being drawn
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit so far, or None for the first dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit so far, or None for the first dataset
        :type hist_max: Optional[float]
        :return: the bin centers, the counts, and the widened shared limits
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], float, float]
        :raises ValueError: if plot_type is unrecognised, or bins cannot be resolved
        """
        # get global stats from the first event, don't forget to use this one later
        egen1, egen2 = itertools.tee(event_generator)

        min_current = float("inf")
        max_current = float("-inf")
        for event in egen1:
            timeseries, padding_before = self._event_timeseries(event, plot_type)
            rectified = self._rectify_event_current(timeseries, padding_before)

            min_curr = np.min(rectified)
            max_curr = np.max(rectified)
            if min_curr < min_current:
                min_current = min_curr
            if max_curr > max_current:
                max_current = max_curr

        if hist_min is None or min_current < hist_min:
            hist_min = min_current
        if hist_max is None or max_current > hist_max:
            hist_max = max_current

        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 1:
                    bins = bins[0]
                else:
                    raise ValueError(f"Invalid bins entry {bins}")
            else:
                try:
                    bins = int((hist_max - hist_min) / bins[0])
                except Exception as e:
                    raise ValueError(
                        f"Unable to calculate bins given sizes {bins}: {str(e)}"
                    ) from e
        else:
            bins = 100

        bin_edges = np.linspace(hist_min, hist_max, bins + 1)
        hist = np.zeros(bins)
        for event in egen2:
            timeseries, padding_before = self._event_timeseries(event, plot_type)
            event_hist, _ = np.histogram(
                self._rectify_event_current(timeseries, padding_before),
                bins=bin_edges,
            )
            hist += event_hist
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return bincenters, hist, hist_min, hist_max

    @log(logger=logger)
    def build_event_overlay(
        self, event_generator: Generator, plot_type: str
    ) -> List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]:
        """
        Put every event of a subset on one baseline-subtracted, normalised axis.

        Each event's time base runs from its own padding: zero at the start of the
        event and one at its end, so events of different durations lie on top of each
        other and the paddings fall outside ``[0, 1]``.

        :param event_generator: the events of one subset, as the loader yields them
        :type event_generator: Generator
        :param plot_type: either 'Raw Event Overlay' or 'Filtered Event Overlay'
        :type plot_type: str
        :return: one (normalised time, rectified current) pair per event
        :rtype: List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        """
        traces: List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]] = []
        for event in event_generator:
            timeseries, padding_before = self._event_timeseries(event, plot_type)
            padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)

            data = self._rectify_event_current(timeseries, padding_before)
            time = np.array(range(len(data)), dtype=np.float64)
            time -= padding_before
            time /= len(data) - padding_after - padding_before
            traces.append((time, data))
        return traces
