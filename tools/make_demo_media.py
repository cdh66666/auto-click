"""录演示素材（直接截各窗口内容合成，不录屏，不会拍到桌面上别的东西）。
三个场景，各出 gif + mp4，另出几张图：
  demo    演示软件被别的窗口盖在后台，照样点到、不抢焦点
  multi   加了 3 个按钮，随机出现哪个点哪个
  region  框选了区域，只点框里的
"""
import ctypes, json, os, shutil, subprocess, sys, tempfile, time
from ctypes import wintypes as W
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
TMP = tempfile.mkdtemp(prefix="auto_click_media_")
os.environ["APPDATA"] = TMP  # 演示用的按钮、设置都放临时目录，不碰真实设置
CFG = os.path.join(TMP, "cfg.json")
os.environ["AUTO_CLICK_CFG"] = CFG
import auto_click as ac
import imgmatch as im
from demo_launch import launch

DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
FONT_S = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)
BTN = os.path.join(ROOT, "tests", "buttons")


def title_of(h):
    b = ctypes.create_unicode_buffer(200)
    ac.u32.GetWindowTextW(h, b, 200)
    return b.value


def origin(h):
    p = W.POINT(0, 0)
    ac.u32.ClientToScreen(h, ctypes.byref(p))
    return p.x, p.y


def client(h):
    r = W.RECT()
    ac.u32.GetClientRect(h, ctypes.byref(r))
    return r.right, r.bottom


def find_title(t, tries=40):
    for _ in range(tries):
        h = ac.find_window(t)
        if h:
            return h
        time.sleep(0.25)
    raise RuntimeError(t)


def kill_all(*ps):
    for p in ps:
        if p:
            p.kill()
    subprocess.run(["powershell", "-c", "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*demo_profile_*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)


def save_video(name, frames, fps):
    w, h = frames[0].size
    vw = cv2.VideoWriter(os.path.join(DOCS, name + ".mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(cv2.cvtColor(np.array(f), cv2.COLOR_RGB2BGR))
    vw.release()
    g = [f.resize((int(w * 0.8), int(h * 0.8)), Image.LANCZOS).quantize(128) for f in frames[::2]]
    g[0].save(os.path.join(DOCS, name + ".gif"), save_all=True, append_images=g[1:], duration=int(2000 / fps), loop=0, optimize=True)


def scene(name, caption, query="", size=(720, 460), cover=None, buttons=(), region_right=False, dur=14, fps=10):
    """跑一个场景并录下来，返回 (演示窗口最后的标题, 工具窗口截图, 演示窗口截图, 区域)"""
    shutil.rmtree(os.path.join(TMP, "自动点击_按钮"), ignore_errors=True)
    if buttons:
        os.makedirs(os.path.join(TMP, "自动点击_按钮"))
        for i, b in enumerate(buttons):
            shutil.copy(b, os.path.join(TMP, "自动点击_按钮", f"{i}.png"))
    demo = launch(100, 100, size[0], size[1], query)
    time.sleep(3)
    hd = find_title("演示软件")
    region = None
    if region_right:
        cw, ch = client(hd)
        region = [cw // 2 + 4, 110, cw // 2 - 8, ch - 120]
    json.dump({"proc": "演示软件", "region": region, "total": 0, "no_default": bool(buttons)}, open(CFG, "w"))
    cov = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "cover_app.py"), cover]) if cover else None
    time.sleep(1.2 if cover else 0.1)
    tx = 100 + size[0] + 40
    tool = subprocess.Popen([sys.executable, os.path.join(ROOT, "auto_click.py")],
                            env={**os.environ, "AUTO_CLICK_AUTOSTART": "1", "AUTO_CLICK_POS": f"{tx},100", "AUTO_CLICK_TITLE": "自动点击演示"})
    ht = find_title("自动点击演示")
    hc = find_title("遮挡窗口") if cover else None
    time.sleep(1)
    PAD, frames, titles = 40, [], []
    try:
        t0 = time.time()
        while time.time() - t0 < dur:
            t1 = time.time()
            wins = [(h, ac.capture(h)) for h in (hd, hc, ht) if h]
            wins = [(h, x, origin(h)) for h, x in wins if x is not None]
            x0 = min(o[0] for _, _, o in wins); y0 = min(o[1] for _, _, o in wins)
            x1 = max(o[0] + x.shape[1] for _, x, o in wins); y1 = max(o[1] + x.shape[0] for _, x, o in wins)
            W_, H_ = x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD + 70
            canvas = Image.new("RGB", (W_, H_), (24, 26, 33))
            for h, x, (ox, oy) in wins:
                canvas.paste(Image.fromarray(cv2.cvtColor(x, cv2.COLOR_BGRA2RGB)), (ox - x0 + PAD, oy - y0 + PAD + 70))
            d = ImageDraw.Draw(canvas)
            if region:
                ox, oy = origin(hd)
                l, t, w, h = region
                bx, by = ox - x0 + PAD + l, oy - y0 + PAD + 70 + t
                d.rectangle((bx, by, bx + w, by + h), outline=(255, 50, 50), width=5)
            d.text((PAD, 18), caption, font=FONT, fill=(240, 240, 240))
            d.text((PAD, H_ - 44), title_of(hd), font=FONT_S, fill=(255, 160, 100))
            titles.append(title_of(hd))
            frames.append(canvas.resize((int(W_ * 0.5), int(H_ * 0.5)), Image.LANCZOS))
            time.sleep(max(0, 1 / fps - (time.time() - t1)))
        ui = ac.capture(ht)
        # 等按钮出现再截演示窗口（做检测标注图）
        ac.cfg.update(json.load(open(CFG)))
        ac.tpls = ac.load_tpls()
        for _ in range(40):
            sc, pos = ac.find(hd)
            if sc >= ac.THRESH:
                break
            time.sleep(0.1)
        shot = ac.capture(hd)
        last = title_of(hd)
    finally:
        kill_all(tool, cov, demo)
    save_video(name, frames, fps)
    print(name, len(frames), "帧,", last)
    # 静图挑“马上要被点”的那一帧（按钮正显示着）
    pick = [i for i in range(len(titles) - 3) if titles[i] == titles[i + 2] != titles[i + 3] and i > len(titles) // 3]
    return last, ui, shot, frames[pick[0] if pick else len(frames) * 2 // 3]


res = {}
# 1. 后台被遮挡
res["demo"] = scene("demo", "演示软件被别的窗口盖在后台，照样点到、不抢焦点", cover="560x380+60+220")
# 2. 多个按钮
res["multi"] = scene("multi", "加了 3 个按钮，出现哪个点哪个",
                     query="btns=../target.png,buttons/ok.png,buttons/reward.png",
                     buttons=[os.path.join(ROOT, "target.png"), os.path.join(BTN, "ok.png"), os.path.join(BTN, "reward.png")])
# 3. 框选区域
res["region"] = scene("region", "框选了右半边（红框），左边的按钮不点", query="mode=region", size=(980, 520),
                      region_right=True)

# 单张图
Image.fromarray(cv2.cvtColor(res["multi"][1], cv2.COLOR_BGRA2RGB)).save(os.path.join(DOCS, "ui.png"))
Image.fromarray(cv2.cvtColor(res["region"][1], cv2.COLOR_BGRA2RGB)).save(os.path.join(DOCS, "ui_region.png"))
res["region"][3].save(os.path.join(DOCS, "region.png"))
res["multi"][3].save(os.path.join(DOCS, "multi.png"))
res["demo"][3].save(os.path.join(DOCS, "background.png"))
# 检测标注图（默认按钮）
ac.cfg.update({"region": None, "no_default": False})
ac.tpls = ac.load_tpls()
shot = res["demo"][2]
g = im.bgra_to_gray(shot)
sc, pos = ac.match_gray(g)
pil = Image.fromarray(cv2.cvtColor(shot, cv2.COLOR_BGRA2RGB))
th, tw = ac.tpl.shape
d = ImageDraw.Draw(pil)
d.rectangle((pos[0] - tw / 2 - 4, pos[1] - th / 2 - 4, pos[0] + tw / 2 + 4, pos[1] + th / 2 + 4), outline=(0, 200, 0), width=3)
d.text((pos[0] - tw / 2, pos[1] - th / 2 - 44), f"相似度 {sc:.0%}", font=FONT, fill=(60, 220, 90))
pil.save(os.path.join(DOCS, "detect.png"))
json.dump({k: v[0] for k, v in res.items()}, open(os.path.join(DOCS, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
shutil.rmtree(TMP, ignore_errors=True)
