# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `whoami` CLI command to print user info about the current user.

## [1.1.3] - 2023-10-08

### Fixed

- Fixed incorrect `shell_cli.sh` path in shell plugin.

### Added

- Added basic e2e tests for CLI and jupyter

## [1.1.2] - 2023-10-05

### Fixed

- Fixed more typing issues

## [1.1.1] - 2023-10-05

### Fixed

- Fixed typing issues from 1.1.0

## [1.1.0] - 2023-10-05

### Added

- `lmk check-existing-script-monitoring` command to check if monitoring existing scripts is supported.

### Changed

- Updated OpenAPI spec

### Fixed

- Traceback when monitoring a script with the CLI and it finishing normally.

## [1.0.6] - 2023-10-01

### Fixed

- Fix bug in CLI where if the LMK config file has not been initialized, the `set_instance()` call fails.

## [1.0.5] - 2023-09-20

### Fixed

- Fix colab support after updates to `notebook_info.py`

## [1.0.4] - 2023-09-20

### Fixed

- Fix issue w/ some notebook environments where getting the notebook name does not work w/ the token in the query string.

- Fix issue where an interactive session does not get created if we can't find the notebook name.

## [1.0.3] - 2023-09-18

### Added

- Add type checking with `mypy`

- Add google colab support

### Fixed

- Fix more compatiblility issues w/ older Python versions.

## [0.1.2] - 2023-09-02

### Fixed

- Fix config file usage; everything was being overwritten on instantiation of the `Instance`.

## [0.1.1] - 2023-09-02

### Fixed

- Fix bug w/ API url, where it could be set to `None` which would cause issues

- Compatibility--previously this package would only work w/ Python 3.11; now it works with python 3.7+

## [0.1.0] - 2023-07-29

### Added

- Creating initial version of CLI to monitor running scripts.

- CLI works both for running and attaching to running processes via lldb.

- Created shell plugin to monitor jobs w/ shell syntax.

- Initial implementation for interactive Jupyter sessions

- Improved top-level `lmk` API--mostly renaming methods, e.g. `send_notification` -> `notify`, `authenticate` -> `login`

- Unified channels fetching between `lmk.jupyter` and `lmk.instance`

- Added patches for better `repr` methods for notification channels

## [0.0.7] - 2023-04-19

### Fixed

- Update plugin version spec to use a tilde because caret isn't working for some reason

## [0.0.6] - 2023-04-19

### Fixed

- Fix jupyter extension asset paths in `pyproject.toml`

## [0.0.5] - 2023-04-19

### Fixed

- Add missing `typing_extensions` and `urllib3` dependencies

## [0.0.4] - 2023-04-19

### Added

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
