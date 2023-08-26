
# Introduction

LMK is a set of tools intended to help you monitor your long-running processes within Jupyter Notebooks and command-line scripts. You'll finally be able to free yourself of the urge to check back on your jobs frequently. Similarly, you can avoid disappointment when you fail to check back only to find that it ended up failing early in the run!

When you monitor a long-running job with LMK, you can remotely see the status of the job and choose at any time to send yourself a notification if it stops or fails with an error.

<!-- TODO: add link to general feedback form here -->
There are currently two different ways you can use LMK (more to come!):

- Monitor your running Jupyter notebooks and optionally notify yourself when they stop running

- Monitor long-running command line tasks

## Installation

LMK is distributed as a python package, so you can install it using `pip`:
```bash
pip install lmk-python
```
If you're going to use it to monitor a jupyter notebook, you
should install the jupyter extras:
```bash
pip install "lmk-python[jupyter]"
```

## Get Started

To get started with using LMK, choose one of the two use-cases below that you'd like to use it for:
- [Monitor a Jupyter Notebook](/docs/jupyter)
- [Monitor a Command Line Script](/docs/process)
