#!/usr/bin/env python3
import os
import sys
import time

import psutil

MARKER = "run_house.py"

def is_house(p):
    try:
        args = p.cmdline() or []
    except Exception:
        return False
    return any(a == MARKER or a.endswith("\\run_house.py")
               or a.endswith("/run_house.py") for a in args)

def houses():
    out = []
    for p in psutil.process_iter():
        try:
            if p.pid == os.getpid():
                continue
            if is_house(p):
                out.append(p)
        except Exception:
            pass
    return out

def listeners():
    return sorted({c.pid for c in psutil.net_connections(kind="inet")
                   if c.laddr and c.laddr.port == 7773
                   and c.status == psutil.CONN_LISTEN and c.pid})

def stop():
    hs = houses()
    for p in hs:
        try:
            p.kill()
        except Exception:
            pass
    for _ in range(10):
        time.sleep(0.5)
        if not houses():
            break
    left = houses()
    print(f"stopped {len(hs)} process(es); remaining: {[p.pid for p in left]}")
    return not left

def start():
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log = open(os.path.join(root, "state", "house_stdout.log"), "w")
    p = subprocess.Popen(
        [sys.executable, os.path.join(root, "run_house.py"), "--port", "7773"],
        cwd=root, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    print("started pid", p.pid)
    return p.pid

def status():
    hs = houses()
    print("run_house processes:", [(p.pid) for p in hs])
    print("7773 listener pids :", listeners())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "stop":
        stop()
    elif cmd == "start":
        start()
    elif cmd == "restart":
        stop()
        time.sleep(1)
        start()
    else:
        status()