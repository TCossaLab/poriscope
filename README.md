## SETUP
Install the required Python packages:

pip install -r requirements.txt

Note: Conda is not supported. You can make it work, but you're on your own. 

## Post-clone Setup

After cloning this repo, run:

python scripts/setup_hooks.py

## To emulate a pull/merge request at any point to rebuild the docs, run: 

python .git/hooks/post-merge 
