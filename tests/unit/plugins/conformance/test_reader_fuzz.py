"""
Fuzz / malformed-input testing for every discovered ``MetaReader``.

Readers parse arbitrary externally-produced files; none of the other checks in this
suite exercise one against anything but a well-formed synthetic recording, so a
malformed one - truncated, a corrupted header, a missing sidecar - could crash or
hang instead of raising a caught exception. This module drives each reader over a
small, fixed set of deterministic mutations of its own valid fixture
(``MUTATIONS`` in ``_recipes.py``) rather than open-ended fuzzing, to keep CI
reproducible and non-flaky.

Three tiers are asserted, in order of how much the mutation lets the reader get:

1. Construction (``apply_settings``) either succeeds or raises a caught
   ``Exception`` subclass - never hangs, never raises something uncatchable.
2. If construction succeeds, ``get_channel_length()`` must be internally
   consistent with what ``load_data`` can actually deliver: requesting exactly
   that many samples must succeed and return exactly that many.
3. Requesting one more sample than ``get_channel_length()`` reports must raise
   ``ValueError`` (``MetaReader.load_data``'s documented bounds check).

**What this deliberately does not assert.** Which exception type tier 1 raises is
unconstrained. Measured directly across the mutations here: a 0-byte file alone
already produces four different exception families depending on reader and
format - ``ValueError`` (most readers, from an empty ``numpy.memmap``),
``json.decoder.JSONDecodeError`` (``ChimeraReader20240101``'s embedded-header
parse, itself a ``ValueError`` subclass), ``struct.error`` (both ABF2 readers,
*not* a ``ValueError`` subclass), and a missing sidecar file raises
``FileNotFoundError`` or ``OSError`` depending on the reader. None of that is a
defect this suite should paper over by asserting a specific type it does not
have - if every reader should converge on one exception contract for malformed
input, that is a design question for whoever owns each reader family
(``@shadowk29`` per ``CODEOWNERS``), not something to decide here. Same reasoning
for a reader with a sidecar file: neither ``ChimeraReader20240501`` nor
``ChimeraReaderVC100`` attempts to degrade gracefully when its sidecar is
missing today (both raise cleanly), and this suite does not assert that they
must keep doing so - only that they do not hang or crash uncaught either way.
"""

from typing import List, Tuple, Type

import pytest

from poriscope.utils.MetaReader import MetaReader
from tests.unit.plugins.conformance._recipes import (
    MUTATIONS,
    build_any_reader,
    build_reader_dataset,
    discover_concrete,
)

READERS: List[Type[MetaReader]] = discover_concrete(MetaReader)

MUTATION_CASES: List[Tuple[Type[MetaReader], str]] = [
    (cls, mutation_name)
    for cls in READERS
    for mutation_name, _ in MUTATIONS.get(cls.__name__, [])
]


@pytest.mark.conformance
@pytest.mark.parametrize(
    "reader_cls,mutation_name",
    MUTATION_CASES,
    ids=[f"{cls.__name__}-{name}" for cls, name in MUTATION_CASES],
)
def test_reader_survives_malformed_input(
    reader_cls: Type[MetaReader], mutation_name: str, tmp_path_factory
) -> None:
    """
    A reader never hangs or crashes uncaught on a mutated copy of its own fixture.

    :param reader_cls: The reader class under test.
    :type reader_cls: Type[MetaReader]
    :param mutation_name: Name of the mutation applied, from ``MUTATIONS``.
    :type mutation_name: str
    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    """
    out_dir = tmp_path_factory.mktemp(f"{reader_cls.__name__}_{mutation_name}")
    dataset = build_reader_dataset(reader_cls, out_dir)

    mutations = dict(MUTATIONS[reader_cls.__name__])
    mutations[mutation_name](dataset)

    try:
        reader = build_any_reader(reader_cls, dataset)
    except Exception:
        return  # Tier 1: a caught exception during construction is acceptable.

    try:
        channel = dataset.channel
        samplerate = reader.get_samplerate()
        length_samples = reader.get_channel_length(channel)
        exact_length_s = length_samples / samplerate

        # Tier 2: get_channel_length must agree with what load_data can deliver.
        exact = reader.load_data(0.0, exact_length_s, channel)
        assert exact.size == length_samples, (
            f"{reader_cls.__name__} ({mutation_name}): get_channel_length reported "
            f"{length_samples} but load_data for exactly that span returned "
            f"{exact.size}"
        )

        # Tier 3: over-requesting must raise, not silently return less. Two
        # samples of margin, not one: load_data itself computes
        # int(length * samplerate), and length_samples/samplerate + 1/samplerate
        # can round to fractionally under length_samples + 1 (confirmed directly:
        # 1000000/4000000 + 1/4000000 * 4000000 == 1000000.9999999999, which
        # truncates to 1000000, not 1000001) - one sample of margin is not
        # reliably enough to land past the boundary once float error is folded
        # back in; two is.
        over_length_s = (length_samples + 2) / samplerate
        with pytest.raises(ValueError):
            reader.load_data(0.0, over_length_s, channel)
    finally:
        reader.close_resources()


@pytest.mark.conformance
def test_every_reader_has_at_least_one_mutation() -> None:
    """Guard against a reader silently having no fuzz coverage at all."""
    missing = [cls.__name__ for cls in READERS if not MUTATIONS.get(cls.__name__)]
    assert not missing, (
        f"no fuzz mutations for {missing}. MUTATIONS is derived from "
        f"READER_DATASET_BUILDERS' own keys in _recipes.py, so this means the reader "
        f"has no conformance fixture at all - add it there and it picks up the shared "
        f"mutations automatically. Add a format-specific mutation only if its format "
        f"carries a structural marker (a signature, an embedded header, a sidecar) "
        f"the shared truncation set would not otherwise corrupt."
    )
