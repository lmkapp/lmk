---
sidebar_position: 2
---
# Monitoring an already running script

:::note

Make sure you've installed the `cli` extras for the package:
```bash
pip install "lmkapp[cli]"
```

:::

## Environment setup

One of the design principles of LMK is that you should be able to decide you want to monitor a long-running process _after_ you've already started it. Often something takes longer than you were expecting, or you might just not remember that you want to monitor it beforehand. With the Jupyter integration this is relatively easy--you can simply use the Jupyter widget to enable or disable notifications at any time while your notebook is running. For command-line processes, however, this is a slightly more involved process. LMK aims to make this easy, but there are limitations imposed by various operating systems that prevent us from making it completely seemless.

The method that LMK uses to monitor already-running scripts is by attaching a debugger to the process. The compatibility of this depends on your OS. You can run the following command to check if monitoring existing processes will work on your system (see [command documentation here](/docs/cli/commands#check-existing-script-monitoring)):

```bash
lmk check-existing-script-monitoring
```

Details for tested operating systems can be found below:

- `OS X` -  The debugger used is `lldb`. However, you must partially [disable system integrity protection](https://developer.apple.com/documentation/security/disabling_and_enabling_system_integrity_protection) in order for `lldb` to be allowed to attach to running processes. **This may have security implications, so you'll have to decide for yourself whether this is a path you want to take. See the link above from Apple's documentation for more information.**

<details><summary>Instructions for allowing `lldb` to attach to processes on OS X</summary>
<p>

1. [Restart your computer in recovery mode](https://support.apple.com/en-us/HT201314)
2. Run `csrutil enable --without debug`
3. Restart your computer again.

</p>
</details>

_NOTE_: Attaching a debugger does add a small amount of overhead to the running process. In most cases this shouldn't be noticable, however if your script is particularly performance-sensitive it may be a concern. In this case, you'll have to rely on the [lmk run](/docs/cli/process) method of monitoring processes to use LMK.

## Monitoring your running script

To monitor a running script by PID, run:

```bash
lmk monitor <pid>
```

Though that isn't the most ergonomic method; you have to find your process's PID using some method like `pgrep` or by printing it out at the beginning of the process, which is a bit of a bother.

LMK also supports using bash jobs syntax with the shell plugin installed, which allows a much nicer workflow:

1. Install the LMK shell plugin using `lmk shell-plugin --install`
1. Run your script normally.
2. Pause it using `Ctrl-Z`
3. Use the built-in `jobs` command in your shell to get the job number; this is usually just `1` unless you have more than one job running at once.
4. Monitor the process using `lmk monitor %<job_id>` e.g. `lmk monitor %1`

From here, you can see it in `lmk jobs` and treat it the same as you would if you monitored the job from the beginning using [`lmk run`](/docs/cli/process), and interact with it using the other commands such as [`lmk attach`](/docs/cli/commands#attach), [`lmk kill`](/docs/cli/commands#kill), etc.
