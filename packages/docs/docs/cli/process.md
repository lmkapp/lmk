---
sidebar_position: 1
---
# Running a script with monitoring

:::note

Make sure you've installed the `cli` extras for the package:
```bash
pip install "lmkapp[cli]"
```

:::

To run a script with monitoring, first ensure that you've logged in to LMK. You should only have to do this once:
```bash
lmk login
```

Then, simply wrap your command in the `lmk run` command:
```bash
lmk run ./my_script.sh
```

If you want to pass arguments to your script, you'll have to enclose the command in quotes:
```bash
lmk run "python script.py --arg1 --arg2"
```

Now your script will be monitored by LMK, and you can view the progress via the LMK web app.

You will also see the logs from your script in your console. At any time, you can press `Ctrl-C`, at which point you will be presented with three options:
- `r` - resume attachment
- `i` - interrupt script
- `d` - detach; the script will keep running, and you can use `lmk attach` to re-attach at any time

If you detach from the script, you should be able to see your job running via the `lmk jobs` command:
```bash
lmk jobs
```

This will also display the ID of each job. If you want to re-attach to a job that you've detached from, simply run:
```bash
lmk attach <job_id>
```

See the [Commands Reference](/docs/cli/commands) for all available commands.
