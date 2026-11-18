## SETUP
Note: Conda is not supported. You can make it work, but you're on your own. 
Make sure you have Python 3.12 or newer installed (python --version); CI tests 3.12 and 3.14.

For regular users, you can install the latest stable release of poriscope directly from PyPi using pip or similar. Simply run:

pip install poriscope 

As a developer:

`git clone https://github.com/TCossaLab/poriscope.git`

`cd poriscope`

`pip install -e ".[dev,docs]"` (the test and lint tools, plus Sphinx for the post-merge docs build)

`python scripts/setup_hooks.py` (installs the pre-commit and post-merge hooks and the git flow tag prefix; the only post-clone step)

To rerun what the post-merge hook does after a pull: `python scripts/hooks/post-merge.py`

To use a stable version (does not allow retroactive pulls): 
`python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@main"`

Then from any cmd you will be able to run the `poriscope` command to open the app.

*If you have a previous version of poriscope installed, make sure to run: 

`pip uninstall poriscope`

## Documentation can be found
https://tcossalab.github.io/poriscope/ 

## Poriscope Tutorial Series
https://youtube.com/@tcossalab?si=A8Wy8yHOXiwSXu5F 

## Data
Tutorial Series data is available on FRDR: https://doi.org/10.20383/103.01695

## Architecture note
The architecture described in the [Poriscope paper](https://doi.org/10.5334/jors.703) (JORS, 2026) corresponds to version 1.5.0 and applies through the 1.x releases. Since version 2.0.0, the central signal dispatcher has been removed. The main components (models, views, controllers and data plugins) keep the same roles; what changed is how they communicate. See [Global Signal (removed)](https://tcossalab.github.io/poriscope/signals/global_signal/global_signal.html) and [Data Plugin Controller Signal (replaced)](https://tcossalab.github.io/poriscope/signals/data_plugin_controller_signal/data_plugin_controller_signal.html) for details.
