#!/usr/bin/env python3
"""지정 초 내에 자식 프로세스를 강제 종료하는 얇은 래퍼.

사용:
    python run_with_timeout.py 600 sitekg-agent --task-id 44 ...
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys


def main() -> int:
    timeout = int(sys.argv[1])
    cmd = sys.argv[2:]
    proc = subprocess.Popen(cmd, start_new_session=True)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # 전체 프로세스 그룹 kill (자식의 자식까지)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        print(f"[run_with_timeout] TIMEOUT after {timeout}s", file=sys.stderr)
        return 124
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
