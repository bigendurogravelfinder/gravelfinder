"""App-Symbole Gravelfinder Big Enduro: Enduro-Motorrad + geplante Route, Petrol-Blau-Verlauf (wie die App)."""
import math
import sys
from PIL import Image, ImageDraw

OUT = sys.argv[1]
S = 1024
WHITE = (255, 255, 255, 255)
STOPS = [(0.0, (13, 148, 136)), (0.55, (14, 116, 144)), (1.0, (29, 78, 216))]   # #0d9488 → #0e7490 → #1d4ed8


def grad_color(t):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3)) + (255,)
    return STOPS[-1][1] + (255,)


def background():
    g = Image.new('RGBA', (S, S))
    px = g.load()
    for y in range(S):
        for x in range(S):
            px[x, y] = grad_color((x + y) / (2 * S - 2))
    return g


def bezier(p0, p1, p2, p3, n=300):
    for k in range(n + 1):
        t = k / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        yield (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def draw_content(img, scale, off):
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (off + x * S * scale, off + y * S * scale)

    def W(v):
        return v * S * scale

    def line(pts, w):
        pts = [P(*p) for p in pts]
        d.line(pts, fill=WHITE, width=int(W(w)), joint='curve')
        r = W(w) / 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)

    # ---- geplante Route: gestrichelte Kurve vom Startpunkt zur Zielnadel ----
    # gleichmäßige runde Punkte entlang der Kurve (ruhiger als Striche)
    curve = list(bezier((0.13, 0.42), (0.30, 0.08), (0.55, 0.40), (0.78, 0.24), n=2000))
    step, acc = 0.052, 0.03
    for a, b in zip(curve, curve[1:]):
        acc += math.dist(a, b)
        if acc >= step:
            acc = 0.0
            x, y = P(*b); r = W(0.017)
            d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
    # Startpunkt
    sx, sy = P(0.13, 0.42); r = W(0.045)
    d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=WHITE)
    r2 = W(0.02); d.ellipse([sx - r2, sy - r2, sx + r2, sy + r2], fill=grad_color(0.3))
    # Zielnadel
    cx, cy = P(0.80, 0.15); R = W(0.075)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=WHITE)
    d.polygon([P(0.80 - 0.066, 0.15 + 0.035), P(0.80 + 0.066, 0.15 + 0.035), P(0.80, 0.33)], fill=WHITE)
    r3 = W(0.03); d.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill=grad_color(0.45))

    # ---- Enduro (nach rechts fahrend) ----
    def wheel(cx_, cy_, r_):
        x, y = P(cx_, cy_); R_ = W(r_); w = W(0.034)
        d.ellipse([x - R_, y - R_, x + R_, y + R_], outline=WHITE, width=int(w))
        # Stollen am Reifen
        # kurze Stollen (kleine Rechtecke) dicht am Reifen
        for k in range(24):
            a = k * math.tau / 24
            c, s_ = math.cos(a), math.sin(a)
            r_in, r_out, hw = R_ - W(0.006), R_ + W(0.016), W(0.009)   # Ring wird nach innen gezeichnet → Stollen ansetzen
            pts = [(x + c * r_in - s_ * hw, y + s_ * r_in + c * hw), (x + c * r_out - s_ * hw, y + s_ * r_out + c * hw),
                   (x + c * r_out + s_ * hw, y + s_ * r_out - c * hw), (x + c * r_in + s_ * hw, y + s_ * r_in - c * hw)]
            d.polygon(pts, fill=WHITE)
        h = W(0.022); d.ellipse([x - h, y - h, x + h, y + h], fill=WHITE)

    wheel(0.27, 0.74, 0.125)
    wheel(0.73, 0.74, 0.125)
    line([(0.27, 0.74), (0.47, 0.63)], 0.036)                 # Schwinge
    line([(0.73, 0.74), (0.645, 0.43)], 0.04)                 # Gabel (lang, Enduro)
    line([(0.60, 0.40), (0.645, 0.43), (0.70, 0.395)], 0.03)  # Lenker
    d.polygon([P(0.43, 0.58), P(0.58, 0.56), P(0.60, 0.66), P(0.47, 0.69)], fill=WHITE)   # Motor
    line([(0.62, 0.48), (0.55, 0.63)], 0.034)                 # Rahmen-Unterzug
    d.polygon([P(0.42, 0.52), P(0.60, 0.455), P(0.645, 0.48), P(0.56, 0.55), P(0.42, 0.565)], fill=WHITE)  # Tank
    line([(0.24, 0.50), (0.44, 0.52)], 0.04)                  # Sitzbank/Heck (hoch)
    line([(0.40, 0.52), (0.33, 0.62)], 0.026)                 # Federbein
    line([(0.665, 0.53), (0.83, 0.555)], 0.03)                # hoher Kotflügel vorne
    line([(0.45, 0.60), (0.30, 0.55), (0.24, 0.53)], 0.026)   # Auspuff hochgezogen
    line([(0.60, 0.44), (0.66, 0.415)], 0.05)                 # Startnummerntafel/Scheinwerfer


def make(maskable):
    bg = background()
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    if maskable:
        img = bg
        scale, off = 0.66, S * 0.17
    else:
        mask = Image.new('L', (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=S * 0.22, fill=255)
        img.paste(bg, (0, 0), mask)
        scale, off = 0.84, S * 0.08
    draw_content(img, scale, off)
    return img


for size, mask, name in [(192, False, 'icon-192.png'), (512, False, 'icon-512.png'), (512, True, 'icon-maskable-512.png'),
                         (180, False, 'apple-touch-icon.png')]:
    make(mask).resize((size, size), Image.LANCZOS).save(f'{OUT}/{name}', optimize=True)
    print(name)
