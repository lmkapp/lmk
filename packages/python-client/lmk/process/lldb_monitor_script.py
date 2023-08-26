# Original: https://opensource.apple.com/source/lldb/lldb-179.1/examples/python/process_events.py
import argparse
import asyncio
import enum
import json
import logging
import os
import signal
import sys
from typing import List, Optional, Any

import lldb


LOGGER = logging.getLogger("lldb_monitor_script")


def setup_logging(level: str) -> None:
    LOGGER.setLevel(getattr(logging, level.strip().upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s - %(levelname)s] %(message)s")
    )
    LOGGER.addHandler(handler)


class ProcessState(enum.Enum):
    """ """

    Attaching = lldb.eStateAttaching
    Connected = lldb.eStateConnected
    Crashed = lldb.eStateCrashed
    Detached = lldb.eStateDetached
    Exited = lldb.eStateExited
    Invalid = lldb.eStateInvalid
    Launching = lldb.eStateLaunching
    Running = lldb.eStateRunning
    Stepping = lldb.eStateStepping
    Stopped = lldb.eStateStopped
    Suspended = lldb.eStateSuspended
    Unloaded = lldb.eStateUnloaded


class ThreadStopReason(enum.Enum):
    """ """

    Exec = lldb.eStopReasonExec
    Breakpoint = lldb.eStopReasonBreakpoint
    Exception = lldb.eStopReasonException
    Instrumentation = lldb.eStopReasonInstrumentation
    Invalid = lldb.eStopReasonInvalid
    None_ = lldb.eStopReasonNone
    PlanComplete = lldb.eStopReasonPlanComplete
    Signal = lldb.eStopReasonSignal
    ThreadExiting = lldb.eStopReasonThreadExiting
    Trace = lldb.eStopReasonTrace


def run_commands(command_interpreter, commands):
    return_obj = lldb.SBCommandReturnObject()
    for command in commands:
        command_interpreter.HandleCommand(command, return_obj)
        if return_obj.Succeeded():
            LOGGER.debug(
                "Command `%s` was successful:\n%s", command, return_obj.GetOutput()
            )
        else:
            LOGGER.error("Command `%s` failed:\n%s", command, return_obj.GetError())


async def wait_for_event(
    listener: lldb.SBListener, timeout: float
) -> Optional[lldb.SBEvent]:
    """ """
    event = lldb.SBEvent()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: listener.WaitForEvent(timeout, event)
    )
    return event if result else None


async def wait_for_fd(fd: int) -> None:
    loop = asyncio.get_running_loop()
    future = asyncio.Future()
    loop.add_reader(fd, future.set_result, None)
    future.add_done_callback(lambda f: loop.remove_reader(fd))
    await future


def process_message(process: lldb.SBProcess, message: Any) -> None:
    if message["type"] == "send_signal":
        process.Signal(message["signal"])
        return

    LOGGER.warn("Unhandled message type: %s", message["type"])


async def run(process: lldb.SBProcess, listener: lldb.SBListener) -> int:
    pid = process.GetProcessID()

    LOGGER.debug(
        "Running w/ pid: %s, process: %s, state: %s",
        pid,
        process,
        ProcessState(process.GetState()),
    )

    stdin_fd = sys.stdin.fileno()

    timeout = 1
    stdin_task = asyncio.create_task(wait_for_fd(stdin_fd))
    event_task = asyncio.create_task(wait_for_event(listener, timeout))

    while True:
        await asyncio.wait(
            [stdin_task, event_task], return_when=asyncio.FIRST_COMPLETED
        )
        if stdin_task.done():
            line = os.read(stdin_fd, 1000)
            try:
                message = json.loads(line)
                LOGGER.debug("New message: %s", message)
                process_message(process, message)
            except json.JSONDecodeError:
                LOGGER.exception("Error processing message")
            stdin_task = asyncio.create_task(wait_for_fd(stdin_fd))

        if event_task.done():
            event = event_task.result()
            event_task = asyncio.create_task(wait_for_event(listener, timeout))

            if not event:
                continue

            stream = lldb.SBStream()
            event.GetDescription(stream)

            state_int = lldb.SBProcess.GetStateFromEvent(event)
            state = ProcessState(state_int)
            LOGGER.debug("State: %s, %s", state, stream.GetData())

            if state == ProcessState.Stopped:
                thread = process.GetSelectedThread()
                stop_reason = ThreadStopReason(thread.GetStopReason())
                print("THREAD", stop_reason)
                if stop_reason == ThreadStopReason.Signal:
                    sig = signal.Signals(thread.GetStopReasonDataAtIndex(0))
                    print("SIGNAL", sig)
                LOGGER.info("process %d stopped", pid)
                continue

            if state == ProcessState.Exited:
                exit_desc = process.GetExitDescription()
                if exit_desc:
                    LOGGER.info(
                        "process %d exited with status %s: %s",
                        pid,
                        process.GetExitStatus(),
                        exit_desc,
                    )
                else:
                    LOGGER.info(
                        "process %d exited with status %s", pid, process.GetExitStatus()
                    )
                return process.GetExitStatus()

            if state == ProcessState.Crashed:
                LOGGER.info("process %d crashed", pid)
                exit_status = -1
                try:
                    exit_status = process.GetExitStatus()
                except Exception:
                    LOGGER.exception("Error getting exit status")
                return exit_status

            if state == ProcessState.Detached:
                LOGGER.error("process %d detached unexpectedly", pid)
                return -1

            if state == ProcessState.Running:
                LOGGER.info("process %d resumed", pid)
                continue

            if state == ProcessState.Unloaded:
                LOGGER.info("process %d unloaded, this shouldn't happen", pid)
                continue

            if state == ProcessState.Connected:
                LOGGER.info("process %d connected", pid)
                continue

            if state == ProcessState.Attaching:
                LOGGER.info("process %d attaching", pid)
                continue

            if state == ProcessState.Launching:
                LOGGER.info("process %d launching")
                continue

            LOGGER.warn("Unhandled state: %s", state)


async def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int, help="Pid to monitor")
    parser.add_argument("output_file", help="File to redirect output to")
    parser.add_argument("-l", "--log-level", default="ERROR", help="Set log level")
    parser.add_argument(
        "-m", "--message", default=None, help="Display message when taking over process"
    )

    args = parser.parse_args(argv)

    setup_logging(args.log_level)

    LOGGER.info("Stopping %d", args.pid)
    os.kill(args.pid, signal.SIGSTOP)

    debugger = lldb.SBDebugger.Create(False)
    debugger.SetAsync(True)

    command_interpreter = debugger.GetCommandInterpreter()

    signals = {sig.name for sig in signal.Signals} - {"SIGKILL"}
    stop_signals = {"SIGTSTP", "SIGSTOP"}
    signals -= stop_signals

    run_commands(
        command_interpreter,
        [
            f"process handle -p true -s false -n true {' '.join(signals)}",
            f"process handle -p true -s true -n true {' '.join(stop_signals)}",
        ],
    )

    target = debugger.CreateTarget("")

    if not target:
        LOGGER.error("Target launch failed")
        return 1

    error = lldb.SBError()
    listener = lldb.SBListener("event_listener")

    process = target.AttachToProcessWithID(listener, args.pid, error)
    if not process:
        LOGGER.error("Process attach failed")
        return 1

    if process.GetProcessID() == lldb.LLDB_INVALID_PROCESS_ID:
        LOGGER.error("Invalid pid: %d", args.pid)
        return 1

    if not error.Success():
        stream = lldb.SBStream()
        error.GetDescription(stream)
        LOGGER.error("Process attach failed: %s", stream.GetData())
        return 1

    commands = [
        f"expr int $fd = (int) open({json.dumps(args.output_file)}, 1089)",
    ]
    if args.message is not None:
        commands.append(f"expr int $xd = (int) dup(1)")

    commands.extend(
        [
            f"expr (void) dup2($fd, 1)",
            f"expr (void) dup2($fd, 2)",
        ]
    )

    if args.message is not None:
        commands.extend(
            [
                f"expr (void) write($xd, {json.dumps(args.message)}, {len(args.message)})",
                f"expr (void) close($xd)",
            ]
        )

    commands.append(f"expr (void) close($fd)")

    run_commands(command_interpreter, commands)
    process.Continue()

    sys.stdout.write(json.dumps({"type": "attached"}) + "\n")
    sys.stdout.flush()
    try:
        exit_code = await run(process, listener)
        sys.stdout.write(json.dumps({"type": "exit", "exit_code": exit_code}) + "\n")
        sys.stdout.flush()
    finally:
        LOGGER.info("Terminating...")
        process.Detach()
        debugger.Terminate()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
