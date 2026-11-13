"""Tie each desktop worker and its descendants to one cancellable process tree."""
from contextlib import contextmanager
import os
import signal
import subprocess


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@contextmanager
def worker_process(command, env):
    with subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                          start_new_session=os.name != 'nt') as process:
        job = None
        if os.name == 'nt':
            # The launcher waits on stdin until it and any future descendants are in the job.
            job = kernel.CreateJobObjectW(None, None)
            if not job or not kernel.AssignProcessToJobObject(job, int(process._handle)):
                error = ctypes.WinError(ctypes.get_last_error())
                if job:
                    kernel.CloseHandle(job)
                process.stdin.close()
                raise error

        def stop():
            if job:
                if not kernel.TerminateJobObject(job, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                kill_group(process.pid)

        try:
            process.stdin.write('start\n')
            process.stdin.close()
            yield process, stop
        finally:
            try:
                stop()
            finally:
                if job:
                    kernel.CloseHandle(job)
