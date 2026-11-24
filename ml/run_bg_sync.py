import os, subprocess, sys
from datetime import datetime

os.chdir(r"C:\Users\gopid\aquatwin-ai\ml")
log_path = os.path.join(os.getcwd(), "gee_sync.log")
py_exe = sys.executable.replace("pythonw.exe", "python.exe")

res = subprocess.run([py_exe, "gee_live_sync.py"], capture_output=True, text=True)
with open(log_path, "a", encoding="utf-8") as f:
    f.write(f"\n--- Sync Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (exit={res.returncode}) ---\n")
    if res.stdout:
        f.write(res.stdout)
    if res.stderr:
        f.write(res.stderr)
