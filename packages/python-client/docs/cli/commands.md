---
sidebar_position: 3
---
# Commands

This page will show you all of the available commands and options for the LMK CLI. The primary function of the LMK CLI is to allow you to monitor, notify yourself, and interrupt command-line processes remotely.

## Common options

The following common options can be passed with any of the other commands:
```
@shell python -m lmk --help | sed 's/python -m lmk/lmk/' | head -9
```

## Commands

### `login`

```
@shell python -m lmk login --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `run`

```
@shell python -m lmk run --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `monitor`

```
@shell python -m lmk run --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `attach`

```
@shell python -m lmk attach --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help" | grep -v "Options:"
```

### `jobs`

```
@shell python -m lmk jobs --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `kill`

```
@shell python -m lmk kill --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `notify`

```
@shell python -m lmk notify --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```

### `shell-plugin`

```
@shell python -m lmk shell-plugin --help | sed 's/python -m lmk/lmk/' | grep -v "\-\-help"
```
