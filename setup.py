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

from setuptools import find_packages, setup

from poriscope.constants import __VERSION__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="poriscope",
    version=__VERSION__,
    author="Kyle Briggs & Alejandra Carolina González González",
    author_email="kbriggs@uottawa.ca",
    description="A tool for selecting and analyzing nanopore data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TCossaLab/data_selection.git",
    packages=find_packages(include=["poriscope", "poriscope.*"]),
    include_package_data=True,
    install_requires=[
        "PySide6==6.9.0",
        "numpy==2.2.6",
        "matplotlib==3.10.3",
        "pandas==2.2.3",
        "platformdirs==4.3.8",
        "scipy==1.15.3",
        "kneed==0.8.5",
        "fast-histogram==0.14",
        "sphinx==8.2.3",
        "sphinx-tabs==3.4.7",
        "furo==2024.8.6",
        "scikit-learn==1.6.1",
        "hdbscan==0.8.40",
    ],
    python_requires=">=3.12.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "poriscope = poriscope.main_app:main",
        ],
    },
)
