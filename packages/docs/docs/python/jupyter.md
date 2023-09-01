---
sidebar_position: 1
---
# Monitoring Notebooks

:::note

Make sure you've installed the `jupyter` extras for the package:
```bash
pip install "lmk-python[jupyter]"
```

Or from within a Jupyter notebook:
```bash
!pip install "lmk-python[jupyter]"
```

:::

To monitor your jupyter notebooks with LMK, simply run the following code in a new cell:
```python
import lmk

# This assumes this is the last line in the cell you are running.
# If it is not, use `display(lmk.jupyter)` instead
lmk.jupyter
```

That's it! You should see the LMK jupyter widget. You'll be prompted to authorize the app, which will allow you to log in or sign up if you don't have an existing LMK account. You'll need an account to use LMK, but you'll only have to pay if you want to send yourself notifications after your 30 day trial.

## `lmk` Cell Magic

When you import `lmk`, There is an `lmk` jupyter cell magic that is automatically registered that can be used to automatically enable monitoring when a cell starts to run. It can be used as follows:

```python
%%lmk on=stop
import time

time.sleep(10)
```

If you run that cell, you will send yourself a notification using the current [default notification channel](/docs/python#default-notification-channel) when the cell is finished running.

Arguments for the cell magic:

- `on=<stop|error>` - indicate whether to notify yourself whenever the currently queued cell(s) finish with any status (`stop`), or only if an error is encountered (`error`)

- `[immediate]` - optional; by default LMK will not notify you if the cell(s) run for less than 2 seconds, since it's likely that you'll see the failure and getting a notification in addition wouldn't be useful. You can add the `immediate` keyword to disable this behavior.
