# Commands

This page will show you all of the available commands and options for the LMK CLI. The primary function of the LMK CLI is to allow you to monitor, notify yourself, and interrupt command-line processes remotely.

## Common options

The following common options can be passed with any of the other commands:
```
@shell lmk --help | tail +7 | head -2
```

## Commands

### `login`

```
@shell lmk login --help | grep -v "\-\-help"
```

### `run`

```
@shell lmk run --help | grep -v "\-\-help"
```

### `monitor`

```
@shell lmk run --help | grep -v "\-\-help"
```

### `attach`

```
@shell lmk attach --help | grep -v "\-\-help" | grep -v "Options:"
```

### `jobs`

```
@shell lmk jobs --help | grep -v "\-\-help"
```

### `kill`

```
@shell lmk kill --help | grep -v "\-\-help"
```

### `notify`

```
@shell lmk notify --help | grep -v "\-\-help"
```

### `shell-plugin`

```
@shell lmk shell-plugin --help | grep -v "\-\-help"
```
