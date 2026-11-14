"""严格测焦点：点击期间每 10ms 采样前台窗口，演示软件是否曾成为前台、层叠顺序是否变化。"""
import ctypes, os, subprocess, sys, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
import auto_click as ac
from demo_launch import launch
demo = launch(); time.sleep(3)
cover = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "cover_app.py")]); time.sleep(1.5)
ac.cfg["proc"] = "演示软件"; ac.cfg["region"] = None
h = ac.find_window("演示软件")
def title(w):
    b = ctypes.create_unicode_buffer(200); ac.u32.GetWindowTextW(w, b, 200); return b.value
time.sleep(1); fg0 = ac.u32.GetForegroundWindow()
hits = {"fg_demo": 0, "fg_changed": 0}; stop = False; seen = set()
def sample():
    while not stop:
        f = ac.u32.GetForegroundWindow()
        if ac.u32.GetAncestor(f, 2) == h: hits["fg_demo"] += 1
        if f != fg0:
            hits["fg_changed"] += 1; seen.add((f, title(f)))
        time.sleep(0.01)
threading.Thread(target=sample, daemon=True).start()
n = 0; t0 = time.time()
while time.time() - t0 < 10:
    sc, pos = ac.find(h)
    if sc >= ac.THRESH:
        ac.post_click(h, *pos); n += 1; time.sleep(1.3)
    time.sleep(0.3)
stop = True; time.sleep(0.1)
page = title(h)
demo.kill(); cover.kill()
subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
print(seen); print(page, "发出", n, hits)
sys.exit(0 if n >= 3 and hits["fg_demo"] == 0 and hits["fg_changed"] == 0 else 1)
