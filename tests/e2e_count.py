"""计数要和真正点成功的次数一致：工具计数 == 演示软件里按钮被点掉的次数"""
import ctypes, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
import auto_click as ac
from demo_launch import launch
STUCK = "--stuck" in sys.argv  # 按钮点了不消失：计数应为 0
demo = launch(query="stuck=1" if STUCK else ""); time.sleep(3)
h = ac.find_window("演示软件"); ac.cfg["region"] = None
ok = sent = 0; t0 = time.time()
while time.time() - t0 < 10:
    sc, pos = ac.find(h)
    if sc >= ac.THRESH:
        ac.post_click(h, *pos); sent += 1
        ok += ac.confirm_gone(h, pos)
    time.sleep(0.3)
b = ctypes.create_unicode_buffer(200); ac.u32.GetWindowTextW(h, b, 200)
page = int(b.value.split("点击 ")[1].split(" 次")[0])
demo.kill()
subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
print(f"发出点击 {sent}，工具计数 {ok}，软件里真正点掉 {page}")
sys.exit(0 if (ok == 0 and sent >= 2 if STUCK else ok == page and ok >= 3) else 1)
