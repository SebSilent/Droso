@echo off
REM One-off: full speech suite, warm then cold, after the shape arbiter.
cd /d C:\Projects\HybridLLM
set PY=.venv\Scripts\python.exe
set WARM=reference accumulation discrimination role_chain switch_back override session_context
for %%S in (%WARM%) do (
  echo === warm %%S ===
  %PY% tools\converse.py --scripts tools\scripts.json --name %%S --save shape_%%S 2>&1 | findstr /C:"answered" /C:"self_consistent" /C:"contradiction" /C:"refused_unknowable" /C:"session_fact_won" /C:"cold_pass" /C:"warm" /C:"FAIL" /C:"fail"
)
for %%S in (%WARM%) do (
  echo === cold %%S ===
  %PY% tools\converse.py --cold tools\scripts_fresh.json --name %%S_fresh --save shapec_%%S 2>&1 | findstr /C:"answered" /C:"self_consistent" /C:"contradiction" /C:"refused_unknowable" /C:"session_fact_won" /C:"cold_pass" /C:"warm" /C:"FAIL" /C:"fail"
)
echo DONE