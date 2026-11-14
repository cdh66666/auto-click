"""录演示：演示软件（Edge，Chromium 内核）被别的窗口盖住一部分，自动点击照样点到。
输出 docs/demo.gif、docs/demo.mp4、docs/ui.png、docs/detect.png
直接截各窗口的内容来合成，不录屏，不会拍到你桌面上别的东西。"""
import ctypes, os, subprocess, sys, tempfile, time
from ctypes import wintypes as W
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import json
cfgf = os.path.join(tempfile.gettempdir(), "demo_media_cfg.json")
json.dump({"proc": "演示软件", "region": None, "total": 0}, open(cfgf, "w"))
os.environ["AUTO_CLICK_CFG"] = cfgf
import auto_click as ac
from demo_launch import launch

DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
FONT_S = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)


def title_of(h):
    b = ctypes.create_unicode_buffer(200)
    ac.u32.GetWindowTextW(h, b, 200)
    return b.value


def origin(h):
    p = W.POINT(0, 0)
    ac.u32.ClientToScreen(h, ctypes.byref(p))
    return p.x, p.y


def find_title(t, tries=40):
    for _ in range(tries):
        h = ac.find_window(t)
        if h:
            return h
        time.sleep(0.25)
    raise RuntimeError(t)


demo = launch(100, 100, 720, 460)
time.sleep(3)
cover = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "cover_app.py"), "560x380+60+220"])
time.sleep(1.2)
tool = subprocess.Popen([sys.executable, os.path.join(ROOT, "auto_click.py")],
                        env={**os.environ, "AUTO_CLICK_AUTOSTART": "1", "AUTO_CLICK_POS": "1250,140"})
hd = find_title("演示软件")
hc = find_title("遮挡窗口")
ht = find_title("自动点击")
time.sleep(1)

PAD = 40
frames = []
t0 = time.time()
DUR, FPS = 16, 10
shots = {}
try:
    while time.time() - t0 < DUR:
        t1 = time.time()
        wins = [(hd, ac.capture(hd)), (hc, ac.capture(hc)), (ht, ac.capture(ht))]
        wins = [(h, im, origin(h)) for h, im in wins if im is not None]
        x0 = min(o[0] for _, _, o in wins); y0 = min(o[1] for _, _, o in wins)
        x1 = max(o[0] + im.shape[1] for _, im, o in wins); y1 = max(o[1] + im.shape[0] for _, im, o in wins)
        W_, H_ = x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD + 70
        canvas = Image.new("RGB", (W_, H_), (24, 26, 33))
        for h, im, (ox, oy) in wins:
            canvas.paste(Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGRA2RGB)), (ox - x0 + PAD, oy - y0 + PAD + 70))
        d = ImageDraw.Draw(canvas)
        d.text((PAD, 18), "演示软件被别的窗口盖在后台，自动点击照样点到", font=FONT, fill=(240, 240, 240))
        d.text((PAD + 700, 100 + 70 - 40), "", font=FONT_S)
        cap = f"{title_of(hd)}"
        d.text((PAD, H_ - 44), cap, font=FONT_S, fill=(255, 160, 100))
        canvas = canvas.resize((int(W_ * 0.5), int(H_ * 0.5)), Image.LANCZOS)
        frames.append(canvas)
        if len(frames) == 80:
            shots["main"] = (wins, canvas.copy())
        time.sleep(max(0, 1 / FPS - (time.time() - t1)))
    # 单张：工具窗口、检测标注
    ui = ac.capture(ht)
    Image.fromarray(cv2.cvtColor(ui, cv2.COLOR_BGRA2RGB)).save(os.path.join(DOCS, "ui.png"))
    ac.cfg["region"] = None
    for _ in range(40):
        sc, pos = ac.find(hd)
        if sc >= ac.THRESH: break
        time.sleep(0.1)
    dimg = ac.capture(hd)
    im = cv2.cvtColor(dimg, cv2.COLOR_BGRA2BGR)
    th, tw = ac.tpl.shape
    cv2.rectangle(im, (int(pos[0] - tw / 2) - 4, int(pos[1] - th / 2) - 4), (int(pos[0] + tw / 2) + 4, int(pos[1] + th / 2) + 4), (0, 200, 0), 3)
    pil = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(pil).text((int(pos[0] - tw / 2), int(pos[1] - th / 2) - 44), f"相似度 {sc:.0%}", font=FONT, fill=(60, 220, 90))
    pil.save(os.path.join(DOCS, "detect.png"))
finally:
    tool.kill(); cover.kill(); demo.kill()
    subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq 自动点击"], capture_output=True)

w, h = frames[0].size
vw = cv2.VideoWriter(os.path.join(DOCS, "demo.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
for f in frames:
    vw.write(cv2.cvtColor(np.array(f), cv2.COLOR_RGB2BGR))
vw.release()
g = [f.resize((int(w * 0.8), int(h * 0.8)), Image.LANCZOS).quantize(128) for f in frames[::2]]
g[0].save(os.path.join(DOCS, "demo.gif"), save_all=True, append_images=g[1:], duration=int(2000 / FPS), loop=0, optimize=True)
print("frames", len(frames), "last title", title_of(hd) if ac.u32.IsWindow(hd) else "")
