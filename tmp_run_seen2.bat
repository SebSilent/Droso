@echo off
REM One-off: the four seen-set cold cells the killed run missed.
cd /d C:\Projects\HybridLLM
set PY=.venv\Scripts\python.exe
for %%S in (role_chain switch_back override session_context) do (
  echo === cold %%S ===
  %PY% tools\converse.py --cold tools\scripts.json --name %%S --save shapecs_%%S 2>&1 | findstr /C:"FAIL" /C:"fail"
)
echo DONE