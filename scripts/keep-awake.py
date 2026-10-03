#!/usr/bin/env python3
"""Keep the temporary macOS server awake independently of the terminal."""
import os
import plistlib
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"start", "stop"}:
        raise SystemExit("Usage: keep-awake.py start|stop")
    if sys.platform != "darwin":
        return
    runtime = Path(__file__).resolve().parent.parent / ".runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    label = "com.fengsihao23.paidquiz.keepawake"
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{label}"
    legacy_pid = runtime / "caffeinate.pid"
    if legacy_pid.exists():
        try:
            pid = int(legacy_pid.read_text().strip())
            if pid > 1:
                command = subprocess.run(
                    ["/bin/ps", "-p", str(pid), "-o", "comm="],
                    capture_output=True, text=True, check=False,
                ).stdout.strip()
                if command in {"caffeinate", "/usr/bin/caffeinate"}:
                    os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
        legacy_pid.unlink(missing_ok=True)
    loaded = subprocess.run(
        ["/bin/launchctl", "print", service],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if sys.argv[1] == "stop":
        if loaded:
            subprocess.run(["/bin/launchctl", "bootout", service], check=True)
        print("本项目防休眠已停止。")
        return
    if not loaded:
        plist = runtime / "keep-awake.plist"
        with plist.open("wb") as output:
            plistlib.dump({
                "Label": label,
                "ProgramArguments": ["/usr/bin/caffeinate", "-i"],
                "RunAtLoad": True,
                "KeepAlive": True,
            }, output)
        plist.chmod(0o600)
        subprocess.run(["/bin/launchctl", "bootstrap", domain, str(plist)], check=True)
    for _ in range(20):
        status = subprocess.run(
            ["/bin/launchctl", "print", service],
            capture_output=True, text=True, check=False,
        )
        if status.returncode == 0 and "state = running" in status.stdout:
            print("本项目防休眠已启用；合盖或手动睡眠仍会中断服务。")
            return
        time.sleep(0.25)
    raise SystemExit("防休眠进程启动失败，请检查本项目 launchd 任务。")


if __name__ == "__main__":
    main()
