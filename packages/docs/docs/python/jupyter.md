---
sidebar_position: 1
---
# Monitoring a Jupyter Notebook

:::note

Make sure you've installed the `jupyter` extras for the package:
```bash
pip install "lmkapp[jupyter]"
```

Or from within a Jupyter notebook:
```bash
!pip install "lmkapp[jupyter]"
```

:::

To monitor your jupyter notebooks with LMK, simply run the following code in a new cell:
```python
import lmk

# This assumes this is the last line in the cell you are running.
# If it is not, use `display(lmk.jupyter)` instead
lmk.jupyter
```

That's it! You should see something like this in your notebook:

![Jupyter Widget Screenshot - Not Authenticated](/img/screenshot-3.png)

Click the button on the widget to log in (or run [`lmk.login()`](/docs/python/api#login)), or sign up if you don't have an existing LMK account. You'll need an account to use LMK, but you'll only have to pay if you want to send yourself notifications after your 30 day trial. **No payment information is required for sign up, all you need is an email address.**

After you've authenticated, the widget should look like this:

![Jupyter Widget Screenshot](/img/screenshot-2.png)

As you run your code, at any time you can use the widget to change whether you'd like to receive a notification when it finishes running, and/or change the notification channel that you'd like to notify. You can check the status of your notebook also perform all of the same actions in the [LMK app](https://app.lmkapp.dev) as well.

Read on to see how you can use the `%%lmk` cell magic function to automatically enable monitoring when you start running a particular cell.

## `lmk` Cell Magic

When you import `lmk`, There is an `lmk` jupyter cell magic that is automatically registered that can be used to automatically enable monitoring when a cell starts to run. It can be used as follows:

```python
%%lmk on=stop
import time

time.sleep(10)
```

If you run that cell, you will send yourself a notification using the current [default notification channel](/docs/python/api#default-notification-channel) when the cell is finished running.

Arguments for the cell magic:

- `on=<stop|error>` - indicate whether to notify yourself whenever the currently queued cell(s) finish with any status (`stop`), or only if an error is encountered (`error`)

- `[immediate]` - optional; by default LMK will not notify you if the cell(s) run for less than 2 seconds, since it's likely that you'll see the failure and getting a notification in addition wouldn't be useful. You can add the `immediate` keyword to disable this behavior.
