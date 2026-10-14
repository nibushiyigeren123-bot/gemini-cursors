from pathlib import Path
import base64, hashlib, io, json, math, shutil, struct, zipfile
from PIL import Image, ImageDraw, ImageFont
ROLES = [('Arrow', '正常选择'), ('Help', '帮助选择'), ('AppStarting', '后台运行'), ('Wait', '忙碌'), ('Crosshair', '精确选择'), ('IBeam', '文本选择'), ('NWPen', '手写'), ('No', '不可用'), ('SizeNS', '垂直调整'), ('SizeWE', '水平调整'), ('SizeNWSE', '对角调整1'), ('SizeNESW', '对角调整2'), ('SizeAll', '移动'), ('UpArrow', '候选选择'), ('Hand', '链接选择'), ('Pin', '位置选择'), ('Person', '人员选择')]
INK = '#182844'
WHITE = '#f7fbff'
MINT = '#6aa4f1'
GOLD = '#e8c66a'

def cursor_bytes(image, hotspot):
    """32-bit bottom-up BGRA DIB plus DWORD-aligned 1-bit AND mask."""
    w, h = image.size
    assert 1 <= w <= 256 and 1 <= h <= 256
    rgba = image.tobytes()
    pixels = bytearray()
    stride = (w + 31) // 32 * 4
    mask = bytearray(stride * h)
    for out_y, y in enumerate(range(h - 1, -1, -1)):
        for x in range(w):
            r, g, b, a = rgba[(y * w + x) * 4:(y * w + x + 1) * 4]
            pixels.extend((b, g, r, a))
            if a == 0:
                mask[out_y * stride + x // 8] |= 1 << 7 - x % 8
    dib = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0) + pixels + mask
    return struct.pack('<HHH', 0, 2, 1) + struct.pack('<BBBBHHII', w % 256, h % 256, 0, 0, *hotspot, len(dib), 22) + dib

def chunk(kind, data):
    return kind + struct.pack('<I', len(data)) + data + (b'\x00' if len(data) % 2 else b'')

def ani_bytes(images, hotspot, jiffies=8):
    frames = b''.join((chunk(b'icon', cursor_bytes(im, hotspot)) for im in images))
    header = struct.pack('<9I', 36, len(images), len(images), 0, 0, 32, 1, jiffies, 1)
    body = b'ACON' + chunk(b'anih', header) + chunk(b'LIST', b'fram' + frames)
    return b'RIFF' + struct.pack('<I', len(body)) + body

def symbol(role, frame):
    """Draw symbol at 4x, in a 64-unit design space."""
    k = 4
    im = Image.new('RGBA', (256, 256))
    d = ImageDraw.Draw(im)

    def pts(p):
        return [(round(x * k), round(y * k)) for x, y in p]

    def line(p, fill=WHITE, width=2.5):
        d.line(pts(p), fill=INK, width=round((width + 2) * k), joint='curve')
        d.line(pts(p), fill=fill, width=round(width * k), joint='curve')

    def poly(p, fill=WHITE):
        d.polygon(pts(p), fill=fill)
        d.line(pts(p + [p[0]]), fill=INK, width=6, joint='curve')

    def ellipse(box, fill=WHITE):
        d.ellipse(tuple((round(a * k) for a in box)), fill=fill, outline=INK, width=6)

    def arrow(p):
        poly(p, MINT)
    hs = (4, 4)
    if role in ('Arrow', 'Help', 'AppStarting'):
        poly([(4, 4), (5, 31), (12, 24), (19, 37), (25, 33), (18, 21), (29, 20)])
        if role == 'Help':
            ellipse((27, 3, 45, 21), MINT)
            f = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 15 * k)
            d.text((32 * k, 2 * k), '?', font=f, fill=INK)
        if role == 'AppStarting':
            ellipse((28, 5, 46, 23), WHITE)
            for i in range(8):
                a = 2 * math.pi * (i + frame) / 8
                x = 37 + 6 * math.cos(a)
                y = 14 + 6 * math.sin(a)
                d.ellipse(((x - 1.8) * k, (y - 1.8) * k, (x + 1.8) * k, (y + 1.8) * k), fill=MINT if i < 4 else INK)
    elif role == 'Wait':
        hs = (19, 19)
        ellipse((5, 5, 33, 33), WHITE)
        a = 2 * math.pi * frame / 8
        line([(19, 19), (19 + 10 * math.sin(a), 19 - 10 * math.cos(a))], MINT, 3)
        line([(19, 19), (12, 16)], GOLD, 2)
    elif role == 'Crosshair':
        hs = (19, 19)
        line([(19, 3), (19, 35)])
        line([(3, 19), (35, 19)])
        ellipse((15, 15, 23, 23), MINT)
    elif role == 'IBeam':
        hs = (16, 20)
        line([(16, 4), (16, 36)], MINT)
        line([(8, 4), (24, 4)])
        line([(8, 36), (24, 36)])
    elif role == 'NWPen':
        hs = (5, 34)
        poly([(5, 34), (9, 23), (28, 4), (35, 11), (16, 30)], MINT)
        poly([(5, 34), (9, 23), (16, 30)], WHITE)
    elif role == 'No':
        hs = (19, 19)
        ellipse((4, 4, 34, 34), WHITE)
        line([(9, 9), (29, 29)], '#ed8991', 4)
    elif role.startswith('Size'):
        hs = (19, 19)
        dirs = {'SizeNS': [(0, -1), (0, 1)], 'SizeWE': [(-1, 0), (1, 0)], 'SizeNWSE': [(-0.707, -0.707), (0.707, 0.707)], 'SizeNESW': [(0.707, -0.707), (-0.707, 0.707)], 'SizeAll': [(0, -1), (0, 1), (-1, 0), (1, 0)]}[role]
        for dx, dy in dirs:
            tx = 19 + 16 * dx
            ty = 19 + 16 * dy
            nx = -dy
            ny = dx
            line([(19, 19), (tx, ty)], MINT, 3)
            arrow([(tx, ty), (tx - 7 * dx + 5 * nx, ty - 7 * dy + 5 * ny), (tx - 7 * dx - 5 * nx, ty - 7 * dy - 5 * ny)])
    elif role == 'UpArrow':
        hs = (19, 4)
        poly([(19, 4), (6, 18), (14, 18), (14, 35), (24, 35), (24, 18), (32, 18)], MINT)
    elif role == 'Hand':
        hs = (14, 4)
        poly([(10, 31), (5, 22), (6, 18), (10, 18), (12, 22), (12, 6), (14, 4), (17, 5), (18, 17), (21, 13), (24, 14), (26, 15), (30, 15), (32, 18), (34, 20), (34, 30), (29, 37), (16, 37)], WHITE)
        line([(21, 17), (21, 26)], MINT, 1.2)
        line([(27, 18), (27, 26)], MINT, 1.2)
    elif role == 'Pin':
        hs = (19, 35)
        ellipse((7, 4, 31, 28), MINT)
        poly([(9, 20), (19, 35), (29, 20)], MINT)
        ellipse((14, 10, 24, 20), WHITE)
    elif role == 'Person':
        hs = (19, 10)
        ellipse((12, 4, 26, 18), MINT)
        poly([(6, 34), (8, 26), (13, 22), (25, 22), (30, 26), (32, 34)], WHITE)
    return (im, hs)
