"""Wait for process-tree setup before launching a Python or MATLAB stage worker."""
import subprocess
import sys


if __name__ == '__main__':
    if sys.stdin.readline() != 'start\n':
        sys.exit(1)
    sys.exit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
