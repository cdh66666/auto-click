"""生成演示用按钮图 tests/buttons/*.png（模拟游戏里的“确定”“领取奖励”）"""
import os
from PIL import Image, ImageDraw, ImageFont

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "buttons")
os.makedirs(out, exist_ok=True)
F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 30)
for name, text, bg, w in [("ok", "确 定", (46, 125, 220), 200), ("reward", "领取奖励", (240, 140, 30), 230)]:
    im = Image.new("RGB", (w, 68), (38, 38, 36))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((3, 3, w - 4, 64), 18, fill=bg, outline=(255, 255, 255), width=2)
    d.text((w / 2, 34), text, font=F, fill="white", anchor="mm")
    im.save(os.path.join(out, name + ".png"))
print("ok", os.listdir(out))
