# Contributing to Poriscope

1. **Branch from `develop`, not `main`.** Poriscope uses git flow: feature branches start
   from `develop` (`git flow feature start <name>`), and `main` only receives releases.
2. **Set up a development checkout:**

   ```
   git clone https://github.com/TCossaLab/poriscope.git
   cd poriscope
   pip install -e ".[dev,docs]"
   python scripts/setup_hooks.py
   ```

   `[dev]` adds the test and lint tools, `[docs]` adds Sphinx for the post-merge docs build,
   and `setup_hooks.py` installs the pre-commit and post-merge hooks.
3. **Before opening a pull request**, work through the
   [pre-PR checklist](https://tcossalab.github.io/poriscope/utils/user_manuals/plugins_manual/development_workflow/quality_control.html#pre-pr-checklist).
   It covers the full `pytest` run, the pre-commit gates and the ratchets that CI enforces;
   the rest of the [quality control page](https://tcossalab.github.io/poriscope/utils/user_manuals/plugins_manual/development_workflow/quality_control.html)
   explains each one.
4. **Adding a plugin or an analysis tab?** Generate it rather than writing it by hand:
   `python scripts/new_plugin.py --list` shows the plugin families and the `AnalysisTab`
   keyword. The [plugins manual](https://tcossalab.github.io/poriscope/) covers the rest.
5. **Add one line to `changelog.md`** under the in-progress release's header for any code
   change, and call a breaking change out as breaking.
6. **Reviewers** are requested automatically from `.github/CODEOWNERS`. It routes a pull
   request to the people who know that code; it is advisory, not a merge gate.
