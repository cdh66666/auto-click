"""启动演示软件（用 Edge 应用窗口，和 Claude 桌面版同为 Chromium 内核）"""
import functools, http.server, os, subprocess, tempfile, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch(x=120, y=80, w=720, h=460):
    edge = next(p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"] if os.path.exists(p))
    prof = tempfile.mkdtemp(prefix="demo_profile_")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/tests/demo.html"
    return subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={prof}", "--no-first-run", "--disable-features=CalculateNativeWinOcclusion", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                             f"--window-size={w},{h}", f"--window-position={x},{y}"])
