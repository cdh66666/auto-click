"""生成图标 assets/icon.ico + icon.png：渐变圆角方块 + 白色对勾 + 鼠标指针"""
from PIL import Image, ImageDraw
import os

S = 1024
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(out, exist_ok=True)

# 渐变底
bg = Image.new("RGB", (S, S))
px = bg.load()
c1, c2 = (255, 138, 76), (217, 70, 120)  # 橙 -> 玫红
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=230, fill=255)
icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
icon.paste(bg, (0, 0), mask)

d = ImageDraw.Draw(icon)
# 白色对勾
d.line([(230, 540), (410, 720), (770, 300)], fill="white", width=120, joint="curve")
for p in [(230, 540), (410, 720), (770, 300)]:
    d.ellipse((p[0] - 60, p[1] - 60, p[0] + 60, p[1] + 60), fill="white")
# 鼠标指针（深色描边 + 白填充）
cur = [(600, 560), (600, 960), (700, 870), (775, 1010), (850, 975), (775, 835), (905, 830)]
cur = [(x - 70, y - 120) for x, y in cur]
d.polygon(cur, fill="white")
d.line(cur + [cur[0]], fill=(40, 40, 46), width=34, joint="curve")
icon.resize((512, 512), Image.LANCZOS).save(os.path.join(out, "icon.png"))
icon.save(os.path.join(out, "icon.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("ok")
