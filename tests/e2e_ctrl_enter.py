"""按钮点了不消失时，只给软件发 Ctrl+Enter：要能确认掉按钮，且前台窗口、真实 Ctrl 键都不受影响"""
import ctypes, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
import auto_click as ac
from demo_launch import launch
demo = launch(query="stuck=1"); time.sleep(3.5)
cover = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "cover_app.py")]); time.sleep(1.5)
h = ac.find_window("演示软件"); ac.cfg["region"] = None
fg0 = ac.u32.GetForegroundWindow()
ok = 0; ctrl_leak = 0; fg_changed = 0; t0 = time.time()
while time.time() - t0 < 12:
    sc, pos = ac.find(h)
    if sc >= ac.THRESH:
        ac.post_click(h, *pos)
        if not ac.confirm_gone(h, pos, 1.0):
            ac.send_ctrl_enter(h)
            ok += ac.confirm_gone(h, pos, 2.5)
        ctrl_leak += bool(ac.u32.GetAsyncKeyState(0x11) & 0x8000)
        fg_changed += ac.u32.GetForegroundWindow() != fg0
    time.sleep(0.3)
b = ctypes.create_unicode_buffer(200); ac.u32.GetWindowTextW(h, b, 200)
topped = bool(ac.u32.GetWindowLongW(h, -20) & 0x8)
demo.kill(); cover.kill()
subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
print(f"{b.value}；确认 {ok} 次，真实 Ctrl 被按住 {ctrl_leak} 次，前台变了 {fg_changed} 次，软件被置顶 {topped}")
K = int(b.value.split("键盘 ")[1].split("）")[0]) if "键盘" in b.value else 0
print("键盘确认", K, "工具计数", ok)
sys.exit(0 if ok >= 2 and ok == K and ctrl_leak == 0 and fg_changed == 0 and not topped else 1)
