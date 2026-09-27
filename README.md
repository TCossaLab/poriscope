## SETUP
Note: Conda is not supported. You can make it work, but you're on your own. 
Make sure you have Python 3.12.10 or newer installed (python --version) to avoid dependencies compatibility issues.

For regular users, you can install the latest stable release of poriscope directly from PyPi using pip or similar. Simply run:

pip install poriscope 

As a developer:

`git clone https://github.com/TCossaLab/poriscope.git`

`cd poriscope`

`pip install -e ".[dev,docs]"` (the test and lint tools, plus Sphinx for the post-merge docs build)

`python scripts/setup_hooks.py` (installs the pre-commit and post-merge hooks and the git flow tag prefix)

To use a stable version (does not allow retroactive pulls): 
`python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@main"`

Then from any cmd you will be able to run the `poriscope` command to open the app.

*If you have a previous version of poriscope installed, make sure to run: 

`pip uninstall poriscope`

## Post-clone Setup for developers

`python scripts/setup_hooks.py`, above, is the only post-clone step. To emulate a pulled run:
`python .git/hooks/post-merge`

## Documentation can be found
https://tcossalab.github.io/poriscope/ 

## Poriscope Tutorial Series
https://youtube.com/@tcossalab?si=A8Wy8yHOXiwSXu5F 

## Data
Tutorial Series data is available on FRDR: https://doi.org/10.20383/103.01695