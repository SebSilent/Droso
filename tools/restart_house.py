#!/usr/bin/env python3
"""Restart the live house on 7773 with current code (used after code changes)."""
import subprocess
import sys
import time

import psutil

for p in psutil.process_iter():
    try:
        if "run_house.py" in " ".join(p.cmdline() or []):
            p.kill()
    except Exception:
        pass
time.sleep(2)
log = open("C:/Projects/HybridLLM/state/house_stdout.log", "w")
n = subprocess.Popen(
    [sys.executable, "C:/Projects/HybridLLM/run_house.py", "--port", "7773"],
    cwd="C:/Projects/HybridLLM", stdout=log, stderr=subprocess.STDOUT,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("house pid", n.pid)