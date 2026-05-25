"""Unit tests for MetaEventFitter abstract base class."""

from typing import Any, Callable, Dict, List, Optional, Type, Union

import numpy as np
import numpy.typing as npt
import pytest

from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader


class MockEventLoader(MetaEventLoader):
    """Mock MetaEventLoader for testing."""

    def __init__(self) -> None:
        """Initialize mock event loader without calling parent __init__."""
        self.samplerate = {0: 10000.0, 1: 10000.0}
        self.channels = [0, 1]
        self.num_events = {0: 10, 1: 10}
        self.events: Dict[int, Dict[int, dict]] = {0: {}, 1: {}}

        # Populate mock events
        for ch in self.channels:
            for i in range(self.num_events[ch]):
                self.events[ch][i] = {
                    "data": np.random.randn(1000) * 10 + 100,
                    "absolute_start": i * 10000,
                    "padding_before": 100,
                    "padding_after": 100,
                    "baseline_mean": 100.0,
                    "baseline_std": 10.0,
                }

    def get_samplerate(self, channel: int) -> float:
        return self.samplerate[channel]

    def get_channels(self) -> List[int]:
        return self.channels

    def get_num_events(self, channel: int) -> int:
        return self.num_events[channel]

    def load_event(
        self, channel: int, index: int, data_filter: Optional[Callable] = None
    ) -> dict:
        """Load mock event."""
        if index >= self.num_events[channel]:
            raise IndexError(f"Event {index} out of range")
        event = self.events[channel][index].copy()
        if data_filter:
            event["data"] = data_filter(event["data"])
        return event

    def force_serial_channel_operations(self) -> bool:
        return False

    # Required abstract method implementations
    def _init(self) -> None:
        pass

    def _validate_settings(self, settings: dict) -> None:
        pass

    def _finalize_initialization(self) -> None:
        pass

    def reset_channel(self, channel: Optional[int] = None) -> None:
        pass

    def close_resources(self, channel: Optional[int] = None) -> None:
        pass

    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        return {}

    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
        return ""

    def get_valid_indices(self, channel: int) -> List[int]:
        """Get valid event indices for a channel."""
        return list(range(self.num_events[channel]))


class ConcreteEventFitter(MetaEventFitter):
    """Concrete implementation of MetaEventFitter for testing."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """Initialize concrete event fitter."""
        super().__init__(settings)

    def close_resources(self, channel: Optional[int] = None) -> None:
        """Close resources."""
        pass

    def _init(self) -> None:
        """Initialize."""
        pass

    def _validate_param_types(self, settings: dict) -> None:
        """Override to skip strict type checking for testing."""
        # Call parent's parent to skip MetaEventFitter's strict check
        # but still allow initialization to proceed
        from poriscope.utils.BaseDataPlugin import BaseDataPlugin

        BaseDataPlugin._validate_param_types(self, settings)

    def construct_fitted_event(
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
        """Construct fitted event - simple step function."""
        if not self.get_eventfitting_status(channel):
            return None

        # Get event length
        length = self.event_lengths[channel][index]
        sublevel_starts = self.sublevel_starts[channel][index]

        # Build step function
        fitted = np.zeros(length)
        for i in range(len(sublevel_starts) - 1):
            start = sublevel_starts[i]
            end = sublevel_starts[i + 1]
            # Use mean current for this sublevel
            fitted[start:end] = self.sublevel_metadata[channel][index][
                "sublevel_current"
            ][i]

        return fitted

    def _pre_process_events(self, channel: int) -> None:
        """Pre-process events."""
        pass

    def _locate_sublevel_transitions(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        padding_before: Optional[int],
        padding_after: Optional[int],
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
    ) -> Optional[List[int]]:
        """Locate sublevel transitions - simple threshold-based."""
        if baseline_mean is None or baseline_std is None:
            raise ValueError("Missing baseline statistics")

        # Find simple step changes
        threshold = 2 * baseline_std
        diff = np.abs(np.diff(data))
        transitions = [0]  # Start with beginning of data

        # Add transitions where change exceeds threshold
        for i in np.where(diff > threshold)[0]:
            if i - transitions[-1] > 10:  # Minimum spacing
                transitions.append(int(i))

        # Always add the end
        transitions.append(len(data))

        return transitions

    def _populate_sublevel_metadata(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_starts: List[int],
    ) -> Dict[str, npt.NDArray[Any]]:
        """Populate sublevel metadata."""
        num_levels = len(sublevel_starts) - 1
        metadata: Dict[str, npt.NDArray[Any]] = {}

        metadata["sublevel_current"] = np.zeros(num_levels)
        metadata["sublevel_stdev"] = np.zeros(num_levels)
        metadata["sublevel_duration"] = np.zeros(num_levels)

        for i in range(num_levels):
            start = sublevel_starts[i]
            end = sublevel_starts[i + 1]
            segment = data[start:end]

            metadata["sublevel_current"][i] = np.mean(segment)
            metadata["sublevel_stdev"][i] = np.std(segment)
            metadata["sublevel_duration"][i] = (end - start) / samplerate * 1e6  # us

        return metadata

    def _define_event_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """Define event metadata types."""
        return {
            "duration": float,
            "max_blockage": float,
            "min_blockage": float,
        }

    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """Define event metadata units."""
        return {
            "duration": "us",
            "max_blockage": "pA",
            "min_blockage": "pA",
        }

    def _define_sublevel_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """Define sublevel metadata types."""
        return {
            "sublevel_current": float,
            "sublevel_stdev": float,
            "sublevel_duration": float,
        }

    def _define_sublevel_metadata_units(self) -> Dict[str, Optional[str]]:
        """Define sublevel metadata units."""
        return {
            "sublevel_current": "pA",
            "sublevel_stdev": "pA",
            "sublevel_duration": "us",
        }

    def _validate_settings(self, settings: dict) -> None:
        """Validate settings."""
        if "MetaEventLoader" not in settings:
            raise ValueError("MetaEventLoader is required")

    def _populate_event_metadata(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_metadata: Dict[str, List[Any]],
    ) -> Dict[str, Union[int, float, str, bool]]:
        """Populate event metadata."""
        return {
            "duration": float(np.sum(sublevel_metadata["sublevel_duration"])),
            "max_blockage": float(np.max(sublevel_metadata["sublevel_current"])),
            "min_blockage": float(np.min(sublevel_metadata["sublevel_current"])),
        }

    def _post_process_events(self, channel: int) -> None:
        """Post-process events."""
        pass


class TestMetaEventFitter:
    """Test suite for MetaEventFitter class."""

    @pytest.fixture
    def mock_loader(self) -> MockEventLoader:
        """Create a mock event loader."""
        return MockEventLoader()

    @pytest.fixture
    def settings(self, mock_loader: MockEventLoader) -> Dict[str, Any]:
        """Create valid settings."""
        return {
            "MetaEventLoader": {"Type": str, "Value": mock_loader},
        }

    @pytest.fixture
    def fitter(self, settings: Dict[str, Any]) -> ConcreteEventFitter:
        """Create a concrete event fitter."""
        fitter = ConcreteEventFitter(settings=settings)
        # Manually set eventloader since _validate_param_types override breaks the chain
        fitter.eventloader = settings["MetaEventLoader"]["Value"]
        return fitter

    def test_init(self, fitter: ConcreteEventFitter) -> None:
        """Test initialization."""
        assert fitter is not None
        assert fitter.event_metadata == {}
        assert fitter.sublevel_metadata == {}
        assert fitter.eventloader is not None

    def test_close_resources(self, fitter: ConcreteEventFitter) -> None:
        """Test closing resources."""
        fitter.close_resources()
        fitter.close_resources(channel=0)

    def test_force_serial_channel_operations(self, fitter: ConcreteEventFitter) -> None:
        """Test force serial channel operations."""
        assert fitter.force_serial_channel_operations() is False

    def test_get_samplerate(self, fitter: ConcreteEventFitter) -> None:
        """Test getting sample rate."""
        assert fitter.get_samplerate(0) == 10000.0

    def test_get_channels(self, fitter: ConcreteEventFitter) -> None:
        """Test getting channels."""
        assert fitter.get_channels() == [0, 1]

    def test_get_empty_settings_standalone(self, fitter: ConcreteEventFitter) -> None:
        """Test getting empty settings in standalone mode."""
        settings = fitter.get_empty_settings(standalone=True)
        assert "MetaEventLoader" in settings

    def test_get_empty_settings_with_plugins(self, fitter: ConcreteEventFitter) -> None:
        """Test getting empty settings with plugins."""
        plugins = {"MetaEventLoader": ["Loader1", "Loader2"]}
        settings = fitter.get_empty_settings(globally_available_plugins=plugins)
        assert "MetaEventLoader" in settings
        assert settings["MetaEventLoader"]["Options"] == ["Loader1", "Loader2"]

    def test_get_empty_settings_no_loaders(self) -> None:
        """Test getting empty settings with no loaders raises error."""
        fitter = ConcreteEventFitter.__new__(ConcreteEventFitter)
        plugins: Dict[str, List[str]] = {"MetaEventLoader": []}
        with pytest.raises(KeyError, match="Cannot instantiate"):
            fitter.get_empty_settings(globally_available_plugins=plugins)

    def test_reset_channel(self, fitter: ConcreteEventFitter) -> None:
        """Test resetting a channel."""
        fitter.event_metadata[0] = {0: {"test": 1}}
        fitter.sublevel_metadata[0] = {0: {"test": 1}}
        fitter.reset_channel(0)
        assert 0 not in fitter.event_metadata
        assert 0 not in fitter.sublevel_metadata

    def test_get_metadata_columns_not_fitted(self, fitter: ConcreteEventFitter) -> None:
        """Test getting metadata columns before fitting."""
        with pytest.raises(RuntimeError, match="Fitting has not finished"):
            fitter.get_metadata_columns(0)

    def test_get_sublevel_columns_not_fitted(self, fitter: ConcreteEventFitter) -> None:
        """Test getting sublevel columns before fitting."""
        with pytest.raises(RuntimeError, match="Fitting has not finished"):
            fitter.get_sublevel_columns(0)

    def test_get_event_metadata_types(self, fitter: ConcreteEventFitter) -> None:
        """Test getting event metadata types."""
        types = fitter.get_event_metadata_types()
        assert "duration" in types
        assert "start_time" in types
        assert types["duration"] is float

    def test_get_event_metadata_units(self, fitter: ConcreteEventFitter) -> None:
        """Test getting event metadata units."""
        units = fitter.get_event_metadata_units()
        assert "duration" in units
        assert units["duration"] == "us"
        assert units["start_time"] == "s"

    def test_get_sublevel_metadata_types(self, fitter: ConcreteEventFitter) -> None:
        """Test getting sublevel metadata types."""
        types = fitter.get_sublevel_metadata_types()
        assert "sublevel_current" in types
        assert types["sublevel_current"] is float

    def test_get_sublevel_metadata_units(self, fitter: ConcreteEventFitter) -> None:
        """Test getting sublevel metadata units."""
        units = fitter.get_sublevel_metadata_units()
        assert "sublevel_current" in units
        assert units["sublevel_current"] == "pA"

    def test_get_eventfitting_status(self, fitter: ConcreteEventFitter) -> None:
        """Test getting eventfitting status."""
        assert fitter.get_eventfitting_status(0) is False
        fitter.eventfitting_status[0] = True
        assert fitter.get_eventfitting_status(0) is True

    def test_get_num_events_not_fitted(self, fitter: ConcreteEventFitter) -> None:
        """Test getting number of events before fitting."""
        with pytest.raises(RuntimeError, match="not complete"):
            fitter.get_num_events(0)

    def test_fit_events_success(self, fitter: ConcreteEventFitter) -> None:
        """Test successfully fitting events."""
        gen = fitter.fit_events(0, indices=[0, 1])
        progress = list(gen)
        assert len(progress) > 0
        assert progress[-1] == 1.0
        assert fitter.eventfitting_status[0] is True
        assert len(fitter.event_metadata[0]) > 0

    def test_fit_events_with_filter(self, fitter: ConcreteEventFitter) -> None:
        """Test fitting events with data filter."""

        def simple_filter(data: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
            return data * 2

        gen = fitter.fit_events(0, data_filter=simple_filter, indices=[0])
        list(gen)  # Consume generator
        assert fitter.eventfitting_status[0] is True

    def test_fit_events_silent(self, fitter: ConcreteEventFitter) -> None:
        """Test fitting events in silent mode."""
        gen = fitter.fit_events(0, silent=True, indices=[0])
        progress = list(gen)
        # Silent mode still yields final 1.0
        assert progress[-1] == 1.0

    def test_get_metadata_columns_after_fitting(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test getting metadata columns after fitting."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)
        columns = fitter.get_metadata_columns(0)
        assert "duration" in columns
        assert "start_time" in columns

    def test_get_sublevel_columns_after_fitting(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test getting sublevel columns after fitting."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)
        columns = fitter.get_sublevel_columns(0)
        assert "sublevel_current" in columns

    def test_get_num_events_after_fitting(self, fitter: ConcreteEventFitter) -> None:
        """Test getting number of events after fitting."""
        gen = fitter.fit_events(0, indices=[0, 1])
        list(gen)
        num = fitter.get_num_events(0)
        assert num >= 0

    def test_get_single_event_metadata_not_fitted(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test getting single event metadata before fitting."""
        with pytest.raises(RuntimeError, match="not complete"):
            fitter.get_single_event_metadata(0, 0)

    def test_get_single_event_metadata_success(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test successfully getting single event metadata."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)

        event_meta, sublevel_meta, filtered_data, raw_data, fitted_data = (
            fitter.get_single_event_metadata(0, 0)
        )
        assert "duration" in event_meta
        assert "sublevel_current" in sublevel_meta
        assert filtered_data is not None
        assert raw_data is not None
        assert fitted_data is not None

    def test_get_event_metadata_generator(self, fitter: ConcreteEventFitter) -> None:
        """Test getting event metadata generator."""
        gen = fitter.fit_events(0, indices=[0, 1])
        list(gen)

        metadata_gen = fitter.get_event_metadata_generator(0)
        events = list(metadata_gen)
        assert len(events) > 0

    def test_report_channel_status_not_fitted(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test reporting channel status before fitting."""
        status = fitter.report_channel_status(0)
        assert "incomplete" in status

    def test_report_channel_status_fitted(self, fitter: ConcreteEventFitter) -> None:
        """Test reporting channel status after fitting."""
        gen = fitter.fit_events(0, indices=[0, 1])
        list(gen)
        status = fitter.report_channel_status(0)
        assert "good fits" in status

    def test_report_channel_status_init(self, fitter: ConcreteEventFitter) -> None:
        """Test reporting channel status during init."""
        status = fitter.report_channel_status(0, init=True)
        assert status == ""

    def test_report_channel_status_all(self, fitter: ConcreteEventFitter) -> None:
        """Test reporting all channel statuses."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)
        status = fitter.report_channel_status()
        assert "Ch0" in status

    def test_get_plot_features(self, fitter: ConcreteEventFitter) -> None:
        """Test getting plot features."""
        vlines, hlines, points, vlabels, hlabels, plabels = fitter.get_plot_features(0, 0)
        assert vlines is None
        assert hlines is None
        assert points is None
        assert vlabels is None
        assert hlabels is None
        assert plabels is None

    def test_construct_fitted_event_not_fitted(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test constructing fitted event before fitting."""
        fitted = fitter.construct_fitted_event(0, 0)
        assert fitted is None

    def test_construct_fitted_event_success(self, fitter: ConcreteEventFitter) -> None:
        """Test successfully constructing fitted event."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)
        fitted = fitter.construct_fitted_event(0, 0)
        assert fitted is not None
        assert len(fitted) > 0

    def test_get_fitted_event_validates_length(
        self, fitter: ConcreteEventFitter
    ) -> None:
        """Test that get_fitted_event validates returned length."""
        gen = fitter.fit_events(0, indices=[0])
        list(gen)

        # This should work - correct length
        fitted = fitter.get_fitted_event(0, 0)
        assert fitted is not None

    def test_eventloader_not_initialized(self) -> None:
        """Test operations without initialized event loader."""
        fitter = ConcreteEventFitter.__new__(ConcreteEventFitter)
        fitter.eventloader = None
        fitter.eventfitting_status = {}

        with pytest.raises(RuntimeError, match="not been initialized"):
            fitter.get_samplerate(0)

    def test_fit_events_no_loader(self) -> None:
        """Test fitting events without loader."""
        fitter = ConcreteEventFitter.__new__(ConcreteEventFitter)
        fitter.eventloader = None

        gen = fitter.fit_events(0)
        with pytest.raises(RuntimeError, match="not been initialized"):
            next(gen)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
