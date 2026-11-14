import ctypes, json, os, sys, threading, time
from ctypes import wintypes as W
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import numpy as np
import imgmatch as im
import tkinter as tk
from tkinter import ttk

THRESH = 0.80
base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TPL = os.path.join(base, "target.png")
TPL_DIR = os.path.join(os.environ.get("APPDATA", "."), "自动点击_按钮")  # 自己加的按钮，一个按钮一张图


def load_tpls():
    """默认按钮 + 自己加的按钮"""
    files = [] if cfg.get("no_default") else [DEFAULT_TPL]
    if os.path.isdir(TPL_DIR):
        files += sorted(os.path.join(TPL_DIR, f) for f in os.listdir(TPL_DIR) if f.endswith(".png"))
    out, paths = [], []
    for f in files:
        try:
            t = im.read_png_gray(f)
            if t is not None:
                out.append(t)
                paths.append(f)
        except Exception:
            pass
    tpl_paths[:] = paths
    return out


tpl_paths = []
tpls = []
SCALES = [1.0, 0.9, 1.1, 0.8, 1.25, 0.7, 1.5]

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
k32 = ctypes.windll.kernel32
for fn, res, args in [
    (u32.GetDC, W.HDC, [W.HWND]), (u32.ReleaseDC, ctypes.c_int, [W.HWND, W.HDC]),
    (g32.CreateCompatibleDC, W.HDC, [W.HDC]), (g32.CreateCompatibleBitmap, W.HBITMAP, [W.HDC, ctypes.c_int, ctypes.c_int]),
    (g32.SelectObject, W.HGDIOBJ, [W.HDC, W.HGDIOBJ]), (g32.DeleteObject, W.BOOL, [W.HGDIOBJ]), (g32.DeleteDC, W.BOOL, [W.HDC]),
    (u32.PrintWindow, W.BOOL, [W.HWND, W.HDC, W.UINT]),
    (g32.GetDIBits, ctypes.c_int, [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]),
    (u32.GetClientRect, W.BOOL, [W.HWND, ctypes.POINTER(W.RECT)]),
    (u32.ClientToScreen, W.BOOL, [W.HWND, ctypes.POINTER(W.POINT)]),
    (u32.ScreenToClient, W.BOOL, [W.HWND, ctypes.POINTER(W.POINT)]),
    (u32.PostMessageW, W.BOOL, [W.HWND, W.UINT, W.WPARAM, W.LPARAM]),
    (u32.IsIconic, W.BOOL, [W.HWND]), (u32.ShowWindow, W.BOOL, [W.HWND, ctypes.c_int]),
    (u32.SetForegroundWindow, W.BOOL, [W.HWND]),
    (u32.ChildWindowFromPointEx, W.HWND, [W.HWND, W.POINT, W.UINT]),
    (u32.GetWindowThreadProcessId, W.DWORD, [W.HWND, ctypes.POINTER(W.DWORD)]),
    (u32.IsWindowVisible, W.BOOL, [W.HWND]),
    (u32.GetClassNameW, ctypes.c_int, [W.HWND, W.LPWSTR, ctypes.c_int]),
    (u32.EnumChildWindows, W.BOOL, [W.HWND, ctypes.c_void_p, W.LPARAM]),
    (u32.GetForegroundWindow, W.HWND, []), (u32.GetAncestor, W.HWND, [W.HWND, W.UINT]),
    (u32.GetWindow, W.HWND, [W.HWND, W.UINT]),
    (u32.SetWindowPos, W.BOOL, [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]),
    (u32.AttachThreadInput, W.BOOL, [W.DWORD, W.DWORD, W.BOOL]), (k32.GetCurrentThreadId, W.DWORD, []),
    (k32.OpenProcess, W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]), (k32.CloseHandle, W.BOOL, [W.HANDLE]),
    (k32.QueryFullProcessImageNameW, W.BOOL, [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]),
]:
    fn.restype, fn.argtypes = res, args

CFG = os.environ.get("AUTO_CLICK_CFG") or os.path.join(os.environ.get("APPDATA", "."), "自动点击.json")
cfg = {"proc": "claude.exe", "region": None, "total": 0}  # region: 相对窗口客户区 (l, t, w, h)
try:
    cfg.update(json.load(open(CFG)))
except Exception:
    pass
running = False
tpls = load_tpls()
tpl = tpls[0] if tpls else np.zeros((10, 10), np.uint8)


def save():
    try:
        json.dump(cfg, open(CFG, "w"))
    except Exception:
        pass


def list_apps():
    """有可见窗口的软件进程名（给下拉选项用）"""
    names = set()

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        if u32.IsWindowVisible(h) and u32.GetWindowTextLengthW(h) > 0:
            pid = W.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            ph = k32.OpenProcess(0x1000, False, pid.value)
            if ph:
                buf = ctypes.create_unicode_buffer(520)
                n = W.DWORD(520)
                k32.QueryFullProcessImageNameW(ph, 0, buf, ctypes.byref(n))
                k32.CloseHandle(ph)
                if buf.value:
                    names.add(os.path.basename(buf.value).lower())
        return True

    u32.EnumWindows(cb, 0)
    names.discard("自动点击.exe")
    return sorted(names)


def find_window(proc):
    proc = proc.lower().strip()
    found = []

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        n = u32.GetWindowTextLengthW(h)
        if n == 0:
            return True
        tb = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, tb, n + 1)
        title = tb.value.lower()
        by_title = not proc.endswith(".exe") and proc in title  # 不写 .exe 就按窗口标题找
        pid = W.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        ph = k32.OpenProcess(0x1000, False, pid.value)
        if ph:
            buf = ctypes.create_unicode_buffer(520)
            n = W.DWORD(520)
            k32.QueryFullProcessImageNameW(ph, 0, buf, ctypes.byref(n))
            k32.CloseHandle(ph)
            if by_title or os.path.basename(buf.value).lower() == proc:
                r = W.RECT()
                u32.GetClientRect(h, ctypes.byref(r))
                found.append((r.right * r.bottom, h))
        return True

    u32.EnumWindows(cb, 0)
    return max(found)[1] if found else None


class BIH(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                ("biClrImportant", W.DWORD)]


def capture(hwnd):
    r = W.RECT()
    u32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right, r.bottom
    if w < 50 or h < 50:
        return None
    sdc = u32.GetDC(None)
    mdc = g32.CreateCompatibleDC(sdc)
    bmp = g32.CreateCompatibleBitmap(sdc, w, h)
    old = g32.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, 3)  # CLIENTONLY | RENDERFULLCONTENT：被遮挡也能截
    bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g32.SelectObject(mdc, old)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(None, sdc)
    return np.frombuffer(buf, np.uint8).reshape(h, w, 4)


def find(hwnd):
    img = capture(hwnd)
    if img is None:
        return 0, None
    ox = oy = 0
    if cfg["region"]:
        l, t, rw, rh = cfg["region"]
        l, t = max(0, l), max(0, t)
        img = img[t:t + rh, l:l + rw]
        ox, oy = l, t
    g = im.bgra_to_gray(img)
    sc, pos = match_gray(g)
    return sc, (None if pos is None else (ox + pos[0], oy + pos[1]))


def match_gray(g):
    """在灰度图里找所有按钮，返回最像的 (相似度, 中心点)。先缩到一半再匹配，快很多"""
    best = (0, None)
    if not tpls:
        return best
    k = 0.5 if min(min(t.shape) for t in tpls) >= 24 else 1.0
    gs = im.resize(g, k) if k != 1.0 else g.astype(np.float32)
    m = im.Matcher(gs)
    for T in tpls:
        for s in SCALES:
            t = im.resize(T, s * k)
            if t.shape[0] > gs.shape[0] or t.shape[1] > gs.shape[1] or min(t.shape) < 4:
                continue
            mx, loc = m.match(t)
            if mx > best[0]:
                best = (mx, ((loc[0] + t.shape[1] / 2) / k, (loc[1] + t.shape[0] / 2) / k))
        if best[0] >= 0.95:
            break
    return best


def chromium_widget(hwnd):
    """Chromium 系软件（Claude、Edge…）真正收鼠标的子窗口"""
    found = []

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(100)
        u32.GetClassNameW(h, b, 100)
        if b.value == "Chrome_RenderWidgetHostHWND":
            found.append(h)
        return True

    u32.EnumChildWindows(hwnd, cb, 0)
    return found[0] if found else None


def deepest_child(hwnd, p):
    target = hwnd
    for _ in range(8):
        q = W.POINT(p.x, p.y)
        u32.ScreenToClient(target, ctypes.byref(q))
        c = u32.ChildWindowFromPointEx(target, q, 0)
        if not c or c == target:
            break
        target = c
    return target


def post_click(hwnd, cx, cy):
    """向窗口发送鼠标消息：不动真实鼠标，窗口在后台也有效"""
    prev_fg = u32.GetForegroundWindow()
    was_top = bool(u32.GetWindowLongW(hwnd, -20) & 0x8)
    above = u32.GetWindow(hwnd, 3)  # 点击前在它上面的那个窗口
    while above and (not u32.IsWindowVisible(above) or u32.GetWindowLongW(above, -20) & 0x8):
        above = u32.GetWindow(above, 3)  # 跳过隐藏和置顶窗口（插到置顶窗口后面会把软件也变成置顶）
    p = W.POINT(int(cx), int(cy))
    u32.ClientToScreen(hwnd, ctypes.byref(p))
    target = chromium_widget(hwnd) or deepest_child(hwnd, p)
    q = W.POINT(p.x, p.y)
    u32.ScreenToClient(target, ctypes.byref(q))
    lp = (q.y & 0xFFFF) << 16 | (q.x & 0xFFFF)
    u32.PostMessageW(target, 0x0200, 0, lp)          # MOUSEMOVE
    u32.PostMessageW(target, 0x0201, 1, lp)          # LBUTTONDOWN
    time.sleep(0.05)
    u32.PostMessageW(target, 0x0202, 0, lp)          # LBUTTONUP
    if u32.GetAncestor(prev_fg, 2) != hwnd:
        restore_back(hwnd, prev_fg, above)
    if not was_top and u32.GetWindowLongW(hwnd, -20) & 0x8:
        u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x13)  # 绝不把软件变成置顶：HWND_NOTOPMOST


def _klp(vk, up=False):
    return 1 | (u32.MapVirtualKeyW(vk, 0) << 16) | (0xC0000000 if up else 0)


def send_ctrl_enter(hwnd):
    """只给这个软件发 Ctrl+Enter：不动真实键盘，不影响别的软件，也不把它拉到前台"""
    prev_fg = u32.GetForegroundWindow()
    u32.PostMessageW(hwnd, 0x0006, 1, 0)   # WM_ACTIVATE：让它以为自己是活动窗口，才会收键盘
    u32.PostMessageW(hwnd, 0x0007, 0, 0)   # WM_SETFOCUS
    time.sleep(0.15)
    me = k32.GetCurrentThreadId()
    tid = u32.GetWindowThreadProcessId(hwnd, None)
    u32.AttachThreadInput(me, tid, True)   # 只和这个软件共享按键状态
    kb = (ctypes.c_ubyte * 256)()
    u32.GetKeyboardState(kb)
    old = bytes(kb)
    kb[0x11] = kb[0xA2] = 0x80             # 这个软件里 Ctrl 视为按下
    u32.SetKeyboardState(kb)
    for msg, vk, up in [(0x100, 0x11, 0), (0x100, 0x0D, 0), (0x102, 0x0A, 0), (0x101, 0x0D, 1), (0x101, 0x11, 1)]:
        u32.PostMessageW(hwnd, msg, vk, _klp(0x0D if vk == 0x0A else vk, up))
    time.sleep(0.12)                       # 等它处理完再还原按键状态
    u32.SetKeyboardState((ctypes.c_ubyte * 256).from_buffer_copy(old))
    u32.AttachThreadInput(me, tid, False)
    u32.PostMessageW(hwnd, 0x0008, 0, 0)   # WM_KILLFOCUS
    u32.PostMessageW(hwnd, 0x0006, 0, 0)   # WM_ACTIVATE(WA_INACTIVE)
    if u32.GetAncestor(prev_fg, 2) != hwnd:
        restore_back(hwnd, prev_fg, None)


def untop(hwnd):
    """去掉软件的置顶（旧版本可能误设了置顶）"""
    if hwnd and u32.GetWindowLongW(hwnd, -20) & 0x8:
        u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x13)


def restore_back(hwnd, prev_fg, above):
    """软件被点击后可能自己跳到前台：把前台和层叠顺序还原"""
    for _ in range(6):
        time.sleep(0.08)
        if u32.GetAncestor(u32.GetForegroundWindow(), 2) == hwnd:
            if prev_fg:
                cur = k32.GetCurrentThreadId()
                ft = u32.GetWindowThreadProcessId(u32.GetForegroundWindow(), None)
                u32.AttachThreadInput(cur, ft, True)
                u32.SetForegroundWindow(prev_fg)
                u32.AttachThreadInput(cur, ft, False)
            if above:
                u32.SetWindowPos(hwnd, above, 0, 0, 0, 0, 0x13)  # NOMOVE|NOSIZE|NOACTIVATE


def confirm_gone(hwnd, pos, wait=2.0):
    """点完后按钮消失（或那个位置不再是按钮）才算点成功"""
    r = max(tpl.shape) / 2 if tpls else 30
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(0.03)
        sc, p2 = find(hwnd)
        if sc < THRESH or p2 is None or abs(p2[0] - pos[0]) > r or abs(p2[1] - pos[1]) > r:
            return True
    return False


def loop(status, counts):
    while True:
        if running:
            try:
                hwnd = find_window(cfg["proc"])
                if not hwnd:
                    status.set("没找到 " + cfg["proc"])
                else:
                    if hwnd != counts.get("untopped"):
                        untop(hwnd)
                        counts["untopped"] = hwnd
                    sc, pos = find(hwnd)
                    if sc >= THRESH:
                        post_click(hwnd, *pos)
                        if confirm_gone(hwnd, pos):
                            cfg["total"] += 1
                            counts["session"] += 1
                            save()
                            status.set(f"已点击 ({sc:.0%})")
                            time.sleep(0.5)
                        elif cfg.get("ctrl_enter", True):
                            send_ctrl_enter(hwnd)
                            if confirm_gone(hwnd, pos, 2.5):
                                cfg["total"] += 1
                                counts["session"] += 1
                                save()
                                status.set("已按 Ctrl+Enter")
                                time.sleep(0.5)
                            else:
                                status.set("没消失，再试")
                        else:
                            status.set("点了没消失，再点")
                    else:
                        status.set(f"找按钮中… 最高 {sc:.0%}")
            except Exception as e:
                status.set("错误: " + str(e)[:30])
        time.sleep(0.3)


def main():
    root = tk.Tk()
    root.title(os.environ.get("AUTO_CLICK_TITLE", "自动点击"))  # 演示/测试用别的标题，免得和正在用的混
    try:
        root.iconbitmap(os.path.join(base, "icon.ico"))
    except Exception:
        pass
    root.minsize(400, 0)  # 高度随按钮数量自动变
    root.attributes("-topmost", True)
    if os.environ.get("AUTO_CLICK_POS"):  # 演示/测试用：指定窗口位置
        root.geometry("+" + os.environ["AUTO_CLICK_POS"].replace(",", "+"))
    status = tk.StringVar(value="已停止")
    tk.Label(root, textvariable=status, font=("Microsoft YaHei", 11)).pack(pady=8)
    counts = {"session": 0}
    ctxt = tk.StringVar()

    def refresh():
        ctxt.set(f"本次 {counts['session']}    累计 {cfg['total']}")
        root.after(300, refresh)

    btn = tk.Button(root, text="开始", font=("Microsoft YaHei", 14), width=10)

    def toggle():
        global running
        running = not running
        if running:
            counts["session"] = 0  # 每次点开始，本次从 0 数
        btn.config(text="停止" if running else "开始")
        if not running:
            status.set("已停止")

    btn.config(command=toggle)
    btn.pack()
    ce = tk.BooleanVar(value=cfg.get("ctrl_enter", True))

    def set_ce():
        cfg["ctrl_enter"] = ce.get()
        save()

    tk.Checkbutton(root, text="点了没消失就按 Ctrl+Enter（只发给这个软件）", variable=ce, command=set_ce).pack()
    if os.environ.get("AUTO_CLICK_AUTOSTART"):  # 演示/测试用：启动即开始
        root.after(500, toggle)
    tk.Label(root, textvariable=ctxt, font=("Microsoft YaHei", 11, "bold")).pack(pady=4)
    refresh()

    row = tk.Frame(root)
    row.pack(pady=6)
    tk.Label(row, text="软件").pack(side="left")
    pv = tk.StringVar(value=cfg["proc"])
    ent = ttk.Combobox(row, textvariable=pv, width=22, values=list_apps(),
                       postcommand=lambda: ent.config(values=list_apps()))
    ent.pack(side="left", padx=4)

    def setproc(*_):
        cfg["proc"] = pv.get().strip() or "claude.exe"
        save()

    pv.trace_add("write", setproc)

    rtxt = tk.StringVar()

    def showr():
        r = cfg["region"]
        rtxt.set(f"区域: {r[2]}×{r[3]}" if r else "区域: 整个软件界面")

    def flash_region(sec=2.5):
        """在软件上画红框，显示框选的区域（鼠标可穿透，几秒后消失）"""
        hwnd = find_window(cfg["proc"])
        if not hwnd:
            status.set("没找到 " + cfg["proc"])
            return
        o = W.POINT(0, 0)
        u32.ClientToScreen(hwnd, ctypes.byref(o))
        if cfg["region"]:
            l, t, w, h = cfg["region"]
        else:
            r = W.RECT()
            u32.GetClientRect(hwnd, ctypes.byref(r))
            l, t, w, h = 0, 0, r.right, r.bottom
        b = 4
        ov = tk.Toplevel(root)
        ov.overrideredirect(True)
        ov.attributes("-topmost", True, "-transparentcolor", "magenta")
        ov.geometry(f"{w + 2 * b}x{h + 2 * b}+{o.x + l - b}+{o.y + t - b}")
        c = tk.Canvas(ov, bg="magenta", highlightthickness=0)
        c.pack(fill="both", expand=True)
        c.create_rectangle(b // 2, b // 2, w + b * 3 // 2, h + b * 3 // 2, outline="red", width=b)
        ov.update()
        hw = u32.GetParent(ov.winfo_id()) or ov.winfo_id()
        ex = u32.GetWindowLongW(hw, -20)
        u32.SetWindowLongW(hw, -20, ex | 0x80000 | 0x20)  # LAYERED | TRANSPARENT：点击穿透
        ov.after(int(sec * 1000), ov.destroy)

    def pick(mode="region"):
        hwnd = find_window(cfg["proc"])
        if not hwnd:
            status.set("没找到 " + cfg["proc"])
            return
        root.withdraw()
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)
        u32.SetForegroundWindow(hwnd)  # 框选时把软件拉到前面
        root.update()
        time.sleep(0.6)
        vx, vy, vw, vh = [u32.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
        top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(bg="black", cursor="crosshair")
        top.geometry(f"{vw}x{vh}+{vx}+{vy}")
        cv = tk.Canvas(top, bg="black", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        st = {}

        def down(e):
            st["x"], st["y"] = e.x_root, e.y_root
            st["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

        def move(e):
            if "r" in st:
                cv.coords(st["r"], st["x"] - vx, st["y"] - vy, e.x, e.y)

        def up(e):
            if "r" in st:
                l, t = min(st["x"], e.x_root), min(st["y"], e.y_root)
                w, h = abs(e.x_root - st["x"]), abs(e.y_root - st["y"])
                if w > 20 and h > 10:
                    o = W.POINT(0, 0)
                    u32.ClientToScreen(hwnd, ctypes.byref(o))
                    if mode == "region":
                        cfg["region"] = (l - o.x, t - o.y, w, h)  # 存成相对窗口的位置
                        save()
                        root.after(300, flash_region)
                    else:
                        top.withdraw()
                        top.update()
                        time.sleep(0.4)
                        img = capture(hwnd)  # 框选前先隐藏遮罩，再截软件画面
                        if img is not None:
                            x0, y0 = max(0, l - o.x), max(0, t - o.y)
                            crop = img[y0:y0 + h, x0:x0 + w]
                            if crop.shape[0] > 10 and crop.shape[1] > 10:
                                os.makedirs(TPL_DIR, exist_ok=True)
                                im.write_png(os.path.join(TPL_DIR, time.strftime("%Y%m%d_%H%M%S.png")), crop[:, :, 2::-1])
                                global tpls
                                tpls = load_tpls()
                                status.set("已加按钮")
                                show_btns()
            top.destroy()
            root.deiconify()
            root.attributes("-topmost", True)
            showr()

        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        top.bind("<Escape>", lambda e: (top.destroy(), root.deiconify(), root.attributes("-topmost", True)))
        top.focus_force()

    def clear():
        cfg["region"] = None
        save()
        showr()

    showr()
    tk.Label(root, textvariable=rtxt).pack(pady=2)
    f = tk.Frame(root)
    f.pack()
    tk.Button(f, text="框选区域", command=pick).pack(side="left", padx=4)
    tk.Button(f, text="整个界面", command=clear).pack(side="left", padx=4)
    tk.Button(f, text="看区域", command=flash_region).pack(side="left", padx=4)
    f2 = tk.Frame(root)
    f2.pack(pady=4)
    tk.Button(f2, text="加按钮", command=lambda: pick("button")).pack(side="left", padx=4)

    def reset_btn():
        global tpls
        import shutil
        shutil.rmtree(TPL_DIR, ignore_errors=True)
        cfg["no_default"] = False
        save()
        tpls = load_tpls()
        status.set("已恢复默认")
        show_btns()

    tk.Button(f2, text="恢复默认", command=reset_btn).pack(side="left", padx=4)
    bl = tk.LabelFrame(root, text="要点的按钮（× 删除）")
    bl.pack(fill="x", padx=8, pady=6)
    thumbs = []

    def remove(path):
        global tpls
        if path == DEFAULT_TPL:
            cfg["no_default"] = True
            save()
        else:
            try:
                os.remove(path)
            except OSError:
                pass
        tpls = load_tpls()
        show_btns()

    def show_btns():
        for w in bl.winfo_children():
            w.destroy()
        thumbs.clear()
        if not tpl_paths:
            tk.Label(bl, text="没有按钮，点「加按钮」", fg="gray").pack(pady=6)
        for i, path in enumerate(tpl_paths):
            cell = tk.Frame(bl)
            cell.grid(row=i // 2, column=i % 2, padx=6, pady=4, sticky="w")
            try:
                ph = tk.PhotoImage(file=path)
                k = max(1, -(-ph.height() // 40), -(-ph.width() // 150))  # 缩到约 150x40 以内
                ph = ph.subsample(k)
                thumbs.append(ph)
                tk.Label(cell, image=ph, relief="solid", bd=1).pack(side="left")
            except Exception:
                tk.Label(cell, text=os.path.basename(path)).pack(side="left")
            tk.Button(cell, text="×", width=2, command=lambda p=path: remove(p)).pack(side="left", padx=2)

    show_btns()
    def keep_top():
        """没最小化就一直在最上层（不抢键盘焦点）"""
        try:
            if root.state() == "normal":
                hw = int(root.wm_frame(), 16)
                u32.SetWindowPos(hw, -1, 0, 0, 0, 0, 0x13)  # HWND_TOPMOST, NOMOVE|NOSIZE|NOACTIVATE
        except Exception:
            pass
        root.after(200, keep_top)

    keep_top()
    threading.Thread(target=loop, args=(status, counts), daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        h = find_window(cfg["proc"])
        print("hwnd", h)
        img = capture(h)
        print(None if img is None else img.shape, None if img is None else int(img.mean()))
        if img is not None:
            im.write_png(sys.argv[2], img[:, :, 2::-1])
        print(find(h))
    else:
        main()
