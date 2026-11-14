"""不依赖 OpenCV 的小工具：PNG 读写、灰度、缩放、模板匹配（TM_CCOEFF_NORMED，FFT 实现）"""
import struct, zlib
import numpy as np


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def read_png_gray(path):
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, w = 8, b"", 0
    while pos < len(d):
        n, typ = struct.unpack(">I4s", d[pos:pos + 8])
        body = d[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or inter:
                return None
        elif typ == b"IDAT":
            idat += body
        pos += 12 + n
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * ch
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.int32)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = np.frombuffer(raw, np.uint8, stride, y * (stride + 1) + 1).astype(np.int32)
        if f == 0:
            cur = line
        elif f == 2:
            cur = (line + prev) & 255
        else:  # 1 / 3 / 4 要逐字节依赖左边像素
            cur = line.copy()
            for i in range(stride):
                a = cur[i - ch] if i >= ch else 0
                if f == 1:
                    cur[i] = (cur[i] + a) & 255
                elif f == 3:
                    cur[i] = (cur[i] + ((a + prev[i]) >> 1)) & 255
                else:
                    c = prev[i - ch] if i >= ch else 0
                    cur[i] = (cur[i] + _paeth(a, prev[i], c)) & 255
        out[y] = cur
        prev = cur
    px = out.reshape(h, w, ch).astype(np.float32)
    if ch >= 3:
        return (px[..., 0] * 0.299 + px[..., 1] * 0.587 + px[..., 2] * 0.114).astype(np.uint8)
    return px[..., 0].astype(np.uint8)


def write_png(path, img):
    """img: 灰度 (h,w) 或 RGB (h,w,3) uint8"""
    img = np.ascontiguousarray(img, np.uint8)
    h, w = img.shape[:2]
    ctype = 0 if img.ndim == 2 else 2
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def bgra_to_gray(img):
    f = img[..., :3].astype(np.float32)
    return f[..., 2] * 0.299 + f[..., 1] * 0.587 + f[..., 0] * 0.114


def resize(g, s):
    h, w = g.shape
    nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
    ys = np.clip((np.arange(nh) + 0.5) / s - 0.5, 0, h - 1)
    xs = np.clip((np.arange(nw) + 0.5) / s - 0.5, 0, w - 1)
    y0, x0 = ys.astype(int), xs.astype(int)
    y1, x1 = np.minimum(y0 + 1, h - 1), np.minimum(x0 + 1, w - 1)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    g = g.astype(np.float32)
    top = g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx
    bot = g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


class Matcher:
    """同一张图对多个模板匹配：图像的 FFT 和积分图只算一次"""

    def __init__(self, img):
        I = img.astype(np.float32)
        self.shape = I.shape
        self.F = np.fft.rfft2(I)
        self.S = np.pad(I.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        self.S2 = np.pad(I.astype(np.float64) ** 2, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def match(self, tpl):
        """返回 (最高相似度, 左上角 (x, y))，同 cv2.TM_CCOEFF_NORMED"""
        T = tpl.astype(np.float64)
        th, tw = T.shape
        n = th * tw
        Tz = T - T.mean()
        tnorm = np.sqrt((Tz ** 2).sum())
        if tnorm < 1e-6:
            return 0.0, (0, 0)
        corr = np.fft.irfft2(self.F * np.fft.rfft2(Tz[::-1, ::-1], self.shape), self.shape)[th - 1:, tw - 1:]
        S, S2 = self.S, self.S2

        def box(A):
            return A[th:, tw:] - A[:-th, tw:] - A[th:, :-tw] + A[:-th, :-tw]

        bs = box(S)
        var = box(S2) - bs * bs / n
        den = np.sqrt(np.maximum(var, 0)) * tnorm
        res = np.where(den > 1e-3 * tnorm * np.sqrt(n), corr / np.maximum(den, 1e-12), 0)
        k = int(np.argmax(res))
        y, x = divmod(k, res.shape[1])
        return float(res[y, x]), (x, y)


def match(img, tpl):
    return Matcher(img).match(tpl)
