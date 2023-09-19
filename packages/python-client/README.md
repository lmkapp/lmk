
# LMK Python Client

<!-- [![Build Status](https://travis-ci.org/cfeenstra67/lmk.svg?branch=master)](https://travis-ci.org/cfeenstra67/lmk)
[![codecov](https://codecov.io/gh/cfeenstra67/lmk/branch/master/graph/badge.svg)](https://codecov.io/gh/cfeenstra67/lmk) -->

## Installation

You can install using `pip`:

```bash
pip install 'lmkapp[cli,jupyter]'
```

If you are using Jupyter Notebook 5.2 or earlier, you may also need to enable
the nbextension:
```bash
jupyter nbextension enable --py [--sys-prefix|--user|--system] lmk
```

## Development Installation

Create a dev environment:
```bash
python -m venv venv
```

Install the python package. This will also build the TS package.
```bash
pip install -e ".[dev,jupyter,cli,docs,types]"
```

## Docs Development

To build the docs, run:
```bash
pnpm build:docs
```
To run a development server, run:
```bash
pnpm dev:docs
```

## Jupyter Development

When developing your extensions, you need to manually enable your extensions with the
notebook / lab frontend. For lab, this is done by the command:

```bash
jupyter labextension develop --overwrite .
pnpm build
```

For classic notebook, you need to run:

```bash
jupyter nbextension install --sys-prefix --symlink --overwrite --py lmk
jupyter nbextension enable --sys-prefix --py lmk
```

Note that the `--symlink` flag doesn't work on Windows, so you will here have to run
the `install` command every time that you rebuild your extension. For certain installations
you might also need another flag instead of `--sys-prefix`, but we won't cover the meaning
of those flags here.

### How to see your changes
#### Typescript:
If you use JupyterLab to develop then you can watch the source directory and run JupyterLab at the same time in different
terminals to watch for changes in the extension's source and automatically rebuild the widget.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
pnpm watch
# Run JupyterLab in another terminal
jupyter lab
```

After a change wait for the build to finish and then refresh your browser and the changes should take effect.

#### Python:
If you make a change to the python code then you will need to restart the notebook kernel to have it take effect.

## Updating the version

To update the version, install tbump and use it to bump the version.
By default it will also create a tag.

```bash
pip install bump2version
bumpversion <pre|prekind|patch|minor|major>
```

## Publishing - PyPI

Build the python package:
```bash
pnpm build:python
```

Check the built assets:
```bash
pnpm pypi-check
```

Publish to the test index:
```bash
pnpm pypi-upload-test
```

Install from test index:
```bash
pip install --extra-index-url https://test.pypi.org/simple/ 'lmkapp[jupyter]==<version>'
```

Publish to real index:
```bash
pnpm pypi-upload
```

## Publishing - NPM

Build the npm package:
```bash
pnpm build:publish
```

Publish the npm package:
```bash
pnpm npm-publish
```
