"""遮挡窗口：盖住演示软件一部分，模拟“软件在后台”（完全盖住时 Chromium 会停止渲染，没法检测）"""
import sys
import ctypes
import tkinter as tk
ctypes.windll.shcore.SetProcessDpiAwareness(2)

root = tk.Tk()
root.title("遮挡窗口")
root.geometry(sys.argv[1] if len(sys.argv) > 1 else "700x420+100+60")
root.configure(bg="#2b5797")
tk.Label(root, text="别的软件\n盖住了演示软件的一部分", fg="white", bg="#2b5797",
         font=("Microsoft YaHei", 22)).pack(expand=True)
root.mainloop()
