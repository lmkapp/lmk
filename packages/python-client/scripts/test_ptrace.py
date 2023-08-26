import ptrace.debugger
import signal
import subprocess
import sys

def debugger_example(pid):
    debugger = ptrace.debugger.PtraceDebugger()

    print("Attach the running process %s" % pid)
    process = debugger.addProcess(pid, False)
    # process is a PtraceProcess instance
    print("IP before: %#x" % process.getInstrPointer())

    print("Execute a single step")
    process.singleStep()
    # singleStep() gives back control to the process. We have to wait
    # until the process is trapped again to retrieve the control on the
    # process.
    process.waitSignals(signal.SIGTRAP)
    print("IP after: %#x" % process.getInstrPointer())

    process.detach()
    debugger.quit()

def main():
    args = [sys.executable, '-c', 'import time; time.sleep(60)']
    child_popen = subprocess.Popen(args)
    debugger_example(child_popen.pid)
    child_popen.kill()
    child_popen.wait()

if __name__ == "__main__":
    main()
