"""端到端：演示软件被遮挡在后台，自动点击仍能点到，且不把它拉到前台。
用法: python tests/e2e_background.py"""
import os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import auto_click as ac

sys.path.insert(0, os.path.join(ROOT, "tests"))
from demo_launch import launch
demo = launch()
time.sleep(3)
cover = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "cover_app.py")])
time.sleep(1.5)
ac.cfg["proc"] = "演示软件"
ac.cfg["region"] = None
fg_cover = ac.u32.GetForegroundWindow()
_b = __import__('ctypes').create_unicode_buffer(100); ac.u32.GetWindowTextW(fg_cover, _b, 100); fg_cover_title = _b.value
steals = 0
t0 = time.time()
while time.time() - t0 < 9:
    h = ac.find_window("演示软件")
    sc, pos = ac.find(h)
    if sc >= ac.THRESH:
        ac.post_click(h, *pos)
        time.sleep(0.6)
        if ac.u32.GetAncestor(ac.u32.GetForegroundWindow(), 2) == h:
            steals += 1
        time.sleep(1.0)
    time.sleep(0.3)
import ctypes
b = ctypes.create_unicode_buffer(200)
ac.u32.GetWindowTextW(ac.find_window("演示软件"), b, 200)
print(repr(b.value), steals)
n = int(b.value.split("点击")[1].split("次")[0])
fgnow = ac.u32.GetForegroundWindow()
bb = ctypes.create_unicode_buffer(100); ac.u32.GetWindowTextW(fgnow, bb, 100)
still_cover = fgnow == fg_cover
demo.kill(); cover.kill()
subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)

print(f"点击次数 {n}，被拉到前台 {steals} 次，前台仍是遮挡窗口: {still_cover}")
sys.exit(0 if n >= 3 and steals == 0 else 1)
