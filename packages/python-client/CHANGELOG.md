# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2023-07-29

- Creating initial version of CLI to monitor running scripts.

- CLI works both for running and attaching to running processes via lldb.

- Created shell plugin to monitor jobs w/ shell syntax.

- Initial implementation for interactive Jupyter sessions

- Improved top-level `lmk` API--mostly renaming methods, e.g. `send_notification` -> `notify`, `authenticate` -> `login`

- Unified channels fetching between `lmk.jupyter` and `lmk.instance`

- Added patches for better `repr` methods for notification channels

## [0.0.7] - 2023-04-19

- Update plugin version spec to use a tilde because caret isn't working for some reason

## [0.0.6] - 2023-04-19

- Fix jupyter extension asset paths in `pyproject.toml`

## [0.0.5] - 2023-04-19

- Add missing `typing_extensions` and `urllib3` dependencies

## [0.0.4] - 2023-04-19

- Published package to pypi

## [0.0.3] - 2023-04-19

### Changed

- Updated npm metadata, published `lmk-jupyter` to npm.

## [0.0.2] - 2023-04-17

### Changed

- Got both python and npm package builds working and changed name of js package to `lmk-jupyter`.

## [0.0.1] - 2023-04-17

### Added

- Initial source code for Python package and Jupyter Widget. This was migrated out of the `lmk` monorepo as for now I don't want to open source that.
