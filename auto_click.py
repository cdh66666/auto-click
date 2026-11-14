import ctypes, json, os, sys, threading, time
from ctypes import wintypes as W
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import cv2, numpy as np
import tkinter as tk

THRESH = 0.80
base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
tpl = cv2.imdecode(np.fromfile(os.path.join(base, "target.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
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


def save():
    try:
        json.dump(cfg, open(CFG, "w"))
    except Exception:
        pass


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
    g = cv2.cvtColor(np.ascontiguousarray(img), cv2.COLOR_BGRA2GRAY)
    sc, pos = match_gray(g)
    return sc, (None if pos is None else (ox + pos[0], oy + pos[1]))


def match_gray(g):
    """在灰度图里找模板，返回 (相似度, 中心点)"""
    best = (0, None)
    for s in SCALES:
        t = cv2.resize(tpl, None, fx=s, fy=s)
        if t.shape[0] > g.shape[0] or t.shape[1] > g.shape[1]:
            continue
        res = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (mx, (loc[0] + t.shape[1] / 2, loc[1] + t.shape[0] / 2))
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
    above = u32.GetWindow(hwnd, 3)  # 点击前在它上面的那个窗口
    while above and not u32.IsWindowVisible(above):
        above = u32.GetWindow(above, 3)
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


def loop(status, counts):
    while True:
        if running:
            try:
                hwnd = find_window(cfg["proc"])
                if not hwnd:
                    status.set("没找到 " + cfg["proc"])
                else:
                    sc, pos = find(hwnd)
                    if sc >= THRESH:
                        post_click(hwnd, *pos)
                        cfg["total"] += 1
                        counts["session"] += 1
                        save()
                        status.set(f"已点击 ({sc:.0%})")
                        time.sleep(1.0)
                    else:
                        status.set(f"找按钮中… 最高 {sc:.0%}")
            except Exception as e:
                status.set("错误: " + str(e)[:30])
        time.sleep(0.3)


def main():
    root = tk.Tk()
    root.title("自动点击")
    try:
        root.iconbitmap(os.path.join(base, "icon.ico"))
    except Exception:
        pass
    root.geometry("260x270")
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
    if os.environ.get("AUTO_CLICK_AUTOSTART"):  # 演示/测试用：启动即开始
        root.after(500, toggle)
    tk.Label(root, textvariable=ctxt, font=("Microsoft YaHei", 11, "bold")).pack(pady=4)
    refresh()

    row = tk.Frame(root)
    row.pack(pady=6)
    tk.Label(row, text="软件").pack(side="left")
    pv = tk.StringVar(value=cfg["proc"])
    ent = tk.Entry(row, textvariable=pv, width=16)
    ent.pack(side="left", padx=4)

    def setproc(*_):
        cfg["proc"] = pv.get().strip() or "claude.exe"
        save()

    pv.trace_add("write", setproc)

    rtxt = tk.StringVar()

    def showr():
        rtxt.set("区域: 已框定" if cfg["region"] else "区域: 整个软件界面")

    def pick():
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
                    cfg["region"] = (l - o.x, t - o.y, w, h)  # 存成相对窗口的位置
                    save()
            top.destroy()
            root.deiconify()
            showr()

        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        top.bind("<Escape>", lambda e: (top.destroy(), root.deiconify()))
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
    threading.Thread(target=loop, args=(status, counts), daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        h = find_window(cfg["proc"])
        print("hwnd", h)
        img = capture(h)
        print(None if img is None else img.shape, None if img is None else int(img.mean()))
        if img is not None:
            cv2.imwrite(sys.argv[2], img)
        print(find(h))
    else:
        main()
