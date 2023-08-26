# Original: https://opensource.apple.com/source/lldb/lldb-179.1/examples/python/process_events.py
import os
import sys
from typing import List

import lldb


# print("HELLO WORLD", lldb, sys.executable, sys.version, sys.argv)


def run_commands(command_interpreter, commands):
    return_obj = lldb.SBCommandReturnObject()
    for command in commands:
        command_interpreter.HandleCommand( command, return_obj )
        if return_obj.Succeeded():
            print("SUCCESS", return_obj.GetOutput())
        else:
            print("FAILED", return_obj)
    

def main(argv: List[str]) -> None:
    target_pid = int(argv[0])

    # Create a new debugger instance
    debugger = lldb.SBDebugger.Create(False)
    debugger.SetAsync(True)
    command_interpreter = debugger.GetCommandInterpreter()

    run_commands(
        command_interpreter,
        [
            "process handle -p true -s false -n true SIGINT SIGTERM SIGCONT",
            "process handle -p true -s true -n true SIGTSTP SIGSTOP"
        ]
    )

    target = debugger.CreateTargetWithFileAndArch(None, lldb.LLDB_ARCH_DEFAULT)
    print("TARGET", target)

    if not target:
        print("TARGET LAUNCH FAILED")
        return
    
    attach_info = lldb.SBAttachInfo(target_pid)

    error = lldb.SBError()
    process = target.Attach(attach_info, error)
    if not process or process.GetProcessID() == lldb.LLDB_INVALID_PROCESS_ID:
        print("PROCESS ATTACH FAILED")
        return

    pid = process.GetProcessID()
    print("PID", pid, process, process.GetState())
    listener = lldb.SBListener("event_listener")

    process.GetBroadcaster().AddListener(listener, lldb.SBProcess.eBroadcastBitStateChanged | lldb.SBProcess.eBroadcastBitStructuredData)
    process.Continue()
    # print("HERE123", listener.WaitForEvent(1, lldb.SBEvent()))
    # try:
    #     process.Continue()
    # except BaseException as err:
    #     print("ERROR", err)
    # print("HERE123", listener.WaitForEvent(1, lldb.SBEvent()))

    stop_idx = 0
    done = False

    while not done:
        event = lldb.SBEvent()
        timeout = 10
        if not listener.WaitForEvent(timeout, event):    
            # timeout waiting for an event
            print("no process event for %u seconds, killing the process..." % timeout)
            done = True
            continue
        
        state = lldb.SBProcess.GetStateFromEvent(event)
        print("STATE", state, event.GetType())
        if lldb.SBProcess.EventIsStructuredDataEvent(event):
            print("IS STRUCTURED")
            data = lldb.SBProcess.GetStructuredDataFromEvent(event)
            print("DATA", data)
        else:
            print("NOT STRUCTURED")
        if state == lldb.eStateStopped:
            thread = process.GetThreadAtIndex(0)
            print("THREAD", thread.GetStopReason())
            print("THREAD 2", thread.GetStopDescription(1000))
            # for thread in process:
            #     print("STOP REASON", thread)
            if stop_idx == 0:
                print("attached to process %u" % (pid))
                # for m in target.modules:
                #     print(m)
                # run_commands(command_interpreter, [])
            else:
                print("process %u stopped" % (pid))
                # run_commands (command_interpreter, [])
            
            continue

        if state == lldb.eStateExited:
            exit_desc = process.GetExitDescription()
            if exit_desc:
                print("process %u exited with status %u: %s" % (pid, process.GetExitStatus(), exit_desc))
            else:
                print("process %u exited with status %u" % (pid, process.GetExitStatus ()))
            # run_commands (command_interpreter, [])
            done = True
            continue
        
        if state == lldb.eStateCrashed:
            print("process %u crashed" % (pid))
            # run_commands(command_interpreter, [])
            done = True
            continue
        
        if state == lldb.eStateDetached:
            print("process %u detached" % (pid))
            done = True
            continue

        if state == lldb.eStateRunning:
            print("process %u resumed" % (pid))
            continue

        if state == lldb.eStateUnloaded:
            print("process %u unloaded, this shouldn't happen" % (pid))
            done = True
            continue

        if state == lldb.eStateConnected:
            print("process connected")
            continue

        if state == lldb.eStateAttaching:
            print("process attaching")
            continue

        if state == lldb.eStateLaunching:
            print("process launching")
            continue
        
        print("UNHANDLED", state)

    # process.Detach()
    print("TERMINATING")
    lldb.SBDebugger.Terminate()


if __name__ == "__main__":
    main(sys.argv[1:])
