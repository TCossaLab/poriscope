## SETUP
Note: Conda is not supported. You can make it work, but you're on your own. 
Make sure you have Python 3.12.10 installed (python --version) to avoid dependencies compatibility issues.

As a developer:

git clone https://github.com/TCossaLab/poriscope.git
cd poriscope
pip install -e .

To use a stable version (does not allow retroactive pulls): 
python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@main"

Then from any cmd you will be able to run the 'poriscope' command to open the app.

*If you have a previous version of poriscope installed, make sure to run: 
pip uninstall poriscope


## Post-clone Setup dor developers

After cloning this repo, run:

python scripts/setup_hooks.py (To enable pre-commit and post-merge)

To emulate a pulled run:
python .git/hooks/post-merge

## Documentation can be found
https://tcossalab.github.io/poriscope/ 
