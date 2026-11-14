"""一键打包并更新开始菜单快捷方式：python build.py
- 先关掉正在运行的 自动点击.exe（否则文件被占用）
- 重新生成图标、打包 exe
- 刷新开始菜单里的「自动点击」快捷方式（带图标），保证它永远指向最新版"""
import os, shutil, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
exe = os.path.join(here, "自动点击.exe")

subprocess.run(["taskkill", "/F", "/IM", "自动点击.exe"], capture_output=True)
subprocess.run([sys.executable, os.path.join("tools", "make_icon.py")], check=True)
subprocess.run([sys.executable, "-m", "PyInstaller", "-F", "-w", "-y", "-n", "自动点击",
                "--icon", os.path.join("assets", "icon.ico"),
                "--exclude-module", "PIL", "--exclude-module", "matplotlib", "--exclude-module", "scipy", "--add-data", "target.png;.", "--add-data", os.path.join("assets", "icon.ico") + ";.",
                "--distpath", here, "auto_click.py"], check=True)
shutil.rmtree("build", ignore_errors=True)
if os.path.exists("自动点击.spec"):
    os.remove("自动点击.spec")

lnk = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "自动点击.lnk")
ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';"
      "$s.WorkingDirectory='%s';$s.IconLocation='%s,0';$s.Description='自动点击确认按钮';$s.Save()"
      % (lnk, exe, here, exe))
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
# 刷新图标缓存，让开始菜单立刻换上新图标
subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
print("已打包:", exe, "\n快捷方式:", lnk)
