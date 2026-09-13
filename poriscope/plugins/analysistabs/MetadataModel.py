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
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class MetadataModel(MetaModel):
    """
    Subclass of MetaModel for handling metadata-related processing and storage.
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
    def resolve_event_ids(
        self,
        loader: str,
        event_ids: Sequence[int],
        exp_id: Optional[int],
        channel: Optional[int],
    ) -> Optional[pd.DataFrame]:
        """
        Look up the database ids of these ``event_id`` values, within scope.

        Owns the SQL, which Step 4b moved out of the Controller - it assembled the
        query and then used the Model as a conduit to the loader, where Decision A has
        the Model make the plugin call. ``ClusteringModel.drop_cluster_columns`` is
        the same shape.

        **The scope is why this query exists at all.** ``event_id`` is unique only
        within an experiment and channel, so an unscoped match returns whichever
        channel's row happens to share the number. The caller stops rather than
        widening the query when it cannot resolve an experiment; that guard stays
        there, because it is the half that has something to tell the user.

        ``DECISIONS.md`` (2026-08-25) accepts the f-string interpolation: the database
        is a local file owned by the user running the app. This is about *where* the
        SQL lives.

        :param loader: the database loader's plugin key
        :type loader: str
        :param event_ids: the event_id values to resolve
        :type event_ids: Sequence[int]
        :param exp_id: the experiment's database id, or None to leave it out of scope
        :type exp_id: Optional[int]
        :param channel: the channel to scope to, or None for all channels
        :type channel: Optional[int]
        :return: the matching rows, or None if the loader had nothing to say
        :rtype: Optional[pd.DataFrame]
        """
        id_list = ",".join(str(eid) for eid in event_ids)
        where_parts = [f"event_id IN ({id_list})"]

        if exp_id is not None:
            where_parts.append(f"experiment_id = {exp_id}")
        if channel is not None:
            where_parts.append(f"channel_id = {channel}")

        query = f"SELECT id FROM events WHERE {' AND '.join(where_parts)}"
        result: Optional[pd.DataFrame] = self.call(
            "MetaDatabaseLoader", loader, "query_database_directly", query
        )
        return result

    @log(logger=logger)
    def load_events_by_id(
        self,
        loader: str,
        db_ids: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> Optional[Generator]:
        """
        Load exactly the rows named by their database ids.

        The ``e.id IN (...)`` clause is a WHERE-clause body, which is what
        ``load_event_data`` takes - it splices it in after its own ``WHERE``. Step 4b
        moved it here with the query that produced the ids.

        :param loader: the database loader's plugin key
        :type loader: str
        :param db_ids: the comma-separated primary keys to load
        :type db_ids: str
        :param experiments_and_channels: the scope handed on to the loader
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: a generator over the matching events, or None
        :rtype: Optional[Generator]
        """
        generator: Optional[Generator] = self.call(
            "MetaDatabaseLoader",
            loader,
            "load_event_data",
            f"e.id IN ({db_ids})",
            experiments_and_channels,
        )
        return generator
