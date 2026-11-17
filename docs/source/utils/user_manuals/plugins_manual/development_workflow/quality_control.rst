.. _quality_control:

Quality Control and Developer Workflow
======================================

Poriscope runs automated **quality control checks** on every commit, through Git hooks, and
again in continuous integration (CI). This page explains what each check does and how to
work with it. If you are about to open a pull request, go straight to
:ref:`pre_pr_checklist`.

.. note::

   New to "automated quality control"? Instead of asking a reviewer to check formatting,
   docstrings, or whether your plugin implements the right methods, Poriscope runs small
   programs that check these things every time, in seconds. You do not need any prior
   experience with these tools to follow this page.

Pre-commit Hooks (Validation)
-----------------------------

These hooks run on every commit, through the **pre-commit** framework, whether you commit
from the command line or from GitHub Desktop (see :doc:`developer_setup` to install them).
They **never modify files**, and if any of them fails the commit is **blocked**.

.. list-table::
   :header-rows: 1
   :widths: 24 52 24

   * - Hook
     - What it checks
     - Scope
   * - ``ruff``
     - lint rules, strictly, without fixing anything
     - every Python file
   * - ``ruff-plugin-security``
     - security-relevant rules; see :ref:`plugin_trust_boundary`
     - ``poriscope/plugins/``
   * - ``mypy``
     - static typing; see :ref:`type_checking_policy`
     - ``poriscope/``
   * - ``pydoclint``
     - docstrings match the real signature and body; see :ref:`docstring_consistency`
     - ``poriscope/``
   * - ``plugin-module-level``
     - no code runs when a data plugin is merely discovered; see
       :ref:`plugin_trust_boundary`
     - the nine data-plugin families
   * - ``settings-schema``
     - every plugin's ``get_empty_settings()`` is self-consistent; see
       :ref:`settings_schema_checking`
     - ``poriscope/plugins/``
   * - ``text-encoding``
     - ``requirements*.txt`` is UTF-8 with no byte-order mark
     - the requirements files
   * - ``check-added-large-files``
     - no file larger than 123 KB
     - every file

``text-encoding`` exists because PowerShell's ``>`` and ``Out-File`` write UTF-16LE, which
git treats as binary, and ``pre-commit-hooks``' ``fix-byte-order-marker`` only recognises
the UTF-8 byte-order mark. Pass ``-Encoding utf8`` when regenerating either requirements
file from PowerShell.

Run every hook, or one of them, by hand:

.. code-block:: bash

   pre-commit run --all-files
   pre-commit run mypy --all-files

Further gates are not pre-commit hooks, but the test suite and CI enforce them just as
strictly:

- :ref:`plugin_compliance_testing` and :ref:`settings_schema_checking`: your plugin
  implements its base class's interface and declares a consistent settings schema.
- :ref:`plugin_conformance_testing`: your plugin actually behaves like a member of its
  family on synthetic data; a reader is also fed malformed files
  (:ref:`reader_fuzz_testing`).
- :ref:`docs_render_check`: the documentation builds with warnings treated as errors.
- If you edit the code they measure: the :ref:`duplication_ratchet`, the
  :ref:`shell_complexity_ratchet`, the :ref:`mvc_boundary` and
  :ref:`recorded_actions_read_no_widgets`.

.. warning::

   Use ``pre-commit run mypy`` rather than a bare ``mypy poriscope``. The hook runs mypy in
   an isolated environment with no project dependencies, as CI does, so PySide6, numpy and
   pandas are all ``Any`` to it. Mypy run from your own virtual environment sees their real
   types and reports several hundred further messages, about a third of them known noise
   (Qt's short-form enum accesses, untyped imports). **The hook is the gate.** Branch CI
   still runs a bare ``mypy poriscope`` as a **non-blocking report** and prints the error
   count, because it sees what the hook cannot - a controller calling a method its View
   does not have, for instance. See ``DECISIONS.md``, 2026-08-24.

   The mypy version is pinned three times - mirrors-mypy's ``rev`` in
   ``.pre-commit-config.yaml``, and ``mypy==`` in ``pyproject.toml``'s ``[dev]`` extra and
   in ``requirements-dev.txt`` - and the three move together in one commit.

Automatic Formatting and Auto-fixes
-----------------------------------

``black`` and ``ruff --fix`` never run on commit, so a commit never changes your files. Run
them yourself:

.. code-block:: bash

   pre-commit run --all-files --hook-stage manual

then review what changed, stage it and commit. In CI, on branch pushes and on pull
requests from inside the repository, the same step runs first and commits its fixes back to
the branch; the strict hooks then run, and only problems that remain fail the job. Pull
requests from a fork get the strict hooks only.

.. note::

   **Which Ruff rules are enabled.** Ruff's default rule set is in force, and
   ``pyproject.toml`` adds to it with ``extend-select``. The default worth knowing is
   ``E722``, **no bare** ``except:`` -- narrow to ``except Exception:`` at minimum, so that
   the exceptions you swallow can be named in a ``:raises:`` docstring section. On top of
   the defaults, ``pyproject.toml`` selects:

   - ``I`` -- import ordering (isort).
   - ``B006`` -- a mutable data structure used as an argument default. A ``[]`` or
     ``{}`` default is built once and shared by every call, so mutating it leaks state
     between calls. Use ``None`` and create the container inside the function.
   - ``B020`` -- a loop control variable that shadows the iterable it iterates over,
     making the original sequence unreachable for the rest of the loop body.
   - ``S110`` -- ``try``/``except``/``pass``, which swallows an error without a trace.
     Log it, narrow it, or let it propagate.

   The other audited ``flake8-bugbear`` and ``bandit`` rules (``B905``, ``B904``,
   ``B007``, ``S112``, ``S101``) are deliberately **not** enabled, and the ``S608``
   hardcoded-SQL sites are accepted; the reasoning is in ``DECISIONS.md``, so please read
   it before re-proposing them. That is a separate question from ``ruff-plugin-security``
   (:ref:`plugin_trust_boundary`), whose narrower ``S`` selection runs only on the plugin
   tree.

.. _docs_render_check:

Checking That the Documentation Still Renders
---------------------------------------------

Most of Poriscope's documentation is generated from the docstrings you write, so a
malformed directive or a broken cross-reference in a docstring is a documentation bug.
``pydoclint`` will not catch it: it verifies that the parameters, return type and
exceptions a docstring documents match the real function, not that the surrounding
reStructuredText is well formed. Sphinx catches it, so Sphinx is a gate.

Every pull request targeting ``main``, ``develop`` or a ``release/*`` branch runs the
**Docs Render Check** workflow, which regenerates the autodoc ``.rst`` files and builds
the HTML with ``-W`` — warnings are errors. It also runs on every push to ``develop``,
``hotfix/*`` and ``release/*``, because git flow merges those locally rather than through a
pull request.

To run exactly what the docs check runs:

.. code-block:: bash

   python scripts/generate_all_autodoc_rst.py
   sphinx-build -W --keep-going -b html -d docs/.doctrees docs/source docs/build

``--keep-going`` reports every warning in one pass instead of stopping at the first, so
you can fix them all in a single edit. The ``post-merge`` git hook uses the same flags
(see :doc:`post_merge_automation`), so if hooks are installed you will usually see a
rendering problem the moment you merge rather than when you open a pull request.

.. note::

   The generator step is not optional. ``docs/source/autodoc/`` is git-ignored and
   regenerated from the source tree, so a build without it fails on missing table-of-
   contents entries rather than on anything you did.

.. note::

   **Not every method is published, and the rule is not simply "public ones".** A method
   with a leading underscore is omitted as an internal helper *unless* its name is one
   some ``Meta*`` base declares ``@abstractmethod``, in which case it is the contract a
   subclass author has to satisfy and it stays. That keeps ``MetaFilter._apply_filter``
   on the base's page and a plugin's own implementation of it on the plugin's page, while
   dropping the helpers around them. ``__init__`` is published too: its signature appears
   on the class line, but the ``:param:`` fields explaining each argument live only in
   its docstring.

   A class whose name starts with an underscore is not published at all: it is internal
   to its module. A base class is linked by its page when it has one - a ``Meta*`` base,
   another plugin, or a hand-written page such as the walkthrough mixin's - and is
   otherwise shown as plain text rather than as a guessed link.

   So if a method you documented does not appear on the site, check whether it is private
   and not part of any declared contract. That is the rule working, not a build problem.

.. note::

   **The build imports the real package, PySide6 included.** ``autodoc`` does not mock Qt
   (``docs/source/conf.py`` explains why), so ``sphinx-build`` needs an environment in
   which ``import poriscope`` works fully - automatic on a development machine with the
   project installed. In CI the docs workflows install the Qt libraries the runner lacks
   (``libegl1``, ``libgl1``, ``libxkbcommon0``) first; without them the build fills with
   unrelated autodoc errors.

.. note::

   **The build downloads other projects' indexes.** Through ``sphinx.ext.intersphinx``, a
   type such as ``numpy.ndarray`` or ``QWidget`` in a docstring links to that library's
   own documentation. A site that cannot be reached is reported as an info line and its
   types render as plain text; it does not fail a ``-W`` build. References to Poriscope's
   own code that point nowhere are not yet a gate: ``nitpicky`` is off.

What CI Runs
------------

- **CI (Branches)**, on every push to ``develop``, ``feature/*``, ``bugfix/*``,
  ``hotfix/*`` and ``release/*``: auto-fix, the strict pre-commit hooks and the
  non-blocking mypy report, then the full test suite on four legs - Python 3.12.0 (the
  floor) with the runtime stack pinned to ``requirements.txt``, and the newest supported
  Python with the ranges in ``pyproject.toml`` resolved fresh, each on Linux and Windows.
  Every leg records each test's duration, and the Linux 3.12.0 leg warns about a slow test
  or a suite slower than its size (:ref:`test_durations`). A second job builds the wheel
  and sdist, checks them with ``twine check --strict``, and imports the installed wheel,
  wavelet library included, outside the checkout.
- **Pull requests**: one workflow for pull requests from inside the repository, and a
  restricted, read-only one for forks (strict hooks and the full suite, no auto-fix).
- **Docs Render Check**: see :ref:`docs_render_check`.
- **Release**, only when a ``v*`` tag is pushed: re-runs the suite on the tagged commit,
  checks the distributions with twine, and publishes to PyPI and GitHub only if that
  passes.

Every action is pinned to a commit SHA, and Dependabot opens weekly pull requests against
``develop`` to move those pins and the exact pins in ``requirements.txt``. Each range in
``pyproject.toml`` starts at the version ``requirements.txt`` pins, so move a pin and its
lower bound together.

.. _plugin_trust_boundary:

Plugin Code Runs on Your Machine
--------------------------------

Two of the hooks exist for one reason: **plugin discovery executes every Python file it
finds.** ``MainModel.populate_available_plugins()`` walks ``poriscope/plugins/`` and your
configured user-plugin folder recursively, and for each file it calls
``spec.loader.exec_module()``. Python runs module-level code unconditionally, before
anything has inspected the class -- so a plugin file is a code-execution boundary in a way
that the rest of the application is not. Two hooks police it:

``ruff-plugin-security``
   A second Ruff pass over ``poriscope/plugins/``, selecting only rules a
   nanopore-analysis plugin has no legitimate reason to trip: ``exec`` and ``eval``
   (``S102``, ``S307``), unsafe deserialization (``S301`` pickle, ``S302`` marshal,
   ``S506`` yaml), process spawning (``S601``--``S607``, ``S609``), network or
   temp-file risks (``S310`` urlopen, ``S306`` mktemp), and ``S612`` (insecure
   ``logging.config.listen``).

``plugin-module-level``
   Rejects any module-level statement in a data plugin that runs code. The rule is that
   **module-level assignment is fine but module-level invocation is not**, so a type alias
   such as ``Numeric = Union[int, float, np.number]`` passes while
   ``logger = logging.getLogger(__name__)`` does not -- move that kind of thing into a
   method. Only imports, constants, classes and functions belong at the top level of a
   plugin. Decorators on a class or function are not examined, since ``@log`` is part of
   the plugin pattern.

   Run it yourself on the plugin you are writing::

      python scripts/check_plugin_module_level.py poriscope/plugins/eventfinders/MyFinder.py

Both are measured at zero findings on the shipped tree, so neither has a baseline or any
exemptions -- if one fires on your plugin, it has found something real.

.. important::

   These checks raise the bar against a careless submission. They are **not** a sandbox
   and not a defence against a determined adversary: a plugin can still do as it likes
   inside a method body that only runs once the plugin is instantiated, and neither hook
   sees a file you drop straight into your user-plugin folder without a pull request.
   Plugins are reviewed by a human before they are merged, and that review remains the
   real gate.


Skipping Hooks (Advanced Use Only)
----------------------------------

``git commit --no-verify`` skips the hooks, for emergencies only. It does **not** skip CI,
which re-runs every enforced check, so in practice it only delays the failure.

.. _docstring_consistency:

Docstring and Signature Consistency (pydoclint)
------------------------------------------------

``pydoclint`` reads your code without running it and compares each docstring's claims with
what the function actually does, because a docstring that is wrong is trusted and acted on
anyway. For every documented function it checks that:

- every parameter named in the docstring actually exists in the function signature
  (and vice versa — no undocumented parameters, no documented parameters that don't
  exist),
- the documented return type matches what the function actually returns,
- the exceptions listed in a ``Raises`` section match the exceptions the function can
  actually raise.

.. important::

   ``pydoclint`` does **not** require every function to have a docstring. It only
   holds a docstring accountable *if one already exists* — if you didn't write one,
   ``pydoclint`` has nothing to check.

   Two more gaps follow from its defaults. A docstring with only a summary - no
   ``:param:``, ``:return:`` or ``:raises:`` fields - is treated as short and not checked,
   and so is one written in another style: a Google ``Args:`` section reads as plain
   summary under ``style = "sphinx"``, so its parameters are never compared with the
   signature. And its raise check counts an exception the function raises even when a
   local ``try`` in the same function catches it; move such code into a helper that
   documents its own ``:raises:`` rather than documenting an exception that never
   escapes.

   It *does* require that a documented function's signature carry type hints, and
   that those hints agree with the docstring's ``:type:`` and ``:rtype:`` fields. The
   signature is the source of truth; where the two disagree, fix the docstring.
   (Separately, ``mypy`` now requires type hints on **every** function under
   ``poriscope/``, documented or not — see :ref:`type_checking_policy`.)

Running it locally
^^^^^^^^^^^^^^^^^^^

``pre-commit run --all-files`` already runs ``pydoclint`` on your behalf, so most
contributors will meet it there rather than by invoking it directly. If you want to
check just the docstring/signature rules on their own:

.. code-block:: bash

   pydoclint --baseline=.pydoclint-baseline.txt poriscope

.. tip::

   A ``DOC105`` ("type hints do not match") that makes no sense is usually a
   formatting problem rather than a real mismatch. ``pydoclint`` folds any prose that
   trails a ``:type:`` field into that field's value, so a docstring written with the
   parameter list first and the descriptive paragraph last reports a spurious
   ``DOC105`` against whichever parameter happens to be documented last. Put the
   description **first**, then the ``:param:``/``:type:``/``:return:``/``:rtype:``
   fields, and it goes away.

Why is there a "baseline" file?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``.pydoclint-baseline.txt`` once listed violations that predated the tool. It is now
empty and must stay empty, so every violation the hook reports is real and fails the
commit. **Do not** regenerate it (``pydoclint --generate-baseline=True ...``) to silence a
failure; fix the docstring instead.

.. _type_checking_policy:

Type Annotation Policy (mypy)
------------------------------

Every function under ``poriscope/`` carries parameter and return type hints, with no
exclusions, and ``mypy.ini`` enforces that:

- ``disallow_untyped_defs = True`` — a function with no annotations is an error rather
  than being silently skipped. **New code must be annotated.**
- ``check_untyped_defs = True`` — function bodies are type-checked even where the
  checker cannot fully resolve their types.
- ``strict_equality = True`` — catches comparisons between types that can never be
  equal, such as a display string compared against an integer channel id.
- ``python_version = 3.12`` — fixes the language and standard-library level mypy checks
  against. Without it mypy assumes whatever interpreter happens to run it, so a
  contributor on a newer Python could see a different verdict from CI. Only
  ``MAJOR.MINOR`` is valid here; the patch-level floor is ``requires-python`` in
  ``pyproject.toml``, which is a separate concern.

.. note::

   If you are adding a plugin, the simplest and most reliable way to annotate its
   methods is to **copy the signature from the ``Meta*`` base class verbatim**, rather
   than inferring types from your implementation. The compliance test in
   :ref:`plugin_compliance_testing` compares your override against the base, and for
   generic types such as ``List[str]`` it compares them by *equality* — so a
   reasonable-looking widening of the base's type will fail it.

.. _test_suite_configuration:

Test Suite Configuration
-------------------------

``pytest.ini`` is the only pytest configuration in the repository. Six settings there are
worth knowing about before you add tests:

- ``timeout = 300`` — a per-test backstop in seconds, supplied by ``pytest-timeout``. It
  exists because a hung Qt test otherwise runs to GitHub Actions' six-hour job limit. It
  is not a performance budget - that is the ``time_budget_*`` settings below - and the
  explicit ``@pytest.mark.timeout`` markers under ``tests/e2e/`` and
  ``tests/integration/`` are all 90 seconds or less and still override the default. **If
  your test trips this value, that is a finding about the test, not a reason to raise
  the number.**
- ``time_budget_unit``, ``time_budget_integration``, ``time_budget_e2e`` — seconds one
  test of each tier may take (5, 20 and 60) before ``pytest --time-budget`` warns about
  it. See :ref:`test_durations`.
- ``junit_duration_report = total`` — a ``--junitxml`` file records each test's setup,
  call and teardown together, so fixture and teardown cost is not hidden.
- ``--strict-markers`` — an unregistered marker name is a collection error rather than an
  expression that matches nothing. Register any new marker in the ``markers`` list.
- ``--dist loadfile`` — under ``-n``, each test file runs whole on one worker, in its own
  order. Splitting a file across workers would reorder its tests, and leaked Qt state has
  made order matter in this suite before. Every worker must also collect the same tests in
  the same order, so a parametrization built from a set or a dict of classes has to be
  sorted.
- ``pythonpath = .`` — puts the repository root on ``sys.path`` so the shared test helpers
  (``tests/unit/views/_qt_mocks.py``, ``tests/e2e/_helpers.py``, the
  ``tests/synthetic_data/`` generators) are importable as ``tests.<module>``. The editable
  install exposes only ``poriscope``, so without this setting those imports resolve only
  when a conftest higher up the tree happens to be collected first — which made running a
  single test file on its own fail with ``No module named 'tests'`` while the same file
  passed in a full run.

Beyond ``pytest.ini``, the root ``tests/conftest.py`` deletes every window a test leaves
behind once the test ends, and **fails the test if a window survives**. Every test shares
one ``QApplication``, so a window that is only closed (``close()`` hides it) stays alive and
makes every later test slower. If your test fails with "Windows still alive after the cleanup",
something is keeping one of its windows from being deleted. It also stops every replay a test
leaves running, and **fails the test that left one**: a running replay takes the errors that
would open a dialog, from a set the whole process shares, so one left running hides the dialogs
of every later test. If your test fails with "A replay was still running after the test", stop
the replay in the test's own fixture, as ``tab.replay_sequence.stop(quitting=True)``.

After any leftover replay is stopped and before the windows go, the same conftest **fails a
test whose worker thread is still running**. Destroying a window while its ``QThread`` runs
aborts the interpreter, and an abort names no test, so each thread a test starts is recorded
and, at teardown, given up to five seconds to end. One still running is named - a
``WorkerThread`` by its key and channel - on the terminal straight away and in the failure.
If your test fails with "left threads running", wait for its work to finish (the flow tests
wait on ``model.workers``) before it ends.

.. note::

   If you add a dev dependency, it must go in **both** ``pyproject.toml``'s ``[dev]`` extra
   and ``requirements-dev.txt``. They are byte-for-byte mirrors of each other and nothing
   enforces that. Every test workflow installs ``.[dev]``; the branch and pull-request
   workflows fall back to ``requirements-dev.txt`` only if that editable install fails, so a
   file missing the entry breaks CI exactly when the fallback is needed. Pin it
   exactly with ``==``, as every other entry in both files is.

Coverage is measured with ``pytest-cov``, which is declared in the ``[dev]`` extra but is
**not** wired into ``addopts``:

.. code-block:: bash

   pytest --cov=poriscope --cov-report=term-missing

Run it deliberately when you want the number. No CI workflow collects coverage: the plain
``pytest -n auto`` invocation is the gate everywhere, and coverage instrumentation would slow every
run for a figure nothing acts on.

.. _test_durations:

Test Durations and Time Budgets
--------------------------------

A cost paid once per test - a window left alive, an application rebuilt - grows with the
number of tests that pay it, and can slow the suite several-fold while every test still
passes. A pass/fail gate cannot see that, so every CI run records how long each test took,
and two checks read the record. Both only warn.

**What CI records.** Every test job runs pytest with ``--junitxml=pytest-junit.xml`` and
``--durations=25``. The job's summary page gets a table of tests, summed seconds and
milliseconds per test for each directory; under ``-n auto`` the summed seconds are more than
the wall time. Branch CI also keeps the file as an artifact for 30 days. Read or compare
files with ``scripts/test_durations.py``:

.. code-block:: bash

   pytest -n auto --junitxml=run.xml
   python scripts/test_durations.py report run.xml --top 50   # per file, then the slowest tests
   python scripts/test_durations.py compare old.xml new.xml   # what changed between two runs

``compare`` splits the change between new tests, removed tests and tests in both runs, which
is the first question about a slowdown: more tests, or dearer tests?

**The per-test budget.** ``pytest --time-budget`` warns about every test over its tier's
budget in ``pytest.ini``: 5 seconds for a unit test, 20 for an integration test, 60 for an
e2e test. A test's own time leaves out setting up a fixture wider than the function, and
the teardown that closes a module or class, since pytest bills those to whichever test
happens to run first or last. It works the same under ``-n auto``. A test that needs its
time says why:

.. code-block:: python

   @pytest.mark.exceeds_time_budget(reason="imports the whole app in a fresh interpreter")
   def test_importing_the_app_adds_no_root_logging_handler(): ...

**The size check.** ``scripts/test_durations.py check`` expects each directory to cost (its
tests now) x (its milliseconds per test in ``tests/test_duration_baseline.json``); a new
directory is expected at its tier's average, and no test counts for more than its budget.
It warns when the suite takes more than 1.3 times what it expects, or a directory of at least
five tests more than 1.5 times. Both margins sit above a CI runner's ordinary run-to-run
variation.

Both checks run on branch CI's Linux 3.12.0 leg only, so their warnings come from one kind
of runner, and neither fails the build: one test's time is noisy from run to run, and a cost
leaked by one test can land on another. The size check is skipped until the
baseline file exists. Make or refresh it from several of that leg's artifacts - the median
of each directory is kept, so one unusual run does not set it - when a slowdown is accepted
or a speed-up should be held:

.. code-block:: bash

   python scripts/test_durations.py baseline a.xml b.xml c.xml > tests/test_duration_baseline.json

``pytest --marker-stats`` prints the number of tests and their mean time per marker, with or
without ``-n``.

.. _plugin_compliance_testing:

Plugin Interface Compliance Testing
------------------------------------

Every ``Meta*`` base class (see :ref:`understanding base classes
<understanding_base_classes>`) defines exactly which methods a plugin must implement, with
which arguments and types; that is how the GUI and the scripting layer talk to your plugin
without extra configuration. ``tests/unit/plugins/test_plugin_compliance.py`` checks every
plugin against that contract. It:

1. recursively imports every module under ``poriscope.plugins`` so that every plugin
   class actually gets loaded,
2. finds every concrete subclass of each ``Meta*``/``BaseDataPlugin`` base,
3. checks that each one implements every method its base class marks as
   ``@abstractmethod``,
4. checks that overridden methods keep the same argument names, the same argument
   order, and (where type hints are present) a compatible type signature - both the
   abstract ones and any method you override that the base already implements, such
   as ``get_empty_settings`` or ``load_data``, since the app calls those through the
   base's contract too.

Run it locally with:

.. code-block:: bash

   pytest tests/unit/plugins/test_plugin_compliance.py

This is exactly the test referred to in :ref:`build_data_plugin` and
:ref:`build_frontend_plugin` when they say a contribution must "pass our tests and
type checks" — **a plugin cannot be merged if this test fails against it**, no matter
how good the underlying science is.

.. tip::

   If you're building a new plugin, don't wait until you're "done" to run this test.
   Stub out the required methods first (even with just ``pass`` in the body), run the
   test, and fix any interface mismatches immediately. It is much cheaper to fix a
   wrong argument name before you've written 200 lines of logic around it than after.

.. _settings_schema_checking:

Settings-Schema Checking
-------------------------

Interface compliance above checks the *methods* your plugin implements. A separate check
covers the *settings schema* it declares — the dict your ``get_empty_settings()`` returns,
where each parameter carries a ``Type`` and optionally a ``Value``, ``Options``, ``Min``,
``Max`` and ``Units``.

The reason this needs its own check is that nothing else looks at the schema until a user
tries to use your plugin. ``BaseDataPlugin`` validates a *supplied* settings dict at
instantiation, so a contradiction baked into the schema itself — a ``Min`` above its
``Max``, an ``Options`` list whose entries are not of the declared ``Type``, a default that
is not among its own ``Options`` — surfaces as a ``TypeError`` or ``ValueError`` raised
from inside the base class, with nothing pointing at your schema as the cause.

The most common version of this is declaring ``"Type": float`` and then writing an int
default:

.. code-block:: python

   settings["Min Height"] = {"Type": float, "Value": 500}     # wrong
   settings["Min Height"] = {"Type": float, "Value": 500.0}   # right

The runtime check is a bare ``isinstance``, and ``isinstance(500, float)`` is ``False``.

Run the check over every plugin, or just yours:

.. code-block:: bash

   python scripts/check_plugin_schemas.py
   python scripts/check_plugin_schemas.py MyEventFinder

It is also part of the normal test suite, as
``tests/unit/plugins/test_plugin_settings_schema.py``, so CI enforces it whether or not
you run the script. To call the check on a schema directly — from your own test, say —
use ``poriscope.utils.settings_schema.validate_settings_schema()``, which takes a schema
and returns a list of human-readable problems.

.. note::

   Omitting ``Value`` entirely is fine and means the same as ``Value: None``: no default,
   the user must supply one. Most shipped readers do exactly this. What is *not* fine is
   supplying a ``Value`` that contradicts the ``Type`` beside it.

The check above is static: it validates the schema's *shape* against hand-built rules, with
no plugin instance involved. ``tests/unit/plugins/test_settings_defaults.py`` covers what
that cannot — whether a plugin's *own real* defaults survive that *same plugin's* live
``_validate_param_types``/``_validate_param_ranges`` at instantiation. The two can
disagree even when the schema is self-consistent by the static rules, so both run; a
plugin that ships no real defaults to check (every parameter omits ``Value`` or sets it to
``None``) is reported as skipped rather than silently passing.

.. _plugin_conformance_testing:

Behavioural Conformance Testing
--------------------------------

Compliance and schema checking are both *static* - they read your plugin without running
your algorithm - so a plugin can satisfy both and still get the wrong answer on the first
real event: a reader can return the right number of samples with the sign flipped, or a
fitter declare every metadata column and then reject every event it is handed.
``tests/unit/plugins/conformance/`` closes that gap. It builds your plugin the way the
application does — real settings, a real parent plugin, a real file — drives it over
synthetic data from ``tests/synthetic_data/``, and checks it behaves like a
well-formed member of its family. All nine families are covered, each with checks
written for what that family's output is actually used for:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Family
     - What conformance asks of it
   * - ``MetaConditioningLoader``
     - One pore size per cycle on every channel, cycles counted from 1; every PSD
       recording has a cycle, a sample rate and points per average, and its samples are
       finite floats in pA; the status report covers the experiment and each channel.
   * - ``MetaReader``
     - Agrees with the recording about channels, sample rate and length; ``load_data``
       recovers the planted baseline and event depth in picoamps, not just a plausible
       shape.
   * - ``MetaFilter``
     - Shape and dtype preserved, output finite, the data actually changed but the
       blockage still detectable, and ``get_callable_filter()`` agreeing with
       ``filter_data()``.
   * - ``MetaEventFinder``
     - Locates exactly the planted events — neither missing any nor reporting noise —
       with boundaries ordered, in-bounds and non-overlapping, landing on the
       plantings, and ``get_single_event_data()`` carrying the documented keys.
   * - ``MetaEventFitter``
     - Fits every planted event rather than silently rejecting them all, and every
       metadata column it produces is declared in ``get_event_metadata_types()``
       **and** ``get_event_metadata_units()`` so the database writer has a type for
       it. Also ``get_single_event_metadata()`` returning usable arrays. The CUSUM
       family (``CUSUM``, ``ClassicCUSUM``, ``IntraCUSUM``) is additionally checked
       against a known planted *sublevel* count, not just a known event count, over
       a dedicated staircase fixture.
   * - ``MetaEventLoader``
     - Agrees with the database about channels, event count and sample rate, and every
       loaded event carries the exact keys ``get_event_generator``'s docstring
       specifies, with padding that leaves room for a blockage.
   * - ``MetaWriter``, ``MetaDatabaseWriter``
     - Driven through a real chain, then the output is checked for SQLite integrity,
       the expected row count, and — the part that matters — being readable back by
       the matching loader.
   * - ``MetaDatabaseLoader``
     - Reports its experiments, channels and per-channel event counts correctly, can
       type every column it lists, and discriminates a valid filter query from an
       invalid one.

Every family is also asked that ``reset_channel`` and ``close_resources`` are safe
after use, including twice, and that its status report holds together: a plugin with
channels answers ``report_status(channel)`` with a non-empty report that is part of what
``report_status()`` gives for the whole plugin, and a filter or database loader, which has
no channels, gives the same report either way. Readers, loaders and writers are further asked to actually
release their file(s) once nothing references the plugin anymore, which on Windows is a
genuine handle-leak check because an open handle blocks ``os.unlink``. The check differs
by family because the contract does: a writer closes its connection explicitly inside
``close_resources``, while ``close_resources``'s docstring permits a reader to leave a
memmap for the garbage collector to reclaim — so the reader/loader version of the check drops its only
reference and runs ``gc.collect()`` before checking, rather than asserting on
``close_resources`` alone.

Like the compliance test, it is parametrised over *discovered* classes, so your plugin
is covered the moment you drop the file in. The suite cannot guess valid settings on
its own — ``Options`` on a file parameter is a dialog filter glob rather than a list of
values, most numeric parameters declare no ``Max`` to interpolate against, and a
parameter naming a parent plugin needs a live instance — so whether *you* need to add
anything depends on which family your plugin belongs to. At a glance:

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Family
     - Recipe work
     - What that means
   * - ``MetaFilter``, ``MetaEventFinder``, ``MetaEventFitter``
     - **Always**
     - An entry keyed by your class name, even if it is empty. An event fitter may also
       have to say which synthetic recording it should be tested against.
   * - ``MetaWriter``, ``MetaDatabaseWriter``, ``MetaDatabaseLoader``,
       ``MetaEventLoader``
     - **Usually none**
     - Nothing, provided your plugin adds no required parameter of its own.
   * - ``MetaReader``
     - **Always**
     - A fixture entry, always — the lookup is per class, so even a covered format
       needs one. How much work it is varies; see :doc:`conformance_recipes`.
   * - ``MetaConditioningLoader``
     - **Always**
     - An entry in ``CONDITIONING_LOADER_BUILDERS`` that writes an experiment folder in
       your format and returns the loader built over it.

.. note::

   One thing applies to **every** family: a plugin generated by
   ``scripts/new_plugin.py`` ships a placeholder parameter with no default, so it
   cannot pass until you replace or delete it. "Usually none" above means no *recipe*
   work — it does not mean a freshly generated plugin passes untouched.

.. tip::

   **Where to start.** Run ``pytest -m conformance`` before you have written any of
   your algorithm, while your plugin is still the generated skeleton. You will get one
   clear failure naming exactly what to add, and from then on the suite watches your
   plugin from your earliest commit.

The family-by-family reference for writing a recipe - the settings dicts, choosing an
event fitter's fixture, a reader's synthetic file, extra settings and format-specific
mutations - is on its own page, :doc:`conformance_recipes`. However much your family needs,
the suite is run the same way; the test ids carry the class name, so ``-k`` matches it:

.. code-block:: bash

   pytest -m conformance                    # every plugin, all nine families
   pytest -m conformance -k YourPlugin      # only yours, while you work

.. _real_recordings_tier:

Real Recordings on a Developer's Machine
----------------------------------------

Synthetic recordings are deterministic and small, which is what the gates need; they are
also idealised. A second tier of tests reads real lab recordings, which are gigabytes each
and never enter the repository. Such a test carries the ``real_data`` marker and takes the
``real_data_dir`` fixture, which resolves the directory the environment variable
``PORISCOPE_REAL_DATA_DIR`` names and **skips** the test wherever the variable is unset or
points nowhere. CI has no such directory, so the whole tier skips there without a failure;
a developer with the recordings runs it by setting one variable:

.. code-block:: bash

   PORISCOPE_REAL_DATA_DIR="/path/to/data" pytest -m real_data

``tests/unit/plugins/conformance/test_real_recordings.py`` lists each recording with the
subfolder it lives in, the reader that opens it, and what that reader reported - sample
rate, channels, lengths and median currents - as goldens any change to a reader has to
reproduce. A recording whose subfolder is missing skips its tests, so a partial copy of
the data is still useful.

Keep two things apart when reading these results: a synthetic test that fails is a defect
or a wrong expectation; a real-recording test that fails may also be a property of that one
recording, which is why the tier reports and the synthetic tiers gate.

.. _reader_fuzz_testing:

Fuzz Testing for Data Readers
-------------------------------

Everything above only ever hands a reader a *well-formed* recording. Readers parse
files produced by real, uncontrolled instrument software, so
``tests/unit/plugins/conformance/test_reader_fuzz.py`` drives every discovered
``MetaReader`` over a small, fixed set of deterministic mutations of its own valid
fixture instead — truncated to zero bytes, truncated mid-file, a corrupted format
marker, a missing sidecar — and asserts three tiers, in order of how far the mutation
lets the reader get:

1. Construction either succeeds or raises a caught exception — never hangs, never
   raises something uncatchable.
2. If construction succeeds, ``get_channel_length()`` agrees with what ``load_data``
   can actually deliver for that many samples.
3. Requesting more than ``get_channel_length()`` reports raises ``ValueError``
   rather than quietly returning a shorter array.

Coverage follows the fixtures. ``MUTATIONS`` in ``_recipes.py`` is keyed by reader class
name and built from ``READER_DATASET_BUILDERS``' own keys, so a reader is fuzz-tested from
the moment it has a conformance fixture, with nothing further to register here. Each
reader gets the shared mutations above, plus any format-specific ones registered for it;
a headerless binary format has nothing of its own to corrupt. :doc:`conformance_recipes`
shows how to add one.

These run as part of ``pytest -m conformance`` like everything else, but they are quick
enough to run on their own while you are working on a parser:

.. code-block:: bash

   pytest tests/unit/plugins/conformance/test_reader_fuzz.py
   pytest tests/unit/plugins/conformance/test_reader_fuzz.py -k YourReader

.. note::

   The suite deliberately does not assert a single exception type for malformed input:
   readers raise different ones today (``ValueError``, ``NotImplementedError`` from
   ``pyabf``, ``FileNotFoundError``, ``OSError``). Whether they should converge is an
   open question tracked in ``future_fixes.md``, not something this suite decides.

.. _duplication_ratchet:

Duplication Ratchet
--------------------

This one affects you if you edit any plugin or widget file. The ratchet measures byte-identical
duplication in **families** of files that tend to copy from one another - the analysis
tabs' Views, Controllers, Models and controls panels, each data-plugin folder, the shared
widgets and the SQLite plugins; ``FAMILIES`` in ``scripts/measure_duplication.py`` is the
list - so that duplication cannot grow back unnoticed.

``PeakFinder.py``, ``Basic_PeakFinder.py`` and ``NanoTrees.py`` are **deliberately outside**
the fitters family: their logic is another maintainer's under standing policy, so a ratchet
over them would fail on their commits for a metric about someone else's refactor. They
are recorded in ``EXCLUDED`` in ``scripts/measure_duplication.py`` with that reason, and a
test asserts it, so a later tidy-up cannot quietly add them back.

**Every module under** ``poriscope/plugins/`` **and** ``poriscope/views/widgets/`` **is
either in a family or in** ``EXCLUDED``, and a test fails on any that is neither. So a
**new plugin or widget file** has to be added to the family it may copy from, or excluded
with its reason, in the commit that adds it. A changed file or function count is reported
as a list change, not as duplication; rerun with ``--update`` to record it.

**Widen a family before the change that would fool it, never after.** A gate scoped by
file path stops measuring the moment code moves out of that path, and it fails *silently*,
because the number moves the way you wanted.

Each family also holds the ``Meta*`` bases its files inherit from (``MetaView``,
``MetaSubsetTabView`` and the rest for the tabs; ``MetaReader`` for the readers). Without them,
a base method copied onto a single tab has no identical twin in the family, so it reads as
one more function rather than as duplication. ``BaseDataPlugin`` is left out, because it
underlies every data family.

``scripts/measure_duplication.py`` counts, per family, how many function bodies are
byte-identical across more than one file and how many lines would be deleted by promoting
one copy to a shared base. ``.duplication-baseline.json`` records those counts and names
each duplicated function, and ``tests/unit/scripts/test_duplication_ratchet.py`` fails if
the measurement disagrees. A rise lists the functions it newly duplicated: that is usually
a copy to remove, and ``--update`` is only for duplication you meant to add. The names are
never compared, so renaming a duplicated function fails nothing.

.. code-block:: bash

   python scripts/measure_duplication.py             # the table
   python scripts/measure_duplication.py --verbose   # every duplicate group, largest first
   python scripts/measure_duplication.py --check     # compare against the baseline

**The check is exact, not "no worse than".** A rise means duplication was added. A fall is
a win — and it fails too, so the win is recorded in the same commit that earned it. The
baseline also records each family's file and function counts, so adding or removing *any*
method in a measured file fails the check as well. That failure names the function count
("the family gained functions") rather than calling it duplication, since the removable
count has not moved. If your change legitimately removed duplication or changed the
function list, rerun with ``--update`` and commit the new baseline alongside it.

.. warning::

   Read the failure message before running ``--update``. Byte identity is brittle in one
   direction: editing a few characters in *one* copy of a five-way duplicate drops that
   copy out of its group, so the removable count falls by a whole copy's worth while
   nothing was deduplicated — and the duplication is actually *worse*, five near-identical
   bodies instead of five identical ones. The check tells the two apart without any
   similarity measure, because promoting a method to a base **deletes** the copies, so the
   function count falls too, while an edit into divergence leaves it untouched. When it
   sees that shape it says so explicitly.

   If you are fixing a bug in one of these methods, the fix almost certainly belongs in
   every copy.

.. _shell_complexity_ratchet:

App-Shell Complexity Ratchet
-----------------------------

This one affects you if you edit the **app shell**: the two controllers and two models
under ``poriscope/controllers/`` and ``poriscope/models/``, ``main_view.py``,
``settings_window.py``, and ``main_app.py``, plus the two packages' ``__init__.py``. Nine
files in all, listed explicitly in the script.

No duplication family includes these files, so this is the gate that watches them. **The
shell is measured in complexity, not in lines**: its length is mostly flat Qt widget
construction with no branching to untangle, and every shell file currently has no
function over the threshold.

``scripts/measure_shell_complexity.py`` reports, per file, how many functions were
scanned, how many exceed cyclomatic complexity 10, and the summed complexity of those
that do. ``.shell-complexity-baseline.json`` records those counts, and
``tests/unit/scripts/test_shell_complexity_ratchet.py`` fails if the measurement
disagrees.

.. code-block:: bash

   python scripts/measure_shell_complexity.py             # the table
   python scripts/measure_shell_complexity.py --verbose   # every function over 10, heaviest first
   python scripts/measure_shell_complexity.py --check     # compare against the baseline

**The check is exact in both directions**, exactly as the duplication ratchet is: a rise
is added complexity, and a fall fails too so that the win is banked in the commit that
earned it. If your change legitimately reduced complexity, rerun with ``--update`` and
commit the new baseline alongside it. The baseline also records each file's function count,
so adding or removing any function in these files fails until you rerun ``--update``.

The counting rule is written out in full in the script's module docstring, because with a
measurement like this the definition *is* the number. The short version: a function starts
at 1 and gains a point per ``if``/``elif``, loop, ``except`` handler, inline conditional,
``case``, comprehension generator and comprehension filter, and one per short-circuit in a
boolean operator — so ``a and b and c`` adds two. Three things deliberately do **not**
count: ``with``, ``assert``, and ``return``/``break``/``continue``.

.. note::

   ``with`` not counting is the one worth knowing: scoring it as a branch would mark a
   function down for using a context manager.

.. warning::

   Read the failure message before running ``--update``. A genuine split leaves every
   extracted helper in the same file, so the file's function count *rises* while its
   complexity falls. Complexity and function count falling together is the other shape — a
   method moved out into a module the file list does not name, which reads as progress
   here while the code is unchanged. The check calls that out when it sees it.

   For the same reason the script refuses to pass if ``poriscope/controllers/`` or
   ``poriscope/models/`` contains any ``.py`` file the list does not name. Add a new module
   there and the gate fails until you list it. ``poriscope/views/`` cannot be swept that
   way, since it holds modules that are deliberately out of scope, so an extraction into a
   new file there has to be added to ``SHELL_FILES`` by hand.

.. _mvc_boundary:

Analysis-Tab MVC Boundary
--------------------------

Like the ratchet above, this one affects you if you edit the analysis tabs, the widgets they
are built from, the app shell's own views and controllers, or the shared bases under
``poriscope/utils/``. Five rules keep computation in the Models and plugin access behind
``call()``:

1. **No View emits on the plugin bus, and the bus does not come back.** The removed
   ``global_signal`` bus (see :ref:`GlobalSignal`) is kept as a tripwire: reintroducing it
   in a View is caught here.
2. **No View imports a computation library to compute with** — ``numpy``, ``scipy``,
   ``sklearn``, ``hdbscan``, ``pandas``, ``fast_histogram`` or ``sqlite3``. An import used
   *only* to write a type is exempt: a method annotated ``Sequence[npt.NDArray[np.float64]]``
   is describing arrays the loader genuinely hands it to plot, and dropping the annotation
   would mean either lying about the parameter or adding a marshalling hop. ``--verbose``
   names the exempted imports so the exemption stays visible.
3. **No Controller reads a View private.** ``self.view._x`` reaches past the View's
   interface into its internals.
4. **No app-shell module imports from a plugin package.** ``poriscope/views/`` importing
   ``poriscope.plugins.analysistabs.utils.walkthrough`` is a layering inversion: the shell
   depending on a plugin.
5. **No analysis-tab module reaches a data plugin except through** ``call()``.
   ``MetaModel.call`` is the whole plugin-facing API a tab gets, and a Controller slot uses
   ``self.model.call(...)``;
   resolving an instance directly, touching ``data_plugin_controller``, or importing a
   concrete plugin class has gone around it.

``.mvc-boundary-allowlist.json`` records every violation that exists today, and
``tests/unit/scripts/test_mvc_boundary_allowlist.py`` fails if the measurement disagrees.

**Which files each rule reads.** Rules 1–3 classify every module under ``poriscope/`` into
a layer, by two tests: a directory whose contents are all one layer (``poriscope/views/`` and
``poriscope/plugins/analysistabs/utils/`` are View, ``poriscope/controllers/`` is Controller),
or a filename suffix that names the role wherever the module lives (``*View.py`` and
``*Controls.py`` are View, ``*Controller.py`` is Controller). The suffix test is what covers
``poriscope/utils/``, which is flat and holds bases for every layer — including eight
data-plugin bases that import ``numpy`` legitimately and are therefore in neither layer. Rule
4 is narrower on purpose: it reads only ``poriscope/views/``, ``poriscope/controllers/`` and
``poriscope/models/``, because ``poriscope/utils/plugin_schemas.py`` imports the plugin
package deliberately, to discover schemas.

If you add a widget or a base, name it for its role and it is measured with no edit to the
script. If you must name it something else, add its directory to ``VIEW_DIRS`` or
``CONTROLLER_DIRS`` — a module that falls into neither layer is silently unmeasured.

.. code-block:: bash

   python scripts/check_mvc_boundary.py             # the current state of each rule
   python scripts/check_mvc_boundary.py --verbose   # name every import and private attribute
   python scripts/check_mvc_boundary.py --check     # compare against the allowlist

This is a **progress metric**, not a pass/fail gate. Two entries remain by decision —
``numpy`` in ``MetadataView`` and ``ProteinView``, recorded as floors in 2.0.0 — and any
other entry is a regression.
What it prevents is a *new* violation slipping in unnoticed beside the known ones. As with
the duplication ratchet, the comparison is exact in both directions — if your change removes
a violation, rerun with ``--update`` and commit the new allowlist alongside it.

.. note::

   The counting rule is stated exactly in the script's module docstring, because the
   definition *is* the number. In particular an import contributes **one entry per import
   statement**, keyed by the dotted path as written: ``import numpy`` and
   ``import numpy.typing`` are two entries, not one module. An earlier hand count that
   conflated statements with distinct modules could not be reproduced, which is the reason
   the rule is now executable rather than described.

   A statement counts only if at least one name it binds is loaded somewhere other than an
   annotation — every load in the module, minus every load inside a parameter annotation, a
   return annotation, or the annotation half of ``x: T = v``. So ``x: np.ndarray =
   np.zeros(3)`` still counts, on its right-hand side. Two blind spots follow from reading
   annotations syntactically: a module-level type alias such as ``Frame = pd.DataFrame`` is
   an ordinary assignment and counts, while a string annotation is invisible and does not.
   Neither exists in the View layer today, and both are pinned by tests.

.. _recorded_actions_read_no_widgets:

Recorded Actions Read No Widgets
---------------------------------

This one affects you if you decorate a method with ``@register_action``. A recorded action
must be a pure function of its recorded arguments: a replay has to reproduce what the user
did, not press the button again against whatever the controls panel shows now, and it takes
intent, never data already on the plot. Two checks hold the rule:

``tests/unit/utils/test_recorded_actions_read_no_widgets.py``
   walks every declared action of every analysis tab, and everything it calls on its own class
   (a Controller action is followed into its View through ``self.view``, and a property read
   into its getter). It fails on a widget-value call with no arguments (``.text()``,
   ``.currentText()``, ``.getSelectedItems()`` and the like; ``Axes.text(x, y, s)`` draws and
   takes arguments, so it is not one), a call to ``collect_parameters``,
   ``get_selected_filters`` or ``_get_event_index_text``, a reach into an attribute named
   ``*controls`` (a call on the panel written as a bare statement, such as refilling a
   dropdown, is a write and is not counted), a read of state a widget handler or dialog sets
   (the analysis mode, the scope, the filter list, the Timer limits, the stored clustering
   settings, the last event button), and a parameter annotated with an
   ``Axes``, a numpy array or a data frame. It reads source with ``ast`` and builds no widget.
   A known exception is listed in the test's ``ALLOWED`` table with its reason and the condition
   that removes it, and an entry that no longer trips is itself a failure. It also fails if an
   analysis tab's View declares an action, since only a Controller's are recorded and replayed.

``poriscope.utils.ReplayGuard``
   is a tripwire. Each step of a replay (``poriscope.utils.replay_sequence``) and Undo's
   ``MetaController.replay`` run inside ``replaying()``, and the eight helpers
   that read a controls panel (``get_selected_filters``, ``_get_event_index_text`` and the six
   ``collect_parameters``) start with ``forbid_while_replaying(...)``, so a recorded action that
   reaches one raises ``ReplayWidgetReadError`` during a replay and nowhere else. It cannot see
   a direct ``.text()`` call; the static test covers those.

``tests/integration/flows/test_replay_guard_no_gui.py`` adds the behavioural check: each
declared action is recorded in one tab, replayed into a second tab whose widgets and stored
inputs have all been changed, and the data-plugin calls, plot cache, figures and the tab's
bookkeeping must match. It fails for a declared action that no scenario records, so a new
recorded action needs a scenario in the same commit. It checks the tabs Poriscope ships with,
listed in its ``TABS``; a contributor's tab is not checked, as the rest of a tab's behaviour is
not. A scenario whose action runs several channels on worker threads at once compares its plugin
calls in any order. The replay writes each step's recorded values into the panel before the
step runs, so this check cannot see a step that reads the panel; the static test above is what
catches that.

.. _golden_net_armed:

Is the Golden Net Armed?
-------------------------

``tests/test_safety_net_is_armed.py`` asserts that ``pytest-regressions`` is registered with
the running pytest session and that every fixture the checked-in golden files are written
against resolves. It needs no arguments and runs as part of a plain ``pytest``.

It exists because of how that dependency fails when it is missing. Every golden test requests
a fixture such as ``num_regression``, so an absent plugin makes them **error during setup**
rather than fail — which renders as a handful of errors beside several thousand passes, and
looks like an environment nit rather than like the entire numerical golden net not running.

.. note::

   If this test fails, install the development extras (``pip install -e ".[dev]"``) and
   rerun. ``pytest-regressions`` must be in both dev-dependency lists; see
   :ref:`test_suite_configuration`.

.. _pre_pr_checklist:

Pre-Pull-Request Compliance Checklist
---------------------------------------

.. important::

   This is the section to bookmark. Before opening or updating a pull request, walk
   through these steps in order. They mirror what CI checks, so a clean run here means CI
   should pass too.

.. tip::

   If you are *starting* a plugin rather than finishing one, generate it with
   ``python scripts/new_plugin.py`` — see :ref:`new_plugin_script` for a data plugin and
   :ref:`new_tab_script` for an analysis tab. Getting a signature or a docstring field
   wrong by hand is by far the most common reason a first plugin PR comes back, and the
   generator copies both verbatim out of the base class.

   **A generated analysis tab passes steps 1-3 as generated**, because a tab has no
   settings schema and no conformance recipe.

   **A generated data plugin passes steps 1 and 2 but not step 3**, and is not meant to:
   its methods still raise ``NotImplementedError``, it ships a placeholder parameter
   (``"My Parameter"``) with no default, and the conformance suite has no recipe for it.
   Each error names what it wants; see :ref:`plugin_conformance_testing`. A failure in
   step 1 or 2, by contrast, really is one you caused.

☐ **1. Apply automatic formatting and safe fixes.**

.. code-block:: bash

   pre-commit run --all-files --hook-stage manual

This runs ``black`` and ``ruff --fix`` and may modify your files. Review the diff,
then stage the changes.

☐ **2. Run strict validation.**

.. code-block:: bash

   pre-commit run --all-files

This runs the eight validation hooks listed in Pre-commit Hooks above.
Nothing here is auto-fixed for you — if ``mypy`` or ``pydoclint`` report a problem,
you need to edit the code or docstring yourself. See :ref:`docstring_consistency`
above if a pydoclint failure doesn't make sense, and :ref:`type_checking_policy` for
what mypy expects of new code.

.. note::

   Neither failure can be waived. There is no baseline left for ``pydoclint`` to
   forgive a new violation with, and the ``mypy`` annotation flags are on, so an
   unannotated function you add will fail here even though it would once have been
   skipped.

☐ **3. If you added or modified a plugin (or a ``Meta*`` base class), run the three
plugin gates.**

.. code-block:: bash

   pytest tests/unit/plugins
   python scripts/check_plugin_schemas.py

The first covers all three at once: interface compliance, settings-schema
consistency, and behavioural conformance. The second is the fast, pytest-independent
settings-schema check, useful when you only want to check the one plugin you are
working on (``python scripts/check_plugin_schemas.py MyEventFinder``). See
:ref:`plugin_compliance_testing`, :ref:`settings_schema_checking` and
:ref:`plugin_conformance_testing` above for what each one checks. A new filter, event
finder, event fitter, reader or conditioning loader needs a recipe in
``tests/unit/plugins/conformance/_recipes.py`` (see :doc:`conformance_recipes`);
conformance fails with a message telling you exactly where.

☐ **4. Run the test suite** — the same suite continuous integration runs on every
branch push:

.. code-block:: bash

   pytest -n auto

There is no subset and no marker filter: CI runs the whole suite everywhere, e2e tests
included. ``-n auto`` runs it in parallel through ``pytest-xdist``, one test file per
worker at a time. ``tests/conftest.py`` chooses the number of workers from your machine:
one per logical core, but no more than your free memory holds at about 2 GB each. Set
``PYTEST_XDIST_AUTO_NUM_WORKERS`` to choose the number yourself.

For per-marker counts and mean durations, run ``pytest --marker-stats``, serially: under
``-n`` the main process collects no tests, so it has nothing to report.

☐ **5. Check that the documentation still renders.**

.. code-block:: bash

   python scripts/generate_all_autodoc_rst.py
   sphinx-build -W --keep-going -b html -d docs/.doctrees docs/source docs/build

Warnings are errors here, and the same build runs on your pull request. See
:ref:`docs_render_check` above for why this is a separate gate from ``pydoclint``.

☐ **6. Update the changelog.**

Add a plain-language entry to ``changelog.md`` describing what changed, under the
appropriate existing heading — **one line per change, and no more**. The changelog is
written for users, so it carries the essential user-facing information and nothing else:
no sub-bullets, no measurements, and no explanation of why the change was made or what was
rejected along the way. A breaking change is still called out explicitly as breaking,
because that *is* user-facing. Reasoning that needs preserving belongs in ``DECISIONS.md``
instead.

.. warning::

   **If you are contributing from a fork** (the typical path for an external/
   community contribution), steps 1–5 above must be completed *before you push*.
   Fork-originated pull requests run in a restricted, read-only CI workflow that
   performs strict validation and the full test suite — it deliberately cannot
   auto-fix formatting or push corrections back to your branch, for security reasons.
   If you skip step 1 or 2 locally, CI will simply fail on something a maintainer has
   no way to fix for you, and you'll need to push a follow-up commit anyway.

Once all six boxes are checked, you're ready to open (or re-request review on) your
pull request.
