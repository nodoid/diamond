#!/usr/bin/env python3
"""Generates every sprite of the game (Diamond.Core/Art/<name>.png) and the app icon masters
(art/icon-1024.png, art/icon-foreground-1024.png).

Run from the repository root:  python3 tools/make_sprites.py [name ...]
With no argument everything is drawn; otherwise only the named sprites ("icon" = the icons).

Sprites are painted as vector shapes on a supersampled float canvas (premultiplied RGBA), shaded
with a pseudo-3D "pillow" lighting model (light from the upper left), textured with fractal noise,
then cropped tightly (the bottom edge is the ground contact) and Lanczos-reduced to 8 px per
virtual pixel of the height listed in art/ART_SPEC.md. Everything is deterministic.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

PX = 8                      # output pixels per virtual pixel
OUT = os.path.join('Diamond.Core', 'Art')
LIGHT = np.array([-0.55, -0.75, 0.62], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)


# ----------------------------------------------------------------------------------------------
# colour helpers

def C(c):
    """Colour as float32 RGB 0..1 from '#rrggbb' or a 0..255 / 0..1 tuple."""
    if isinstance(c, str):
        c = c.lstrip('#')
        if len(c) == 3:
            c = ''.join(ch * 2 for ch in c)
        return np.array([int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    a = np.array(c, np.float32)
    return a / 255 if a.max() > 1.0 else a


def mix(a, b, t):
    return C(a) * (1 - t) + C(b) * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, sigma):
    """Gaussian blur of a 2-D float array (sigma in pixels); large sigmas via a reduced copy."""
    if sigma <= 0.3:
        return a
    if sigma <= 10:
        return ndimage.gaussian_filter(a, sigma, mode='constant')
    f = sigma / 6.0
    h, w = a.shape
    sh, sw = max(2, int(h / f)), max(2, int(w / f))
    small = np.asarray(Image.fromarray(a.astype(np.float32)).resize((sw, sh), Image.BILINEAR))
    small = ndimage.gaussian_filter(small, sigma * sw / w, mode='constant')
    return np.asarray(Image.fromarray(small).resize((w, h), Image.BILINEAR))


# ----------------------------------------------------------------------------------------------
# geometry helpers (all in virtual-pixel units)

def bez(*p, n=40):
    """Bezier curve through control points p (any degree) -> list of n points."""
    p = np.array(p, np.float64)
    out = []
    for t in np.linspace(0, 1, n):
        q = p.copy()
        while len(q) > 1:
            q = q[:-1] * (1 - t) + q[1:] * t
        out.append((q[0][0], q[0][1]))
    return out


def spline(pts, n=14, closed=False):
    """Catmull-Rom spline through pts."""
    p = [np.array(q, np.float64) for q in pts]
    if closed:
        p = [p[-1]] + p + [p[0], p[1]]
    else:
        p = [p[0]] + p + [p[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((q[0], q[1]))
    if not closed:
        out.append(tuple(p[-2]))
    return out


def tube_poly(pts, w0, w1=None, widths=None):
    p = np.array(pts, np.float64)
    n = len(p)
    if widths is None:
        widths = np.linspace(w0, w0 if w1 is None else w1, n)
    widths = np.asarray(widths, np.float64)
    d = np.gradient(p, axis=0)
    ln = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)
    nrm = np.stack([-d[:, 1] / ln, d[:, 0] / ln], 1)
    left = p + nrm * widths[:, None] / 2
    right = p - nrm * widths[:, None] / 2
    return [tuple(q) for q in left] + [tuple(q) for q in right[::-1]], widths


def ell_pts(cx, cy, rx, ry, rot=0.0, n=72, a0=0.0, a1=2 * math.pi):
    out = []
    cr, sr = math.cos(rot), math.sin(rot)
    for t in np.linspace(a0, a1, n):
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def rot_pts(pts, ang, cx=0.0, cy=0.0):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def mirror(pts, cx):
    return [(2 * cx - x, y) for x, y in pts]


# ----------------------------------------------------------------------------------------------
# colour fields: callables f(R) -> (h, w, 3) evaluated on a region R of the canvas

class Region:
    def __init__(self, cv, ys, xs):
        self.cv, self.sl = cv, (ys, xs)
        self.X = ((np.arange(xs.start, xs.stop, dtype=np.float32) + 0.5) / cv.u)[None, :]
        self.Y = ((np.arange(ys.start, ys.stop, dtype=np.float32) + 0.5) / cv.u)[:, None]
        self.shape = (ys.stop - ys.start, xs.stop - xs.start)


def stops_eval(stops, t):
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    ts = [s[0] for s in stops]
    cs = [C(s[1]) for s in stops]
    for ch in range(3):
        out[..., ch] = np.interp(t, ts, [c[ch] for c in cs])
    return out


def _stops(stops):
    if isinstance(stops[0], tuple) and len(stops[0]) == 2:
        return stops
    n = len(stops)
    return tuple((i / (n - 1), c) for i, c in enumerate(stops))


def Lin(x0, y0, x1, y1, *stops):
    """Linear gradient from (x0,y0) to (x1,y1): colours, or (t, colour) stops."""
    stops = _stops(stops)
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy

    def f(R):
        t = ((R.X - x0) * dx + (R.Y - y0) * dy) / l2
        return stops_eval(stops, np.broadcast_to(t, R.shape))
    return f


def Rad(cx, cy, r, *stops, sy=1.0):
    stops = _stops(stops)

    def f(R):
        t = np.sqrt((R.X - cx) ** 2 + ((R.Y - cy) / sy) ** 2) / r
        return stops_eval(stops, np.broadcast_to(t, R.shape))
    return f


def Tex(field, amt, scale=1.0, seed=0, aniso=(1, 1), octaves=4):
    """Multiply a colour (or field) by fractal noise: 1 + amt*(n-0.5)*2."""
    def f(R):
        base = field(R) if callable(field) else np.broadcast_to(C(field), R.shape + (3,))
        n = R.cv.noise(scale, seed, aniso, octaves)[R.sl]
        return base * (1 + amt * (n[..., None] - 0.5) * 2)
    return f


def field_eval(col, R):
    if callable(col):
        return col(R)
    return np.broadcast_to(C(col), R.shape + (3,))


# ----------------------------------------------------------------------------------------------
# the canvas

class Canvas:
    def __init__(self, w, h, ss=3, seed=0):
        self.ss = ss
        self.u = PX * ss
        self.w, self.h = w, h
        self.W, self.H = int(math.ceil(w * self.u)), int(math.ceil(h * self.u))
        self.img = np.zeros((self.H, self.W, 4), np.float32)
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.ground = None
        self.anchor = None
        self._noise = {}

    # --- masks
    def _draw(self):
        im = Image.new('L', (self.W, self.H), 0)
        return im, ImageDraw.Draw(im)

    def _arr(self, im):
        return np.asarray(im, np.float32) / 255.0

    def P(self, pts):
        u = self.u
        return [(x * u, y * u) for x, y in pts]

    def poly(self, *polys):
        im, d = self._draw()
        for pts in polys:
            d.polygon(self.P(pts), fill=255)
        return self._arr(im)

    def ellipse(self, cx, cy, rx, ry, rot=0.0):
        if rot:
            return self.poly(ell_pts(cx, cy, rx, ry, rot, 96))
        im, d = self._draw()
        u = self.u
        d.ellipse([(cx - rx) * u, (cy - ry) * u, (cx + rx) * u, (cy + ry) * u], fill=255)
        return self._arr(im)

    def circle(self, cx, cy, r):
        return self.ellipse(cx, cy, r, r)

    def rect(self, x0, y0, x1, y1):
        return self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    def rrect(self, x0, y0, x1, y1, r):
        im, d = self._draw()
        u = self.u
        d.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=r * u, fill=255)
        return self._arr(im)

    def line(self, pts, w, caps=True):
        im, d = self._draw()
        u = self.u
        P = self.P(pts)
        d.line(P, fill=255, width=max(1, int(round(w * u))), joint='curve')
        if caps:
            r = w * u / 2
            for x, y in (P[0], P[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return self._arr(im)

    def lines(self, segs, w):
        """Many separate polylines of the same width in one mask."""
        im, d = self._draw()
        u = self.u
        r = w * u / 2
        for pts in segs:
            P = self.P(pts)
            d.line(P, fill=255, width=max(1, int(round(w * u))), joint='curve')
            for x, y in (P[0], P[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return self._arr(im)

    def tube(self, pts, w0, w1=None, widths=None, caps=True):
        poly, ws = tube_poly(pts, w0, w1, widths)
        im, d = self._draw()
        u = self.u
        d.polygon(self.P(poly), fill=255)
        if caps:
            for (x, y), w in ((pts[0], ws[0]), (pts[-1], ws[-1])):
                r = w * u / 2
                d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=255)
        return self._arr(im)

    def feather(self, m, r):
        return np.clip(blur(m, r * self.u), 0, 1)

    # --- noise
    def noise(self, scale=1.0, seed=0, aniso=(1, 1), octaves=4):
        key = (scale, seed, tuple(aniso), octaves)
        if key in self._noise:
            return self._noise[key]
        rng = np.random.default_rng(1000 + seed * 7919 + int(scale * 100))
        acc = np.zeros((self.H, self.W), np.float32)
        tot = 0.0
        amp = 1.0
        for o in range(octaves):
            cell = scale * self.u / (2 ** o)
            gw = max(2, int(self.W / (cell * aniso[0])) + 3)
            gh = max(2, int(self.H / (cell * aniso[1])) + 3)
            g = rng.random((gh, gw)).astype(np.float32)
            im = Image.fromarray(g).resize((self.W, self.H), Image.BICUBIC)
            acc += amp * np.asarray(im)
            tot += amp
            amp *= 0.55
        acc /= tot
        lo, hi = np.percentile(acc[::7, ::7], [1, 99])
        acc = np.clip((acc - lo) / max(hi - lo, 1e-6), 0, 1)
        self._noise[key] = acc
        return acc

    # --- painting
    def _bbox(self, m, pad=0):
        rows = np.flatnonzero(m.max(1) > 1e-4)
        if len(rows) == 0:
            return None
        cols = np.flatnonzero(m[rows[0]:rows[-1] + 1].max(0) > 1e-4)
        y0, y1 = max(0, rows[0] - pad), min(self.H, rows[-1] + 1 + pad)
        x0, x1 = max(0, cols[0] - pad), min(self.W, cols[-1] + 1 + pad)
        return slice(y0, y1), slice(x0, x1)

    def paint(self, m, col, alpha=1.0):
        bb = self._bbox(m)
        if bb is None:
            return
        R = Region(self, *bb)
        a = (m[bb] * alpha)[..., None]
        c = field_eval(col, R)
        dst = self.img[bb]
        dst[..., :3] = dst[..., :3] * (1 - a) + c * a
        dst[..., 3:] = dst[..., 3:] * (1 - a) + a

    def erase(self, m, amount=1.0):
        bb = self._bbox(m)
        if bb is None:
            return
        self.img[bb] *= (1 - m[bb] * amount)[..., None]

    def shade(self, m, col, r=1.5, amb=0.42, diff=0.78, spec=0.25, shin=18, rim=0.35, bulge=1.0,
              tex=0.0, tscale=1.0, tseed=0, aniso=(1, 1), alpha=1.0, light=None, hmap=None, ret=False):
        """Paint mask m with colour/field col, lit as a soft rounded volume (pillow shading)."""
        rp = r * self.u
        bb = self._bbox(m, int(rp * 2.5) + 2)
        if bb is None:
            return
        R = Region(self, *bb)
        mc = m[bb]
        h = blur(mc, rp) if hmap is None else hmap[bb]
        gy, gx = np.gradient(h)
        k = bulge * rp * 1.6
        nx, ny = -gx * k, -gy * k
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
        nx, ny, nz = nx * inv, ny * inv, inv
        L = LIGHT if light is None else light
        lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
        sh = amb + diff * lam
        if rim:
            sh = sh * (1 - rim * (1 - smooth(0.0, 0.75, h)))
        c = field_eval(col, R) * sh[..., None]
        if tex:
            n = self.noise(tscale, tseed, aniso)[bb]
            c = c * (1 + tex * (n[..., None] - 0.5) * 2)
        if spec:
            hd = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)
            c = c + spec * (hd ** shin)[..., None]
        c = np.clip(c, 0, 1.2)
        a = (mc * alpha)[..., None]
        dst = self.img[bb]
        dst[..., :3] = dst[..., :3] * (1 - a) + c * a
        dst[..., 3:] = dst[..., 3:] * (1 - a) + a

    def glow(self, m, col, r, alpha=1.0):
        self.paint(np.clip(blur(m, r * self.u), 0, 1), col, alpha)

    def shadow(self, cx, base, rx, ry, alpha=0.35, soft=None):
        soft = ry * 0.6 if soft is None else soft
        m = self.feather(self.ellipse(cx, base - ry * 0.55, rx, ry), soft)
        m[int(base * self.u):] = 0
        self.paint(m, (0.04, 0.03, 0.02), alpha)

    def hl(self, cx, cy, rx, ry, alpha=0.6, rot=0.0, soft=0.4, col=(1, 1, 1)):
        self.paint(self.feather(self.ellipse(cx, cy, rx, ry, rot), min(rx, ry) * soft), col, alpha)

    def sparkle(self, cx, cy, size, alpha=1.0, col=(1, 1, 1), thin=0.07, ang=0.0):
        s = size
        pts = []
        for i in range(8):
            a = ang + i * math.pi / 4
            rr = s if i % 2 == 0 else s * thin * 2.2
            if i % 4 == 2:
                rr = s * 0.55
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        star = self.poly(pts)
        self.glow(self.circle(cx, cy, s * 0.22), col, s * 0.18, alpha * 0.9)
        self.paint(self.feather(star, s * 0.03), col, alpha)

    def hairs(self, m, n, length, width, col, seed=0, angle=None, jitter=0.6, clip=None, alpha=1.0, lw=None):
        """Draw n short strokes rooted inside mask m. angle(x,y)->direction (radians) in units."""
        rng = np.random.default_rng(seed)
        idx = np.flatnonzero(m.ravel() > 0.5)
        if len(idx) == 0:
            return
        pick = rng.choice(idx, size=min(n, len(idx) * 4), replace=True)
        ys, xs = np.divmod(pick, self.W)
        im, d = self._draw()
        u = self.u
        wpx = max(1, int(round(width * u)))
        for x, y in zip(xs, ys):
            xu, yu = x / u, y / u
            a = angle(xu, yu) if angle else rng.uniform(0, 2 * math.pi)
            a += rng.normal(0, jitter)
            L = length * rng.uniform(0.6, 1.3) * u
            d.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=255, width=wpx)
        hm = self._arr(im)
        if clip is not None:
            hm = hm * clip
        self.paint(hm, col, alpha)

    def over(self, other, alpha=1.0):
        a = other.img[..., 3:] * alpha
        self.img[..., :3] = self.img[..., :3] * (1 - a) + other.img[..., :3] * alpha
        self.img[..., 3:] = self.img[..., 3:] * (1 - a) + a

    def layer(self):
        c = Canvas.__new__(Canvas)
        c.__dict__.update(self.__dict__)
        c.img = np.zeros_like(self.img)
        return c

    # --- output
    def crop_image(self, vh, margin=2):
        a = self.img[..., 3]
        rows = np.flatnonzero(a.max(1) > 3 / 255)
        y0, y1 = rows[0], rows[-1] + 1
        if self.ground is not None:
            y1 = min(self.H, int(round(self.ground * self.u)))
        cols = np.flatnonzero(a[y0:y1].max(0) > 3 / 255)
        x0, x1 = cols[0], cols[-1] + 1
        m = margin * self.ss
        y0, x0, x1 = max(0, y0 - m), max(0, x0 - m), min(self.W, x1 + m)
        if self.anchor is not None:
            ax = self.anchor * self.u
            half = max(ax - x0, x1 - ax)
            x0, x1 = int(ax - half), int(ax + half)
        crop = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
        sx0, sx1 = max(0, x0), min(self.W, x1)
        crop[:, sx0 - x0:sx1 - x0] = self.img[y0:y1, sx0:sx1]
        oh = int(round(vh * PX))
        ow = max(1, int(round(crop.shape[1] * oh / crop.shape[0])))
        chans = [np.asarray(Image.fromarray(np.ascontiguousarray(crop[..., i])).resize((ow, oh), Image.LANCZOS))
                 for i in range(4)]
        out = np.stack(chans, -1)
        al = np.clip(out[..., 3:], 0, 1)
        rgb = np.where(al > 1e-4, out[..., :3] / np.maximum(al, 1e-4), 0)
        res = np.concatenate([np.clip(rgb, 0, 1), al], -1)
        return Image.fromarray((res * 255 + 0.5).astype(np.uint8))

    def save(self, name, vh):
        im = self.crop_image(vh)
        os.makedirs(OUT, exist_ok=True)
        im.save(os.path.join(OUT, name + '.png'), optimize=True)
        print(f'{name:14s} {im.width:4d} x {im.height:4d}')
        return im


SPRITES = {}


def sprite(name, vh):
    def deco(fn):
        SPRITES[name] = (fn, vh)
        return fn
    return deco


# ==============================================================================================
# SPRITES
# ==============================================================================================

# ---- small objects -----------------------------------------------------------------------------

def radial(cx, cy, off=0.0):
    return lambda x, y: math.atan2(y - cy, x - cx) + off


@sprite('coconut', 9)
def coconut():
    cv = Canvas(14, 12, seed=1)
    cv.ground = 10.6
    cv.shadow(7, 10.6, 5.6, 1.1, 0.45)
    body = cv.ellipse(7, 6.0, 5.2, 4.55, rot=-0.18)
    cv.shade(body, Rad(5.0, 3.8, 7.5, '#a8703f', '#6a3e1c', '#3b2210'), r=1.8, spec=0.12, tex=0.35, tscale=0.25, tseed=4)
    ang = radial(7, 6.0, 1.35)
    cv.hairs(body, 1400, 1.1, 0.12, '#d29a5c', seed=2, angle=ang, jitter=0.35, clip=body, alpha=0.45)
    cv.hairs(body, 900, 1.0, 0.12, '#24140a', seed=3, angle=ang, jitter=0.35, clip=body, alpha=0.45)
    rim = body - cv.feather(cv.ellipse(7, 6.0, 4.6, 3.95, rot=-0.18), 0.1)
    rim = np.clip(rim, 0, 1)
    cv.hairs(rim, 260, 0.8, 0.13, '#8a5a30', seed=5, angle=radial(7, 6.0, 0.0), jitter=0.5, alpha=0.8)
    # the three "eyes"
    for ex, ey, rr in ((3.7, 4.6, 0.62), (5.2, 4.1, 0.58), (4.6, 5.8, 0.6)):
        e = cv.ellipse(ex, ey, rr, rr * 0.85)
        cv.shade(e, '#1c0f06', r=0.3, spec=0.15, rim=0.0, amb=0.7)
    cv.hl(4.2, 3.2, 1.6, 0.8, 0.18, rot=-0.5)
    return cv


def draw_diamond(cv, cx, top, s, glow=True, sparkles=True, edge=0.05):
    """A brilliant-cut diamond, point down: width 2*s, height 1.65*s, top edge at y=top."""
    def T(pts):
        return [(cx + x * s, top + y * s) for x, y in pts]
    tt = [-0.56, -0.19, 0.19, 0.56]
    gg = [-1.0, -0.5, 0.0, 0.5, 1.0]
    gy, cul = 0.32, 1.65
    if glow:
        g = cv.ellipse(cx, top + 0.6 * s, 1.05 * s, 0.8 * s)
        cv.glow(g, '#9fd8ff', 0.25 * s, 0.3)
    outline = T([(-0.56, 0), (0.56, 0), (1, gy), (0, cul), (-1, gy)])
    cv.paint(cv.poly(outline), '#cfeeff')
    crown_cols = ['#f4fbff', '#ffffff', '#cdeaff', '#eaf6ff', '#a8d6ff', '#dff1ff', '#7fb8f2']
    pts = []
    for i in range(4):
        pts.append((gg[i], gy))
        pts.append((tt[i], 0))
    pts.append((gg[4], gy))
    facets = []
    for i in range(len(pts) - 2):
        facets.append([pts[i], pts[i + 1], pts[i + 2]])
    for f, c in zip(facets, crown_cols):
        m = cv.poly(T(f))
        cx0 = sum(p[0] for p in f) / 3
        col = Lin(cx + (cx0 - 0.4) * s, top, cx + (cx0 + 0.5) * s, top + gy * s, mix(c, '#ffffff', 0.35), mix(c, '#4c86d8', 0.25))
        cv.paint(m, col)
    pav_cols = ['#e9f5ff', '#9ccdfb', '#ffffff', '#5b9be6', '#c7e4ff', '#3d74cf', '#8cc0f5', '#2b56b0']
    k = 0
    for i in range(4):
        a, b = gg[i], gg[i + 1]
        mid = (a + b) / 2
        for f in ([(a, gy), (mid, gy), (0, cul)], [(mid, gy), (b, gy), (0, cul)]):
            m = cv.poly(T(f))
            c = pav_cols[k]
            col = Lin(cx - 0.6 * s, top + gy * s, cx + 0.6 * s, top + cul * s, mix(c, '#ffffff', 0.25), mix(c, '#1d3f8f', 0.35))
            cv.paint(m, col)
            k += 1
    # fire: soft coloured flecks
    for (fx, fy, c) in ((-0.35, 0.75, '#ff9ad5'), (0.42, 0.6, '#ffe08a'), (0.15, 1.05, '#9affea'), (-0.65, 0.42, '#c9a6ff')):
        cv.hl(cx + fx * s, top + fy * s, 0.12 * s, 0.07 * s, 0.55, col=C(c))
    # facet edges
    segs = [T([(tt[0], 0), (tt[3], 0)]), T([(-1, gy), (1, gy)])]
    for i in range(len(pts) - 1):
        segs.append(T([pts[i], pts[i + 1]]))
    for x in gg + [(gg[i] + gg[i + 1]) / 2 for i in range(4)]:
        segs.append(T([(x, gy), (0, cul)]))
    cv.paint(cv.lines(segs, edge * s * 0.5) * cv.poly(outline), '#ffffff', 0.55)
    cv.paint(np.clip(cv.line(T([(-0.56, 0), (0.56, 0), (1, gy), (0, cul), (-1, gy), (-0.56, 0)]), edge * s, caps=False), 0, 1), '#e8f8ff', 0.85)
    if sparkles:
        cv.sparkle(cx - 0.42 * s, top + 0.12 * s, 0.75 * s, 1.0)
        cv.sparkle(cx + 0.5 * s, top + 0.55 * s, 0.38 * s, 0.9, ang=0.3)
        cv.sparkle(cx - 0.1 * s, top + 1.2 * s, 0.25 * s, 0.8)


@sprite('diamond', 14)
def diamond():
    cv = Canvas(30, 22, seed=2)
    cv.ground = 4.0 + 1.65 * 8.2
    draw_diamond(cv, 15, 4.0, 8.2, glow=True)
    return cv


@sprite('key', 5)
def key():
    cv = Canvas(19, 7, seed=3)
    cv.ground = 6.0
    cv.shadow(9.5, 6.0, 8.5, 0.9, 0.4)
    iron = Tex(Lin(0, 0.5, 0, 5.5, '#8c8a86', '#4a4642', '#2c2926'), 0.18, 0.5, 9)
    bow = cv.ellipse(3.2, 3.0, 2.6, 2.3)
    shaft = cv.tube([(5.0, 3.0), (15.6, 3.1)], 1.15)
    collar = np.maximum(cv.rrect(5.0, 2.0, 6.2, 4.1, 0.3), cv.rrect(6.6, 2.2, 7.3, 3.9, 0.25))
    bit = cv.poly([(13.2, 3.0), (16.0, 3.0), (16.0, 5.7), (15.3, 5.7), (15.3, 4.8), (14.6, 4.8), (14.6, 5.7), (13.2, 5.7)])
    m = np.clip(bow + shaft + collar + bit, 0, 1)
    hole = cv.ellipse(3.2, 3.0, 1.35, 1.15)
    m = m * (1 - hole)
    cv.shade(m, iron, r=0.55, spec=0.55, shin=24, rim=0.3, tex=0.2, tscale=0.3, tseed=7)
    # rust flecks
    rust = cv.feather((cv.noise(0.35, 11) > 0.72).astype(np.float32), 0.05) * m
    cv.paint(rust, '#8a4a22', 0.55)
    cv.hl(2.4, 1.3, 1.2, 0.3, 0.5, rot=-0.3)
    cv.hl(10, 2.75, 4.2, 0.18, 0.45)
    return cv


@sprite('club', 7)
def club():
    cv = Canvas(32, 10, seed=4)
    cv.ground = 8.6
    cv.shadow(16, 8.6, 14.5, 1.3, 0.42)
    path = bez((2.0, 6.6), (10, 6.2), (18, 5.0), (27.5, 4.4), n=50)
    ws = [1.7 + 4.3 * smooth(0.3, 0.92, t) ** 0.8 for t in np.linspace(0, 1, len(path))]
    m = cv.tube(path, 0, widths=ws)
    for kx, ky, kr in ((22.0, 3.0, 1.1), (25.8, 6.4, 1.0), (27.6, 2.6, 1.2)):
        m = np.maximum(m, cv.circle(kx, ky, kr))
    wood = Tex(Lin(0, 1.5, 0, 7.5, '#c9b89a', '#9c8a6c', '#5e5040'), 0.22, 1.0, 3, aniso=(8, 0.6))
    cv.shade(m, wood, r=1.1, spec=0.1, tex=0.25, tscale=0.6, tseed=12, aniso=(10, 0.5))
    # grain cracks
    rng = np.random.default_rng(4)
    segs = []
    for i in range(9):
        y = rng.uniform(-1.4, 1.4)
        x0 = rng.uniform(4, 18)
        seg = [(x, 6.6 - (x - 2) * 0.085 + y * (0.4 + x / 30) + 0.15 * math.sin(x * 0.9 + i)) for x in np.linspace(x0, x0 + rng.uniform(4, 9), 12)]
        segs.append(seg)
    cv.paint(cv.lines(segs, 0.14) * m, '#3c3024', 0.55)
    for kx, ky in ((22.1, 2.9), (25.8, 6.2), (27.5, 2.7)):
        cv.paint(cv.ellipse(kx + 0.1, ky + 0.1, 0.45, 0.35) * m, '#4a3c2c', 0.6)
    cv.hl(12, 4.9, 6, 0.35, 0.3, rot=-0.08)
    return cv


@sprite('knife', 5)
def knife():
    cv = Canvas(34, 7, seed=5)
    cv.ground = 6.0
    cv.shadow(17, 6.0, 15.5, 0.9, 0.4)
    blade = cv.poly([(9.5, 1.6), (25, 1.3), (30.5, 1.0), (32.6, 1.6)] + bez((32.6, 1.6), (31, 4.0), (24, 5.0), (9.5, 4.9), n=24))
    steel = Lin(0, 1.2, 0, 5.0, '#f2f5f7', '#b7bec5', '#6f7880', '#d8dee3')
    cv.shade(blade, steel, r=0.4, spec=0.5, shin=30, rim=0.15, tex=0.08, tscale=2.0, tseed=3, aniso=(6, 0.4))
    bevel = cv.poly(bez((32.6, 1.6), (31, 4.0), (24, 5.0), (9.5, 4.9), n=24) + bez((9.5, 4.2), (24, 4.3), (30.6, 3.2), (32.0, 1.75), n=24))
    cv.paint(bevel * blade, Lin(0, 3.6, 0, 5.0, '#ffffff', '#c8d0d6'), 0.75)
    cv.paint(cv.line([(10, 1.8), (30, 1.4)], 0.18), '#ffffff', 0.6)
    guard = cv.rrect(8.6, 0.9, 9.9, 5.6, 0.4)
    cv.shade(guard, '#6e6a62', r=0.3, spec=0.5)
    handle = cv.rrect(0.8, 1.9, 8.8, 4.7, 1.2)
    wood = Tex(Lin(0, 1.8, 0, 4.8, '#8a5634', '#5b3420', '#2e1a10'), 0.25, 0.7, 5, aniso=(6, 0.5))
    cv.shade(handle, wood, r=0.6, spec=0.18)
    for rx in (2.7, 6.2):
        cv.shade(cv.circle(rx, 3.25, 0.45), '#d6c9a8', r=0.2, spec=0.7, rim=0.1)
    return cv


def smooth_union(cv, m, r):
    """Metaball-style blend of a mask's parts (r in units)."""
    return smooth(0.35, 0.65, blur(m, r * cv.u))


def rope_path(cv, path, w, col='#c2a26a', dark='#5a4424', twist=0.85, alpha=1.0, shade_r=None):
    m = cv.tube(path, w)
    cv.shade(m, col, r=shade_r or w * 0.45, spec=0.12, rim=0.4, tex=0.15, tscale=0.4, alpha=alpha)
    p = np.array(path, np.float64)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    segs = []
    step = w * twist
    for t in np.arange(step * 0.5, s[-1], step):
        x = np.interp(t, s, p[:, 0])
        y = np.interp(t, s, p[:, 1])
        i = min(np.searchsorted(s, t), len(p) - 1)
        i0 = max(i - 1, 0)
        dx, dy = p[i] - p[i0]
        ln = math.hypot(dx, dy) or 1
        dx, dy = dx / ln, dy / ln
        nx, ny = -dy, dx
        hw = w * 0.5
        segs.append([(x - nx * hw - dx * hw * 0.7, y - ny * hw - dy * hw * 0.7), (x + nx * hw + dx * hw * 0.7, y + ny * hw + dy * hw * 0.7)])
    cv.paint(cv.lines(segs, w * 0.13) * m, dark, 0.6 * alpha)
    return m


@sprite('gourd', 12)
def gourd():
    cv = Canvas(15, 16, seed=6)
    cv.ground = 15.0
    cv.shadow(7.0, 15.0, 5.2, 1.1, 0.45)
    m = np.maximum(cv.ellipse(7, 10.4, 4.6, 4.4), cv.ellipse(7, 5.0, 2.6, 2.5))
    m = np.maximum(m, cv.rect(5.9, 4, 8.1, 8))
    m = smooth_union(cv, m, 0.55)
    cv.shade(m, Rad(5.2, 7.0, 8.5, '#f0c26a', '#c98c34', '#7a4a18'), r=1.8, spec=0.35, shin=14, tex=0.18, tscale=0.6, tseed=3)
    # mottled streaks
    streak = (cv.noise(0.9, 21, (0.4, 3)) > 0.62).astype(np.float32)
    cv.paint(cv.feather(streak, 0.2) * m, '#8a5420', 0.25)
    # stopper
    cork = cv.poly([(5.9, 1.0), (8.1, 1.0), (7.85, 3.4), (6.15, 3.4)])
    cv.shade(cork, Tex('#b98a5a', 0.35, 0.25, 4), r=0.4, spec=0.1)
    cv.shade(cv.ellipse(7, 1.0, 1.1, 0.35), '#d2a676', r=0.2, rim=0.1)
    # cord round the neck and a carrying loop
    rope_path(cv, bez((4.7, 7.4), (7.0, 8.4), (9.3, 7.4), n=20), 0.6, '#8b6a3e', '#3d2a14')
    rope_path(cv, bez((4.6, 7.3), (1.0, 3.0), (4.0, -0.6), (7.0, 0.2), (10.0, -0.6), (13.0, 3.0), (9.4, 7.3), n=60), 0.55, '#8b6a3e', '#3d2a14')
    cv.hl(4.6, 8.6, 1.3, 2.4, 0.35, rot=0.3)
    cv.hl(6.1, 3.9, 0.6, 0.9, 0.35)
    return cv


def table_draw(open_):
    cv = Canvas(62, 42, ss=3, seed=7)
    cv.ground = 39.5
    G = 39.5
    wood = lambda s: Tex(Lin(0, 3, 0, 40, '#a8743f', '#7a4e28', '#4a2c16'), 0.3, 1.4, s, aniso=(9, 0.5))
    # shadow on the ground
    cv.paint(cv.feather(cv.poly([(7, 34.5), (55, 34.5), (58, G + 0.6), (4, G + 0.6)]), 1.6), (0.03, 0.02, 0.01), 0.45)
    # back legs
    for x0 in (12.5, 46.5):
        leg = cv.poly([(x0, 16), (x0 + 3, 16), (x0 + 2.8, 34.6), (x0 + 0.2, 34.6)])
        cv.shade(leg, Tex('#4e3018', 0.3, 0.8, 4, aniso=(0.4, 6)), r=0.8, spec=0.05)
    # front legs
    for x0 in (5.0, 52.8):
        leg = cv.poly([(x0, 12), (x0 + 4.2, 12), (x0 + 3.9, G), (x0 + 0.3, G)])
        cv.shade(leg, Tex(Lin(x0, 0, x0 + 4.2, 0, '#9a6a3a', '#5c3a1c'), 0.35, 0.8, 5 + int(x0), aniso=(0.4, 7)), r=1.0, spec=0.08)
        # stretcher peg + worn foot
        cv.paint(cv.rect(x0, G - 1.0, x0 + 4.2, G), '#2e1c0e', 0.5)
    # stretcher between back and front legs (low rail)
    rail = cv.poly([(9, 28.5), (13, 26.5), (13, 28), (9, 30.2)])
    cv.shade(rail, '#5a3a1e', r=0.4)
    rail = cv.poly([(53, 28.5), (49, 26.5), (49, 28), (53, 30.2)])
    cv.shade(rail, '#5a3a1e', r=0.4)
    # apron
    ap = cv.rect(6, 11.5, 56, 19.5)
    cv.shade(ap, wood(8), r=0.8, spec=0.05, rim=0.2)
    cv.paint(cv.rect(6, 18.6, 56, 19.5), '#2c1a0c', 0.55)
    # drawer
    dx0, dx1, dy0, dy1 = 22, 40, 12.6, 18.4
    if not open_:
        cv.paint(cv.rect(dx0 - 0.35, dy0 - 0.35, dx1 + 0.35, dy1 + 0.35), '#1e1008', 0.9)
        front = cv.rect(dx0, dy0, dx1, dy1)
        cv.shade(front, Tex(Lin(0, dy0, 0, dy1, '#b07c46', '#7c5028'), 0.3, 1.2, 9, aniso=(8, 0.5)), r=0.6, spec=0.1)
        kx, ky = 31, 15.5
    else:
        cv.paint(cv.rect(dx0 - 0.3, dy0 - 0.3, dx1 + 0.3, dy1 + 0.3), '#120904', 1.0)
        # drawer pulled out: sides, inside, front lower and larger
        ex0, ex1, ey0, ey1 = dx0 - 0.9, dx1 + 0.9, dy0 + 6.2, dy1 + 6.8
        inside = cv.poly([(dx0 + 0.3, dy0 + 1.2), (dx1 - 0.3, dy0 + 1.2), (ex1 - 0.7, ey0 + 0.6), (ex0 + 0.7, ey0 + 0.6)])
        cv.paint(inside, Lin(0, dy0, 0, ey0, '#1a0e06', '#4a2e16'))
        bottom = cv.poly([(dx0 + 1.2, dy0 + 2.4), (dx1 - 1.2, dy0 + 2.4), (ex1 - 1.6, ey0 + 0.2), (ex0 + 1.6, ey0 + 0.2)])
        cv.paint(bottom, Tex(Lin(0, dy0, 0, ey0, '#2a1709', '#6a4422'), 0.25, 0.9, 13, aniso=(0.5, 5)))
        for sx0, sx1, ex in ((dx0, dx0 + 1.2, ex0), (dx1 - 1.2, dx1, ex1)):
            pass
        sideL = cv.poly([(dx0 + 0.1, dy0 + 0.6), (dx0 + 1.2, dy0 + 0.6), (ex0 + 1.6, ey0 + 0.4), (ex0 + 0.1, ey0 + 0.4)])
        sideR = cv.poly([(dx1 - 1.2, dy0 + 0.6), (dx1 - 0.1, dy0 + 0.6), (ex1 - 0.1, ey0 + 0.4), (ex1 - 1.6, ey0 + 0.4)])
        cv.shade(sideL, '#9a6a38', r=0.3, spec=0.05)
        cv.shade(sideR, '#6a4420', r=0.3, spec=0.05)
        cv.paint(cv.feather(cv.rect(dx0, dy0 + 1.0, dx1, dy0 + 3.2), 0.6) * inside, (0, 0, 0), 0.6)
        front = cv.rect(ex0, ey0, ex1, ey1)
        cv.paint(cv.feather(cv.rect(ex0 + 0.5, ey1, ex1 + 0.3, ey1 + 1.4), 0.5), (0, 0, 0), 0.4)
        cv.shade(front, Tex(Lin(0, ey0, 0, ey1, '#b07c46', '#7c5028'), 0.3, 1.2, 9, aniso=(8, 0.5)), r=0.6, spec=0.1)
        cv.paint(cv.rect(ex0, ey0, ex1, ey0 + 0.5), '#d09a60', 0.6)
        kx, ky = 31, (ey0 + ey1) / 2
    knob = cv.circle(kx, ky, 1.15)
    cv.paint(cv.feather(cv.circle(kx + 0.35, ky + 0.45, 1.2), 0.3), (0, 0, 0), 0.5)
    cv.shade(knob, '#8a6a40', r=0.5, spec=0.5, shin=20)
    # top slab: surface seen from above + front edge
    top = cv.poly([(9.5, 3.0), (52.5, 3.0), (58.5, 9.5), (3.5, 9.5)])
    cv.shade(top, Tex(Lin(0, 3, 0, 9.5, '#b8844c', '#9a6a38'), 0.32, 1.4, 17, aniso=(10, 0.35)), r=0.6, spec=0.08, rim=0.1)
    # planks seams converge
    segs = []
    for f in (0.25, 0.5, 0.75):
        segs.append([(9.5 + 43 * f, 3.0), (3.5 + 55 * f, 9.5)])
    cv.paint(cv.lines(segs, 0.18) * top, '#3a220e', 0.7)
    cv.paint(cv.lines([[(9.5 + 43 * f + 0.25, 3.0), (3.5 + 55 * f + 0.25, 9.5)] for f in (0.25, 0.5, 0.75)], 0.12) * top, '#e0b07a', 0.35)
    edge = cv.poly([(3.5, 9.5), (58.5, 9.5), (58.3, 12.2), (3.7, 12.2)])
    cv.shade(edge, Tex(Lin(0, 9.5, 0, 12.2, '#a06c38', '#5e3a1a'), 0.3, 1.0, 19, aniso=(8, 0.5)), r=0.5, spec=0.1)
    cv.paint(cv.line([(3.6, 9.55), (58.4, 9.55)], 0.3, caps=False), '#e8b880', 0.55)
    # knots, nail heads, scratches
    for x, y in ((18, 6.2), (44, 5.0), (12, 26), (54.6, 30)):
        cv.paint(cv.ellipse(x, y, 0.9, 0.45), '#3e2410', 0.6)
    for x, y in ((7.2, 10.8), (16.5, 10.8), (31, 10.8), (45.5, 10.8), (55, 10.8)):
        cv.shade(cv.circle(x, y, 0.38), '#3a3632', r=0.15, spec=0.6)
    rng = np.random.default_rng(7)
    scr = [[(x, y), (x + rng.uniform(1, 4), y + rng.uniform(-0.3, 0.3))] for x, y in zip(rng.uniform(10, 48, 10), rng.uniform(4, 9, 10))]
    cv.paint(cv.lines(scr, 0.1) * top, '#ffe2b0', 0.3)
    return cv


@sprite('table', 36)
def table():
    return table_draw(False)


@sprite('table_open', 36)
def table_open():
    return table_draw(True)


@sprite('cigarettes', 5)
def cigarettes():
    cv = Canvas(14, 7, seed=8)
    cv.ground = 6.0
    cv.shadow(7, 6.0, 6.2, 0.9, 0.4)
    # two cigarettes spilling out
    for (x0, y0, x1, y1) in ((0.6, 4.6, 3.8, 4.1), (1.4, 5.3, 4.2, 5.2)):
        cig = cv.tube([(x0, y0), (x1, y1)], 0.72)
        cv.shade(cig, '#f4f1ea', r=0.3, spec=0.2)
        tip = cv.tube([(x0, y0), (x0 + 0.9 * (x1 - x0) / abs(x1 - x0) * 1.1, y0 + (y1 - y0) * 0.3)], 0.72)
        cv.shade(tip * cig, '#d89a4a', r=0.3, spec=0.2)
    top = cv.poly([(2.6, 2.5), (5.5, 1.3), (9.2, 0.8), (12.7, 1.6), (10.2, 3.2), (6.5, 3.9), (3.4, 4.1)])
    front = cv.poly([(3.4, 4.1), (6.5, 3.9), (10.2, 3.2), (12.7, 1.6), (12.6, 3.3), (10.1, 5.0), (6.6, 5.7), (3.5, 5.6)])
    end = cv.poly([(2.6, 2.5), (3.4, 4.1), (3.5, 5.6), (2.5, 4.4)])
    cv.shade(top, Lin(4, 0, 10, 4, '#ffffff', '#e6e2da'), r=0.5, spec=0.25, rim=0.1)
    redtop = cv.poly([(7.4, 1.0), (9.2, 0.8), (12.7, 1.6), (10.2, 3.2), (8.6, 3.5)])
    cv.shade(redtop * top, '#d22a22', r=0.4, spec=0.3, rim=0.1)
    cv.shade(front, Lin(0, 3, 0, 6, '#f0ece4', '#c9c3b8'), r=0.4, spec=0.15, rim=0.1)
    redf = cv.poly([(8.6, 3.5), (10.2, 3.2), (12.7, 1.6), (12.6, 3.3), (10.1, 5.0), (8.7, 5.3)])
    cv.shade(redf * front, '#a81c16', r=0.3, spec=0.2, rim=0.1)
    cv.shade(end, '#b7b0a4', r=0.3, rim=0.1)
    # gold foil strip and crumples
    cv.paint(cv.line([(3.0, 2.95), (6.3, 1.85)], 0.25), '#e8c060', 0.9)
    creases = [[(5.2, 1.5), (6.1, 3.8)], [(9.5, 1.0), (8.6, 3.4)], [(6.6, 4.0), (7.4, 5.5)], [(10.2, 3.3), (11.0, 4.4)], [(4.0, 2.2), (5.0, 3.0)]]
    cv.paint(cv.lines(creases, 0.12) * np.maximum(top, front), '#5a5048', 0.55)
    cv.paint(cv.lines([[(x + 0.15, y) for x, y in c] for c in creases], 0.1) * np.maximum(top, front), '#ffffff', 0.6)
    return cv


def torch_head(cv, path, w, seed=0, burnt=0.0):
    """Rag-wrapped torch head along path (list of 2 points), w = diameter."""
    (x0, y0), (x1, y1) = path
    L = math.hypot(x1 - x0, y1 - y0)
    dx, dy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -dy, dx
    pts = [(x0 + dx * t, y0 + dy * t) for t in np.linspace(0, L, 20)]
    ws = [w * (0.75 + 0.25 * math.sin(math.pi * min(1, t / L * 1.2))) for t in np.linspace(0, L, 20)]
    m = cv.tube(pts, 0, widths=ws)
    rag = Tex(mix('#b8a07a', '#3a2c20', burnt), 0.35, 0.4, seed + 2)
    cv.shade(m, rag, r=w * 0.3, spec=0.08, rim=0.45, tex=0.25, tscale=0.25, tseed=seed)
    # wrapping bands
    segs = []
    k = 7
    for i in range(k):
        t = (i + 0.5) / k * L
        cx, cy = x0 + dx * t, y0 + dy * t
        segs.append([(cx - nx * w * 0.6 - dx * w * 0.35, cy - ny * w * 0.6 - dy * w * 0.35), (cx + nx * w * 0.6 + dx * w * 0.35, cy + ny * w * 0.6 + dy * w * 0.35)])
    cv.paint(cv.lines(segs, w * 0.09) * m, '#3e2e1e', 0.75)
    cv.paint(cv.lines([[(x + dx * w * 0.1, y + dy * w * 0.1) for x, y in s] for s in segs], w * 0.06) * m, '#e6d4ae', 0.45)
    tar = (cv.noise(w * 0.35, seed + 30) > 0.6).astype(np.float32)
    cv.paint(cv.feather(tar, w * 0.05) * m, '#24180e', 0.55 + 0.4 * burnt)
    return m


def torch_stick(cv, pts, w0, w1, seed=0):
    m = cv.tube(pts, w0, w1)
    cv.shade(m, Tex('#7a4c26', 0.3, 0.5, seed, aniso=(0.3, 5)), r=w0 * 0.45, spec=0.12, tex=0.25, tscale=0.4, tseed=seed + 1, aniso=(4, 0.3))
    return m


@sprite('torch', 6)
def torch():
    cv = Canvas(28, 8, seed=9)
    cv.ground = 7.0
    cv.shadow(14, 7.0, 13, 0.9, 0.42)
    # stick lying, rising slightly towards the head
    m = cv.tube([(1.2, 5.6), (20.5, 4.95)], 1.3, 1.5)
    cv.shade(m, Tex('#7a4c26', 0.3, 0.5, 2, aniso=(5, 0.3)), r=0.5, spec=0.12)
    cv.paint(cv.line([(2, 5.25), (18, 4.7)], 0.2), '#c8925a', 0.4)
    torch_head(cv, [(18.6, 4.6), (26.4, 4.2)], 4.4, seed=3)
    return cv


def flame(cv, cx, base, h, w, seed=0, alpha=1.0):
    rng = np.random.default_rng(seed)
    lay = cv.layer()
    halo = lay.ellipse(cx, base - h * 0.45, w * 0.8, h * 0.5)
    lay.glow(halo, '#ff8a20', w * 0.45, 0.35)
    for k, (col, sc) in enumerate((('#c8260c', 1.0), ('#ff6a12', 0.82), ('#ffb030', 0.62), ('#fff2b0', 0.38))):
        pts = []
        tips = 3 if k < 2 else 1
        top = base - h * sc
        for t in np.linspace(0, 1, 30):
            pass
        # teardrop with flickering tongues
        poly = []
        n = 60
        for i in range(n + 1):
            a = i / n * 2 * math.pi
            # parametric teardrop: y from base up to top
            yy = base - h * sc * (1 - math.cos(a)) / 2 * 1.0
            wid = w * sc * 0.55 * math.sin(a) * (0.35 + 0.65 * (1 - (1 - math.cos(a)) / 2) ** 0.6)
            wob = 0.12 * w * sc * math.sin(a * (3 + k) + seed) * (1 - math.cos(a)) / 2
            poly.append((cx + wid + wob, yy + h * sc * 0.08 * (1 - k * 0.15)))
        m = lay.poly(poly)
        if tips > 1:
            for j in range(tips):
                ox = (j - 1) * w * 0.28 * sc + rng.normal(0, 0.05 * w)
                tong = lay.poly([(cx + ox - w * 0.16 * sc, base - h * sc * 0.45), (cx + ox * 1.4 + rng.normal(0, 0.1 * w), base - h * sc * (1.05 + 0.1 * rng.random())), (cx + ox + w * 0.16 * sc, base - h * sc * 0.45)])
                m = np.maximum(m, tong)
        m = lay.feather(m, w * 0.04 * (1 + k))
        lay.paint(m, col, 0.92)
    cv.over(lay, alpha)


@sprite('torch_lit', 20)
def torch_lit():
    X = 10.0
    cv = Canvas(20, 26, seed=10)
    cv.ground = 24.5
    G = 24.5
    cv.shadow(X, G, 2.6, 0.6, 0.45)
    mound = cv.ellipse(X, G, 2.3, 0.9)
    cv.shade(mound, '#6a5440', r=0.4, tex=0.4, tscale=0.2)
    torch_stick(cv, [(X, G - 0.2), (X + 0.05, 14)], 1.3, 1.5, seed=4)
    torch_head(cv, [(X + 0.05, 16.0), (X + 0.1, 10.0)], 3.8, seed=3, burnt=0.55)
    # embers on the head
    cv.paint(cv.feather((cv.noise(0.3, 44) > 0.68).astype(np.float32), 0.05) * cv.ellipse(X + 0.1, 10.8, 1.8, 0.9), '#ff9a30', 0.9)
    flame(cv, X + 0.1, 11.4, 10.4, 5.4, seed=1)
    return cv


@sprite('boots', 14)
def boots():
    cv = Canvas(22, 16, seed=11)
    cv.ground = 15.0
    G = 15.0
    cv.shadow(10.8, G, 9.8, 1.2, 0.45)

    def boot(ox, oy, dark):
        lay = cv
        shape = spline([(2.4, 1.2), (7.6, 1.0), (7.8, 6.0), (8.6, 9.4), (12.6, 10.6), (15.4, 11.6), (15.6, 13.4), (2.2, 13.4), (2.0, 7.0)], n=10, closed=True)
        shape = [(x + ox, y + oy) for x, y in shape]
        m = lay.poly(shape)
        base = mix('#8a5228', '#3a2210', dark)
        hi = mix('#b8783e', '#5a3818', dark)
        lay.shade(m, Tex(Lin(ox, oy, ox + 14, oy + 13, hi, base, mix(base, '#000000', 0.4)), 0.15, 0.4, 3), r=1.2, spec=0.35, shin=16, tex=0.15, tscale=0.3)
        # sole and heel
        sole = lay.poly([(ox + 1.9, oy + 13.0), (ox + 15.7, oy + 13.0), (ox + 15.5, oy + 14.0), (ox + 2.0, oy + 14.0)])
        lay.shade(sole, mix('#2c2018', '#100a06', dark), r=0.3, spec=0.15)
        heel = lay.rect(ox + 1.9, oy + 12.4, ox + 5.6, oy + 14.0)
        lay.shade(heel, mix('#3a2a1e', '#100a06', dark), r=0.3, spec=0.15)
        # collar opening and pull strap
        lay.shade(lay.ellipse(ox + 5.0, oy + 1.25, 2.7, 0.65), '#1a0e06', r=0.2, rim=0, spec=0)
        lay.paint(lay.line([(ox + 2.3, oy + 1.4), (ox + 7.7, oy + 1.2)], 0.4, caps=False), hi, 0.8)
        # laces criss-cross on the front of the shaft
        segs = []
        for i in range(6):
            y = oy + 2.4 + i * 1.25
            x = ox + 7.5 + max(0, (i - 3)) * 0.35
            segs.append([(x - 1.6, y), (x + 0.2, y + 1.2)])
            segs.append([(x - 1.6, y + 1.2), (x + 0.2, y)])
        lm = lay.lines(segs, 0.28) * m
        lay.paint(lm, mix('#e2c9a0', '#6a5a44', dark), 1.0)
        for i in range(7):
            y = oy + 2.4 + i * 1.25
            lay.shade(lay.circle(ox + 7.6 + max(0, (i - 3)) * 0.35, y, 0.22) * m, '#c8b070', r=0.1, spec=0.6)
        # toe cap seam and stitching
        lay.paint(lay.line(bez((ox + 11.0, oy + 10.4), (ox + 11.6, oy + 12.0), (ox + 11.2, oy + 13.0), n=12), 0.15) * m, '#2a1608', 0.7)
        st = [[(x, oy + 12.6), (x + 0.4, oy + 12.6)] for x in np.arange(ox + 2.6, ox + 15, 0.8)]
        lay.paint(lay.lines(st, 0.1) * m, '#e0c090', 0.6)
        lay.hl(ox + 3.6, oy + 5.5, 0.6, 3.0, 0.25)
        lay.hl(ox + 13.0, oy + 11.2, 1.4, 0.4, 0.3, rot=0.25)

    boot(4.4, 0.2 - 1.0 + 1.0, 0.55)
    boot(0.0, 1.0, 0.0)
    return cv


@sprite('kit', 11)
def kit():
    cv = Canvas(19, 13, seed=12)
    cv.ground = 12.0
    G = 12.0
    cv.shadow(9.5, G, 8.6, 1.0, 0.45)
    canvas_col = lambda a, b: Tex(Lin(0, 2, 0, 12, a, b), 0.12, 0.12, 5)
    # carrying handle
    h = cv.line(bez((6.2, 3.4), (6.4, 0.2), (12.6, 0.2), (12.8, 3.4), n=30), 0.75)
    cv.shade(h, '#4a5e2c', r=0.3, spec=0.1)
    body = cv.rrect(1.4, 2.8, 17.6, G, 1.6)
    cv.shade(body, canvas_col('#71904a', '#3e5226'), r=1.3, spec=0.08, tex=0.1, tscale=0.15, tseed=3)
    # vertical seams/pockets
    cv.paint(cv.lines([[(3.4, 7.5), (3.4, 11.6)], [(15.6, 7.5), (15.6, 11.6)]], 0.15), '#2a3814', 0.6)
    flap = cv.poly(spline([(1.3, 3.2), (17.7, 3.2), (17.4, 6.6), (16, 8.0), (3.0, 8.0), (1.6, 6.6)], n=8, closed=True))
    cv.paint(cv.feather(cv.rect(2, 7.8, 17, 8.7), 0.3) * body, (0, 0, 0), 0.4)
    cv.shade(flap, canvas_col('#7e9e54', '#56703a'), r=0.8, spec=0.08, tex=0.1, tscale=0.15, tseed=4)
    st = [[(x, 7.6), (x + 0.45, 7.6)] for x in np.arange(3.0, 16.2, 0.8)]
    cv.paint(cv.lines(st, 0.1), '#c8d4a0', 0.5)
    # straps + buckles
    for sx in (4.6, 14.4):
        st_ = cv.rect(sx - 0.7, 2.9, sx + 0.7, 11.2)
        cv.shade(st_, '#3a4a20', r=0.3, spec=0.1)
        b = cv.rrect(sx - 0.95, 7.0, sx + 0.95, 8.6, 0.25) * (1 - cv.rect(sx - 0.5, 7.4, sx + 0.5, 8.2))
        cv.shade(b, '#c9b070', r=0.15, spec=0.7)
    # red cross on white disc
    disc = cv.circle(9.5, 5.4, 2.25)
    cv.shade(disc, '#f6f2e8', r=0.4, spec=0.2, rim=0.15)
    cross = np.maximum(cv.rect(8.85, 3.85, 10.15, 6.95), cv.rect(7.95, 4.75, 11.05, 6.05))
    cv.shade(cross, '#d0201a', r=0.25, spec=0.2, rim=0.1)
    return cv


@sprite('tonic', 9)
def tonic():
    cv = Canvas(8, 11, seed=13)
    cv.ground = 10.0
    G = 10.0
    cv.shadow(4, G, 3.0, 0.6, 0.45)
    out = spline([(3.25, 1.2), (3.2, 2.6), (2.1, 3.7), (1.8, 4.6), (1.8, 9.6), (4, 10.0), (6.2, 9.6), (6.2, 4.6), (5.9, 3.7), (4.8, 2.6), (4.75, 1.2)], n=8)
    m = cv.poly(out)
    cv.shade(m, Lin(1.8, 0, 6.2, 0, '#7a3a10', '#4a1e06', '#2a0e02'), r=0.9, spec=0.6, shin=30, rim=0.2)
    # label
    lab = cv.rect(1.8, 5.4, 6.2, 8.4) * m
    cv.shade(lab, Lin(1.8, 0, 6.2, 0, '#f4e6c4', '#cfbf98', '#9a8c6a'), r=0.5, spec=0.1, rim=0.1, bulge=0.6)
    cv.paint(cv.rect(1.8, 6.4, 6.2, 7.0) * m, '#2a6a8a', 0.9)
    cv.paint(cv.rect(1.8, 7.5, 6.2, 7.75) * m, '#a8442a', 0.8)
    # cap
    cap = cv.rrect(3.0, 0.2, 5.0, 1.9, 0.25)
    cv.shade(cap, '#c8b080', r=0.3, spec=0.6, shin=20)
    cv.paint(cv.lines([[(x, 0.4), (x, 1.7)] for x in np.arange(3.3, 5.0, 0.35)], 0.08), '#6a5a3a', 0.6)
    # glass glints
    cv.paint(cv.line([(2.6, 4.6), (2.6, 9.0)], 0.35) * m * (1 - lab), '#ffffff', 0.5)
    cv.hl(2.6, 4.2, 0.35, 0.5, 0.7)
    cv.paint(cv.line([(3.6, 2.1), (3.6, 3.0)], 0.2), '#ffffff', 0.45)
    return cv


@sprite('serum', 8)
def serum():
    cv = Canvas(19, 10, seed=14)
    cv.ground = 9.0
    G = 9.0
    cv.shadow(9, G, 8.5, 0.7, 0.4)
    # vial (upright, behind)
    glass = cv.rrect(1.0, 2.4, 4.4, G, 0.7)
    liquid = cv.rrect(1.15, 4.5, 4.25, G - 0.15, 0.6)
    cv.shade(glass, '#c8dce4', r=0.6, spec=0.3, rim=0.3, alpha=0.65)
    cv.shade(liquid, Lin(0, 4.5, 0, 9, '#f0d880', '#c89a2a'), r=0.6, spec=0.5, alpha=0.9)
    cv.paint(cv.line([(1.25, 4.5), (4.15, 4.5)], 0.18, caps=False), '#fff4c0', 0.9)
    lab = cv.rect(1.0, 5.6, 4.4, 7.6)
    cv.shade(lab, '#f6f4ee', r=0.4, rim=0.1, bulge=0.6)
    cv.paint(cv.rect(1.0, 6.3, 4.4, 6.8), '#c22a22', 0.9)
    cv.shade(cv.rect(1.3, 1.6, 4.1, 2.8), '#aeb4ba', r=0.25, spec=0.7)
    cv.shade(cv.rrect(1.6, 0.3, 3.8, 1.9, 0.35), '#b0261c', r=0.35, spec=0.4)
    cv.paint(cv.line([(1.7, 3.0), (1.7, 8.4)], 0.28), '#ffffff', 0.55)
    # syringe lying in front, diagonally
    a = -0.08
    def R(pts):
        return rot_pts(pts, a, 10, 7.2)
    cv.shade(cv.poly(R([(4.2, 6.5), (5.0, 6.5), (5.0, 8.4), (4.2, 8.4)])), '#e8e8e8', r=0.2, spec=0.3)
    cv.shade(cv.poly(R([(5.0, 7.15), (8.0, 7.15), (8.0, 7.75), (5.0, 7.75)])), '#d8d8d8', r=0.2, spec=0.3)
    barrel = cv.poly(R([(7.6, 6.45), (14.6, 6.45), (14.6, 8.45), (7.6, 8.45)]))
    cv.shade(barrel, '#e4f0f4', r=0.5, spec=0.5, rim=0.25, alpha=0.75)
    cv.paint(cv.poly(R([(11.2, 6.75), (14.4, 6.75), (14.4, 8.15), (11.2, 8.15)])), '#f2d070', 0.7)
    cv.shade(cv.poly(R([(10.9, 6.6), (11.4, 6.6), (11.4, 8.3), (10.9, 8.3)])), '#2a2a2a', r=0.15, spec=0.3)
    cv.paint(cv.lines([R([(x, 6.5), (x, 7.0 if i % 2 else 7.3)]) for i, x in enumerate(np.arange(8.2, 14.4, 0.55))], 0.08), '#2a4a9a', 0.85)
    cv.shade(cv.poly(R([(7.4, 6.2), (7.75, 6.2), (7.75, 8.7), (7.4, 8.7)])), '#f0f0f0', r=0.15, spec=0.4)
    cv.shade(cv.poly(R([(14.6, 7.05), (15.6, 7.05), (15.6, 7.85), (14.6, 7.85)])), '#d0d4d8', r=0.15, spec=0.6)
    cv.paint(cv.line(R([(15.6, 7.45), (18.4, 7.45)]), 0.16, caps=False), '#c8ccd0', 1.0)
    cv.paint(cv.line(R([(8.0, 6.75), (14.3, 6.75)]), 0.15), '#ffffff', 0.7)
    return cv


@sprite('aspirin', 4)
def aspirin():
    cv = Canvas(14, 6, seed=15)
    cv.ground = 5.0
    G = 5.0
    cv.shadow(6.5, G, 6.0, 0.6, 0.45)
    side = np.maximum(cv.rect(1.0, 2.0, 10.0, 3.7), cv.ellipse(5.5, 3.7, 4.5, 1.15))
    cv.shade(side, Lin(1, 0, 10, 0, '#e8eaec', '#a4a8ac', '#5a5e62'), r=0.3, spec=0.5, rim=0.15, bulge=0.4)
    cv.paint(cv.rect(1.0, 2.6, 10.0, 3.1) * side, '#b02018', 0.85)
    top = cv.ellipse(5.5, 2.0, 4.5, 1.15)
    cv.shade(top, Lin(2, 1, 9, 3, '#ffffff', '#c8ccd0'), r=0.25, spec=0.4, rim=0.1)
    cv.shade(cv.ellipse(5.5, 2.0, 3.3, 0.8), '#c8261e', r=0.25, spec=0.4, rim=0.1)
    cv.paint(np.maximum(cv.rect(5.25, 1.4, 5.75, 2.6), cv.rect(4.6, 1.85, 6.4, 2.15)), '#ffffff', 0.95)
    for tx, ty in ((11.2, 4.3), (12.6, 3.9)):
        cv.shade(cv.ellipse(tx, ty, 0.85, 0.42), '#f8f8f4', r=0.2, spec=0.3)
        cv.paint(cv.line([(tx - 0.5, ty), (tx + 0.5, ty)], 0.07), '#9a9a92', 0.6)
    return cv


@sprite('bandage', 5)
def bandage():
    cv = Canvas(15, 7, seed=16)
    cv.ground = 6.0
    G = 6.0
    cv.shadow(7, G, 6.5, 0.7, 0.4)
    gauze = Tex('#f4f0e6', 0.12, 0.08, 3)
    # loose end lying on the ground
    tail = cv.poly(bez((5.5, 5.0), (8, 5.6), (10.5, 5.2), (13.8, 5.7), n=20) + bez((13.8, 6.0), (10.5, 5.9), (8, 6.0), (5.5, 6.0), n=20))
    cv.shade(tail, gauze, r=0.25, spec=0.1, rim=0.2)
    body = np.maximum(cv.rect(2.4, 1.0, 6.6, 6.0), cv.ellipse(6.6, 3.5, 1.0, 2.5))
    cv.shade(body, Lin(0, 1, 0, 6, '#ffffff', '#e2dccc', '#b0a890'), r=0.6, spec=0.15, rim=0.2, bulge=0.6)
    end = cv.ellipse(2.4, 3.5, 1.1, 2.5)
    cv.shade(end, '#efe9dc', r=0.4, spec=0.1, rim=0.25)
    sp = []
    for k in range(4):
        rr = 0.25 + k * 0.22
        sp.append(ell_pts(2.4, 3.6, rr * 1.1 / 2.5 * 2.2, rr * 2.4 / 2.5 * 2.2 / 2.2 * 1.0, n=40))
    cv.paint(cv.lines(sp, 0.1) * end, '#a8a090', 0.7)
    # gauze weave
    weave = (np.abs(np.sin(cv.noise(0.08, 9) * 3)) > 0.95).astype(np.float32)
    cv.paint(cv.lines([[(x, 1.0), (x, 6.0)] for x in np.arange(3.0, 6.6, 0.45)], 0.06) * body, '#b8b0a0', 0.4)
    return cv


@sprite('bananas', 9)
def bananas():
    cv = Canvas(17, 11, seed=17)
    cv.ground = 10.0
    G = 10.0
    cv.shadow(8.5, G, 7.6, 0.9, 0.45)
    fingers = [
        ((2.4, 3.6), (6, 0.6), (12, 0.2), (15.2, 2.4)),
        ((2.4, 4.0), (6.5, 2.4), (12.5, 2.8), (15.8, 5.2)),
        ((2.4, 4.4), (6.2, 4.6), (11.8, 6.0), (14.8, 8.4)),
        ((2.4, 4.8), (5.4, 6.6), (9.5, 9.0), (12.4, 9.8)),
    ]
    for i, f in enumerate(fingers):
        path = bez(*f, n=40)
        ws = [2.7 * (0.45 + 0.55 * math.sin(math.pi * min(1, 0.12 + t * 0.95)) ** 0.5) for t in np.linspace(0, 1, 40)]
        m = cv.tube(path, 0, widths=ws)
        col = Lin(2, 0, 16, 0, (0.0, '#8fae3a'), (0.22, '#f0d23a'), (0.88, '#ffe050'), (1.0, '#7a6a20'))
        cv.shade(m, col, r=0.75, spec=0.3, shin=14, rim=0.35, tex=0.12, tscale=0.5, tseed=i)
        cv.paint(cv.line(path[4:-3], 0.09) * m, '#a88a20', 0.45)
        tip = cv.circle(*path[-1], 0.55)
        cv.shade(tip, '#3a2a12', r=0.2, rim=0)
        sx, sy = path[24]
        cv.paint(cv.ellipse(sx, sy, 0.22, 0.14) * m, '#5a3a10', 0.5)
    crown = cv.poly(spline([(0.3, 3.0), (2.6, 2.7), (3.4, 4.2), (2.6, 5.6), (0.3, 5.0)], n=6, closed=True))
    cv.shade(crown, '#6a7a2a', r=0.5, spec=0.15)
    cv.shade(cv.ellipse(0.7, 4.0, 0.55, 1.05), '#4a3a18', r=0.3)
    return cv


@sprite('rope', 9)
def rope():
    cv = Canvas(20, 11, seed=18)
    cv.ground = 10.0
    G = 10.0
    cv.shadow(9.5, G, 8.8, 1.2, 0.45)
    # loose end trailing out
    rope_path(cv, bez((13.5, 8.6), (16.5, 9.6), (18.5, 8.8), (19.4, 9.2), n=24), 1.15)
    for i in range(5):
        cy = 7.6 - i * 1.0
        pts = ell_pts(9.0, cy, 7.4 - i * 0.15, 2.4, n=72)
        rope_path(cv, pts, 1.3, '#c8a86c' if i % 2 else '#bc9c62')
    hole = cv.ellipse(9.0, 3.6, 5.6, 1.35)
    cv.paint(cv.feather(hole, 0.3), Lin(0, 2.4, 0, 4.8, '#1c140a', '#5a4428'), 0.92)
    # inner coils glimpsed
    rope_path(cv, ell_pts(9.0, 4.1, 4.6, 1.0, n=60, a0=0.15, a1=math.pi - 0.15), 1.0, '#9c7e4c', '#3a2a14')
    return cv


def draw_helmet(cv, cx, base, s=1.0, col='#cdbb8a', seed=0):
    """Pith helmet, 3/4 side view; base = bottom of the brim, ~16*s wide, ~9*s tall."""
    def T(pts):
        return [(cx + x * s, base + y * s) for x, y in pts]
    # brim underside (back part) then dome then brim front
    brim = cv.poly(T(ell_pts(0, -1.6, 8.0, 1.85, n=80)))
    cv.shade(brim, Lin(0, base - 3 * s, 0, base, mix(col, '#ffffff', 0.1), mix(col, '#3a3020', 0.45)), r=0.6 * s, spec=0.12, tex=0.12, tscale=0.3 * s, tseed=seed)
    inner = cv.poly(T(ell_pts(0, -2.2, 5.6, 1.2, n=60)))
    cv.paint(cv.feather(inner, 0.2 * s), '#3a2e1a', 0.85)
    dome = cv.poly(T([(-5.4, -2.2)] + bez((-5.4, -2.2), (-5.6, -8.6), (5.6, -8.6), (5.4, -2.2), n=40) + ell_pts(0, -2.2, 5.4, 1.15, n=30, a0=0, a1=math.pi)))
    cv.shade(dome, Rad(cx - 2.2 * s, base - 7 * s, 8 * s, mix(col, '#ffffff', 0.35), col, mix(col, '#4a3c22', 0.5)), r=1.6 * s, spec=0.25, shin=10, tex=0.12, tscale=0.3 * s, tseed=seed + 1)
    # seams
    segs = [T(bez((-2.6, -2.4), (-2.2, -6.5), (-0.6, -7.6), n=16)), T(bez((2.6, -2.4), (2.2, -6.5), (0.6, -7.6), n=16)), T([(0, -1.1), (0, -7.7)])]
    cv.paint(cv.lines(segs, 0.12 * s) * dome, mix(col, '#3a2e1a', 0.6), 0.5)
    band = cv.poly(T(ell_pts(0, -2.6, 5.45, 1.2, n=40, a0=0, a1=math.pi) + ell_pts(0, -3.6, 5.5, 1.2, n=40, a0=math.pi, a1=0)))
    cv.shade(band * dome, mix(col, '#5a4a2a', 0.55), r=0.4 * s, spec=0.1)
    knob = cv.ellipse(cx, base - 7.75 * s, 0.75 * s, 0.4 * s)
    cv.shade(knob, mix(col, '#ffffff', 0.15), r=0.25 * s, spec=0.3)


@sprite('helmet', 9)
def helmet():
    cv = Canvas(19, 11, seed=19)
    cv.ground = 10.0
    cv.shadow(9.5, 10.0, 8.6, 1.0, 0.45)
    draw_helmet(cv, 9.5, 9.9, 1.0)
    return cv


@sprite('hammer', 10)
def hammer():
    cv = Canvas(25, 12, seed=20)
    cv.ground = 11.0
    G = 11.0
    cv.shadow(12, G, 11.5, 1.0, 0.45)
    handle = cv.tube([(1.2, 8.6), (18.5, 7.0)], 1.5, 1.9)
    cv.shade(handle, Tex(Lin(0, 6, 0, 10, '#c89a62', '#8a5e34', '#5a3a1e'), 0.25, 0.8, 3, aniso=(6, 0.4)), r=0.6, spec=0.2)
    cv.paint(cv.line([(2, 8.1), (17.5, 6.6)], 0.22), '#ecc894', 0.4)
    head = cv.poly([(16.0, 2.2), (21.6, 1.6), (22.2, 2.4), (22.2, 9.8), (21.6, 10.8), (16.0, 10.8), (15.4, 9.8), (15.4, 3.0)])
    cv.shade(head, Lin(15, 0, 22, 0, '#8a8e92', '#5a5e62', '#2e3034'), r=0.9, spec=0.5, shin=20, rim=0.25, tex=0.06, tscale=0.6, tseed=5)
    cv.paint(cv.poly([(15.4, 3.0), (16.0, 2.2), (21.6, 1.6), (22.2, 2.4)]), '#c4c8cc', 0.7)
    cv.paint(cv.feather((cv.noise(0.6, 17) > 0.82).astype(np.float32), 0.08) * head, '#7a4220', 0.4)
    wedge = cv.poly([(17.6, 6.8), (19.8, 6.6), (19.6, 7.4), (17.6, 7.6)])
    cv.paint(wedge, '#3a2a1a', 0.6)
    return cv


def draw_bucket(cv, cx, base, full):
    G = base
    rx, top_y, bot_y = 6.2, 3.0, G - 1.0
    body = cv.poly(ell_pts(cx, top_y, rx, 1.9, n=40, a0=math.pi, a1=2 * math.pi) + ell_pts(cx, bot_y, rx * 0.82, 1.3, n=40, a0=0, a1=math.pi))
    wood = Tex(Lin(cx - rx, 0, cx + rx, 0, '#c99258', '#9a6534', '#5a3818'), 0.22, 1.0, 5, aniso=(0.25, 8))
    cv.shade(body, wood, r=1.6, spec=0.12, rim=0.2, bulge=0.8)
    # staves
    segs = []
    for f in np.linspace(-0.85, 0.85, 8):
        segs.append([(cx + f * rx, top_y + 1.9 * math.sqrt(1 - f * f) * 0.95), (cx + f * rx * 0.82, bot_y + 1.3 * math.sqrt(1 - f * f) * 0.95)])
    cv.paint(cv.lines(segs, 0.14) * body, '#3a2410', 0.6)
    cv.paint(cv.lines([[(x + 0.18, y) for x, y in s_] for s_ in segs], 0.1) * body, '#e8b880', 0.3)
    # iron hoops
    for t in (0.18, 0.78):
        y = top_y + (bot_y - top_y) * t
        r_ = rx + (rx * 0.82 - rx) * t
        ry_ = 1.9 + (1.3 - 1.9) * t
        hoop = cv.tube(ell_pts(cx, y, r_ + 0.05, ry_, n=40, a0=0.02, a1=math.pi - 0.02), 0.85)
        cv.shade(hoop, '#4a4642', r=0.3, spec=0.5, shin=20)
        for hx in (-0.55, 0.0, 0.55):
            cv.shade(cv.circle(cx + hx * r_, y + ry_ * math.sqrt(1 - hx * hx), 0.2), '#8a8580', r=0.1, spec=0.6)
    rim = cv.ellipse(cx, top_y, rx, 1.9)
    cv.shade(rim, '#b07a44', r=0.3, spec=0.1, rim=0.1)
    inner = cv.ellipse(cx, top_y + 0.05, rx - 0.6, 1.45)
    if full:
        cv.paint(inner, Lin(0, top_y - 1.4, 0, top_y + 1.4, '#2a160a', '#3a2412'))
        water = cv.ellipse(cx, top_y + 0.25, rx - 0.65, 1.25)
        cv.paint(water, Lin(cx - rx, top_y - 1, cx + rx, top_y + 1, '#7fd0e0', '#2a8aa8', '#145a7a'))
        cv.paint(cv.feather(cv.ellipse(cx - 1.8, top_y - 0.2, 2.2, 0.35, rot=-0.08), 0.15) * water, '#ffffff', 0.75)
        cv.paint(cv.feather(cv.ellipse(cx + 2.4, top_y + 0.6, 1.2, 0.2), 0.1) * water, '#e8fcff', 0.5)
        cv.paint(cv.lines([ell_pts(cx + 0.6, top_y + 0.4, 1.6 + k * 1.1, 0.35 + k * 0.25, n=30) for k in range(2)], 0.08) * water, '#c8f4ff', 0.35)
        # drips down the side
        for dx_, l in ((-3.6, 2.0), (2.6, 3.0)):
            d = cv.tube([(cx + dx_, top_y + 1.5), (cx + dx_ * 0.97, top_y + 1.5 + l)], 0.35, 0.5)
            cv.shade(d, '#6ab8d0', r=0.15, spec=0.9, shin=30, alpha=0.6)
    else:
        cv.paint(inner, Lin(0, top_y - 1.4, 0, top_y + 1.4, '#1a0e06', '#6a4220'))
    # bail handle
    bail = cv.line(bez((cx - rx + 0.2, top_y + 0.6), (cx - rx * 0.9, top_y - 6.2), (cx + rx * 0.9, top_y - 6.2), (cx + rx - 0.2, top_y + 0.6), n=40), 0.45)
    cv.shade(bail, '#555', r=0.15, spec=0.6)
    for sx in (-1, 1):
        cv.shade(cv.circle(cx + sx * (rx - 0.2), top_y + 0.8, 0.45), '#444', r=0.2, spec=0.5)


@sprite('bucket', 13)
def bucket():
    cv = Canvas(16, 15, seed=21)
    cv.ground = 14.4
    cv.shadow(8, 14.4, 6.6, 1.0, 0.45)
    draw_bucket(cv, 8, 14.4, False)
    return cv


@sprite('bucket_full', 13)
def bucket_full():
    cv = Canvas(16, 15, seed=21)
    cv.ground = 14.4
    cv.shadow(8, 14.4, 6.6, 1.0, 0.45)
    draw_bucket(cv, 8, 14.4, True)
    return cv


@sprite('sabre', 6)
def sabre():
    cv = Canvas(40, 8, seed=22)
    cv.ground = 7.0
    G = 7.0
    cv.shadow(20, G, 18.5, 0.9, 0.4)
    spine = bez((10.5, 4.0), (20, 3.6), (30, 2.6), (38.6, 0.8), n=60)
    edge = bez((38.6, 0.8), (31, 4.2), (20, 5.6), (10.5, 5.6), n=60)
    blade = cv.poly(spine + edge)
    cv.shade(blade, Lin(0, 1, 0, 6, '#ffffff', '#c4ccd2', '#7a848c'), r=0.35, spec=0.6, shin=30, rim=0.1, tex=0.06, tscale=2, aniso=(8, 0.3))
    fuller = cv.line(bez((12, 4.45), (21, 4.1), (29, 3.2), (34, 2.2), n=40), 0.3)
    cv.paint(fuller, '#5a646c', 0.6)
    cv.paint(cv.line(bez((12, 4.8), (21, 4.45), (29, 3.55), (34, 2.6), n=40), 0.15), '#ffffff', 0.6)
    # brass guard + knuckle bow
    bow = cv.line(bez((10.6, 5.6), (8.5, 7.4), (3.4, 7.2), (1.4, 5.2), n=40), 0.55)
    cv.shade(bow, '#d4a640', r=0.25, spec=0.7, shin=20)
    guard = cv.poly([(10.0, 2.6), (11.2, 2.8), (11.2, 6.4), (10.0, 6.4)])
    cv.shade(guard, '#d4a640', r=0.3, spec=0.7, shin=20)
    grip = cv.tube([(2.4, 4.7), (10.0, 4.6)], 1.55, 1.75)
    cv.shade(grip, '#3a2014', r=0.5, spec=0.25)
    cv.paint(cv.lines([[(x, 3.9), (x + 0.5, 5.4)] for x in np.arange(2.8, 9.8, 0.5)], 0.12) * grip, '#c8a050', 0.7)
    pom = cv.ellipse(1.6, 4.7, 1.0, 1.1)
    cv.shade(pom, '#d4a640', r=0.4, spec=0.8, shin=20)
    return cv


@sprite('jerrican', 16)
def jerrican():
    cv = Canvas(16, 18, seed=23)
    cv.ground = 17.0
    G = 17.0
    cv.shadow(8, G, 7.6, 1.0, 0.5)
    paint_ = lambda a, b: Tex(Lin(0, 2, 0, 17, a, b), 0.1, 0.4, 4)
    front = cv.rrect(1.0, 4.4, 10.6, G, 0.5)
    side = cv.poly([(10.4, 4.4), (14.2, 2.6), (14.2, 15.2), (10.4, G)])
    top = cv.poly([(1.1, 4.5), (4.9, 2.6), (14.2, 2.6), (10.5, 4.5)])
    cv.shade(side, paint_('#4a5426', '#262c12'), r=0.5, spec=0.15, rim=0.15)
    cv.shade(top, '#7a8644', r=0.4, spec=0.2, rim=0.1)
    cv.shade(front, paint_('#66743a', '#3c4620'), r=0.6, spec=0.15, rim=0.15)
    # embossed X on front (recessed panels with raised ridges)
    xm = np.maximum(cv.line([(2.3, 6.0), (9.3, 15.6)], 1.2), cv.line([(9.3, 6.0), (2.3, 15.6)], 1.2))
    xm = xm * cv.rect(1.8, 5.4, 9.8, 16.2)
    cv.shade(xm, '#6e7e40', r=0.4, spec=0.3, rim=0.2)
    cv.paint(cv.line([(1.5, 10.8), (10.1, 10.8)], 0.3, caps=False), '#2a3014', 0.6)
    # side ridges
    for t in (0.33, 0.66):
        cv.paint(cv.line([(10.4 + 3.8 * t, 4.4 - 1.8 * t + 0.6), (10.4 + 3.8 * t, G - 1.8 * t - 0.6)], 0.25), '#1a2008', 0.4)
    # three handles
    for i, hx in enumerate((5.0, 7.4, 9.8)):
        h = cv.line(bez((hx - 0.8, 3.6 - i * 0.05), (hx - 0.6, 0.9), (hx + 0.6, 0.9), (hx + 0.8, 3.4), n=20), 0.6)
        cv.shade(h, '#59652e', r=0.25, spec=0.3)
    # spout cap
    cap = cv.rrect(1.6, 2.3, 3.6, 4.4, 0.4)
    cv.shade(cap, '#4a5426', r=0.4, spec=0.3)
    cv.shade(cv.rect(1.9, 1.7, 3.3, 2.5), '#8a8a80', r=0.2, spec=0.6)
    # chips and scratches
    chips = (cv.noise(0.5, 31) > 0.93).astype(np.float32) * np.maximum(np.maximum(front, side), top)
    cv.paint(cv.feather(chips, 0.04), '#8a8a7e', 0.5)
    cv.paint(cv.line([(1.1, 4.5), (10.5, 4.5), (14.2, 2.6)], 0.15, caps=False), '#c8d08a', 0.6)
    return cv


@sprite('button', 14)
def button():
    cv = Canvas(15, 16, seed=24)
    cv.ground = 15.0
    plate = cv.rrect(0.5, 1.0, 14.5, 15.0, 1.0)
    cv.paint(cv.feather(cv.rrect(0.9, 1.6, 14.9, 15.0, 1.0), 0.3), (0, 0, 0), 0.45)
    cv.shade(plate, Tex(Lin(0, 1, 15, 15, '#b4b8bc', '#7c8084', '#4c5054'), 0.1, 3.0, 8, aniso=(6, 0.3)), r=0.5, spec=0.35, rim=0.15)
    for x, y in ((1.8, 2.3), (13.2, 2.3), (1.8, 13.7), (13.2, 13.7)):
        cv.shade(cv.circle(x, y, 0.5), '#c8ccd0', r=0.2, spec=0.7)
    # hazard ring
    ring = cv.circle(7.5, 8.0, 5.4)
    cv.shade(ring, '#2a2a2a', r=0.5, spec=0.3)
    st = cv.circle(7.5, 8.0, 5.0) * (1 - cv.circle(7.5, 8.0, 4.1))
    ang = np.arctan2(np.arange(cv.H)[:, None] / cv.u - 8.0, np.arange(cv.W)[None, :] / cv.u - 7.5)
    stripes = ((np.floor((ang + math.pi) / (math.pi / 8)) % 2) == 0).astype(np.float32)
    cv.paint(st * stripes, '#f0c020', 0.95)
    bez_ = cv.circle(7.5, 8.0, 3.95)
    cv.shade(bez_, '#9a9ea2', r=0.4, spec=0.6)
    cv.paint(cv.feather(cv.circle(7.6, 8.2, 3.3), 0.25), (0, 0, 0), 0.6)
    dome = cv.circle(7.5, 8.0, 3.2)
    cv.shade(dome, Rad(6.4, 6.8, 4.2, '#ff6a5a', '#e01818', '#7a0606'), r=1.4, spec=0.8, shin=40, rim=0.2)
    cv.hl(6.3, 6.6, 1.2, 0.7, 0.75, rot=-0.6)
    return cv


@sprite('bottle', 9)
def bottle():
    cv = Canvas(23, 11, seed=25)
    cv.ground = 10.0
    G = 10.0
    cv.shadow(10.5, G, 10, 1.0, 0.4)
    outline = spline([(1.2, 2.0), (12.8, 1.6), (15.2, 3.4), (18.4, 3.7), (19.6, 3.6), (19.6, 6.3), (18.4, 6.2), (15.2, 6.6), (12.8, 9.6), (1.2, 9.6), (0.5, 5.8)], n=10, closed=True)
    glass = cv.poly(outline)
    # paper scroll inside (behind glass)
    paper = cv.tube([(3.0, 5.9), (13.2, 5.5)], 3.0)
    cv.shade(paper, Lin(0, 4, 0, 7.6, '#ffffff', '#f0e2b8', '#c0a870'), r=0.8, spec=0.1, rim=0.2)
    cv.paint(cv.lines([[(x, 4.5), (x + 0.15, 7.3)] for x in (5.5, 9.8, 12.0)], 0.12) * paper, '#9a8458', 0.6)
    cv.paint(cv.line([(7.6, 4.3), (7.8, 7.4)], 0.35) * paper, '#a03020', 0.9)
    cv.shade(glass, Lin(0, 1.6, 0, 9.6, '#7ac8a0', '#2a7a5a', '#0c3a28'), r=1.4, spec=0.0, rim=0.5, alpha=0.38)
    cv.paint(glass * cv.rect(0, 7.6, 30, 10), '#0a3020', 0.3)
    cork = cv.rrect(19.2, 3.8, 21.6, 6.1, 0.35)
    cv.shade(cork, Tex('#c09060', 0.35, 0.2, 3), r=0.4, spec=0.1)
    lip = cv.rrect(18.6, 3.2, 19.8, 6.7, 0.4)
    cv.shade(lip, '#3a9a70', r=0.3, spec=0.6, alpha=0.8)
    # strong glass highlights
    cv.paint(cv.line(bez((2.0, 3.0), (7, 2.6), (12, 2.5), n=12), 0.45), '#ffffff', 0.75)
    cv.paint(cv.line([(15.6, 4.2), (18.0, 4.35)], 0.25), '#ffffff', 0.6)
    cv.paint(cv.line([(2.5, 8.6), (11.5, 8.7)], 0.2), '#bff0d0', 0.35)
    cv.hl(1.6, 5.8, 0.4, 2.2, 0.4)
    return cv


@sprite('gun', 8)
def gun():
    cv = Canvas(40, 10, seed=26)
    cv.ground = 9.0
    G = 9.0
    cv.shadow(19, G, 18, 0.9, 0.45)
    rust = lambda a, b: Tex(Lin(0, 1, 0, 9, a, b), 0.35, 0.3, 3)
    metal_m = []
    # stock
    stock = cv.poly(spline([(1.0, 3.2), (9.8, 2.6), (11.0, 2.6), (11.2, 5.4), (9.0, 6.0), (1.2, 7.8), (0.6, 5.4)], n=6, closed=True))
    cv.shade(stock, Tex(Lin(0, 2, 0, 8, '#8a5430', '#5a3018', '#341a0a'), 0.3, 0.9, 5, aniso=(6, 0.4)), r=0.8, spec=0.2)
    # pistol grip + front grip (wood)
    pg = cv.poly([(13.0, 4.4), (15.4, 4.4), (15.0, 7.6), (13.3, 8.2), (12.4, 7.8)])
    cv.shade(pg, Tex('#6a3a1c', 0.3, 0.6, 6), r=0.5, spec=0.2)
    fg = cv.poly([(22.0, 4.4), (24.2, 4.4), (24.0, 7.4), (22.6, 7.8), (21.8, 7.2)])
    cv.shade(fg, Tex('#6a3a1c', 0.3, 0.6, 7), r=0.5, spec=0.2)
    # receiver
    rec = cv.poly([(10.8, 2.3), (21.0, 2.3), (21.5, 3.0), (21.5, 4.8), (10.8, 4.8)])
    cv.shade(rec, rust('#5a4a40', '#2a201a'), r=0.5, spec=0.35, tex=0.2, tscale=0.3)
    # magazine
    mag = cv.poly([(16.2, 4.6), (18.2, 4.6), (18.6, 8.6), (16.6, 8.6)])
    cv.shade(mag, rust('#4a3e36', '#241a14'), r=0.4, spec=0.3)
    cv.paint(cv.lines([[(16.5, y), (18.4, y)] for y in (5.6, 6.6, 7.6)], 0.12) * mag, '#120c08', 0.5)
    # trigger guard
    tg = cv.line(bez((14.6, 4.7), (14.8, 6.6), (17.0, 6.4), (16.6, 4.7), n=20), 0.3)
    cv.shade(tg, '#3a302a', r=0.1, spec=0.3)
    # barrel with cooling fins + compensator
    bar = cv.rect(21.4, 2.7, 33.5, 4.0)
    cv.shade(bar, rust('#5a4a40', '#2a201a'), r=0.35, spec=0.4)
    cv.paint(cv.lines([[(x, 2.6), (x, 4.1)] for x in np.arange(22.0, 27.5, 0.6)], 0.22), '#1a120c', 0.7)
    comp = cv.rect(33.0, 2.4, 36.8, 4.3)
    cv.shade(comp, rust('#4a3e36', '#241a14'), r=0.35, spec=0.4)
    cv.paint(cv.lines([[(x, 2.5), (x + 0.6, 2.5)] for x in (33.6, 34.9)], 0.3), '#0a0604', 0.9)
    cv.shade(cv.rect(35.8, 1.6, 36.4, 2.6), '#3a302a', r=0.1)
    cv.shade(cv.rect(18.6, 1.6, 20.2, 2.5), '#3a302a', r=0.1)
    cv.shade(cv.circle(12.6, 3.4, 0.45), '#7a6a5a', r=0.2, spec=0.5)
    # rust blooms
    allm = np.clip(rec + mag + bar + comp, 0, 1)
    rustm = cv.feather((cv.noise(0.45, 41) > 0.55).astype(np.float32), 0.1) * allm
    cv.paint(rustm, Tex('#9a4a1c', 0.5, 0.15, 9), 0.75)
    cv.paint(cv.feather((cv.noise(0.2, 43) > 0.75).astype(np.float32), 0.05) * allm, '#d07a34', 0.6)
    cv.paint(cv.line([(11, 2.5), (21, 2.5)], 0.15), '#c8a890', 0.35)
    return cv


@sprite('scorpion', 6)
def scorpion():
    cv = Canvas(16, 8, seed=27)
    cv.ground = 7.4
    G = 7.4
    cv.shadow(8, G, 6.6, 0.6, 0.45)
    black = Lin(0, 0, 0, 7, '#4a4c58', '#16161c', '#060608')
    sh = dict(r=0.35, spec=0.7, shin=26, rim=0.3)
    # legs (behind)
    legs = []
    for i, lx in enumerate((5.4, 6.6, 7.8, 9.0)):
        legs.append([(lx, 5.2), (lx - 0.6 + i * 0.25, 4.1), (lx - 1.2 + i * 0.55, G - 0.05)])
    cv.shade(cv.lines(legs, 0.28), '#1a1a20', r=0.12, spec=0.5)
    # tail: segments arching up and over
    tail = bez((10.2, 5.0), (14.8, 4.8), (15.0, 0.2), (11.6, 0.2), (10.0, 1.2), n=60)
    for k, t in enumerate(np.linspace(0.02, 0.86, 11)):
        i = int(t * (len(tail) - 1))
        x, y = tail[i]
        cv.shade(cv.circle(x, y, 0.95 - k * 0.04), black, **sh)
    bulb = cv.ellipse(9.9, 1.6, 0.9, 0.75)
    cv.shade(bulb, '#3a2414', r=0.3, spec=0.6)
    sting = cv.tube(bez((9.3, 1.9), (8.6, 2.4), (8.7, 3.2), n=10), 0.55, 0.05)
    cv.shade(sting, '#1a0e06', r=0.15, spec=0.7)
    # body
    body = cv.ellipse(8.2, 5.2, 3.2, 1.25)
    cv.shade(body, black, **sh)
    cv.paint(cv.lines([[(x, 4.1), (x - 0.2, 6.3)] for x in (7.0, 8.0, 9.0, 10.0)], 0.1) * body, '#6a6c7a', 0.45)
    head = cv.ellipse(4.8, 5.4, 1.5, 1.05)
    cv.shade(head, black, **sh)
    # pincers
    for dy, sc in ((0.0, 1.0), (0.5, 0.85)):
        arm = cv.tube([(4.4, 5.2 + dy), (3.0, 4.8 + dy), (2.4, 3.9 + dy)], 0.6 * sc, 0.7 * sc)
        cv.shade(arm, black, **sh)
        claw = cv.poly(spline([(2.9, 3.6 + dy), (2.2, 2.8 + dy), (0.9, 2.3 + dy), (-0.2, 2.5 + dy), (0.9, 2.9 + dy), (1.2, 3.25 + dy), (0.0, 3.7 + dy), (1.2, 4.3 + dy), (2.4, 4.4 + dy)], n=5))
        cv.shade(claw, black, **sh)
    return cv


@sprite('shovel', 34)
def shovel():
    cv = Canvas(16, 36, seed=28)
    cv.ground = 35.0
    G = 35.0
    ang = 0.07
    T = lambda pts: rot_pts(pts, ang, 7, G)
    cv.shadow(7.2, G, 5.6, 1.0, 0.45)
    shaft = cv.tube(T([(7, 25.0), (7, 3.2)]), 1.35, 1.25)
    cv.shade(shaft, Tex(Lin(5, 0, 9, 0, '#c8925a', '#8a5a30', '#4a2c14'), 0.25, 0.7, 4, aniso=(0.3, 8)), r=0.55, spec=0.2)
    cv.paint(cv.line(T([(6.7, 24), (6.7, 4)]), 0.2), '#f0c890', 0.35)
    # D-handle
    d = cv.line(T(bez((7, 4.0), (3.6, 3.6), (4.0, 0.4), (7, 0.5), n=20) + bez((7, 0.5), (10.0, 0.4), (10.4, 3.6), (7, 4.0), n=20)), 0.75)
    cv.shade(d, '#8a5a30', r=0.3, spec=0.2)
    grip = cv.tube(T([(4.9, 1.0), (9.1, 1.0)]), 0.95)
    cv.shade(grip, '#a06a38', r=0.35, spec=0.25)
    # socket
    sock = cv.poly(T([(6.15, 22.6), (7.85, 22.6), (8.6, 27.2), (5.4, 27.2)]))
    cv.shade(sock, Lin(5, 0, 9, 0, '#9aa0a4', '#5a6064', '#2c3034'), r=0.4, spec=0.6, shin=24)
    cv.shade(cv.circle(*T([(7, 24.3)])[0], 0.3), '#cfd3d6', r=0.15, spec=0.6)
    # blade (partly buried)
    blade = cv.poly(T([(1.6, 26.6), (12.4, 26.6), (12.2, 32.6)] + bez((12.2, 32.6), (11.0, 37.0), (3.0, 37.0), (1.8, 32.6), n=20)))
    cv.shade(blade, Tex(Lin(2, 26, 11, 36, '#c4c9cd', '#82888c', '#40464a'), 0.12, 0.5, 6), r=1.0, spec=0.5, shin=20, rim=0.2)
    cv.paint(cv.feather((cv.noise(0.5, 61) > 0.62).astype(np.float32), 0.08) * blade, '#8a4a20', 0.55)
    cv.paint(cv.line(T([(1.7, 26.7), (12.3, 26.7)]), 0.5, caps=False), '#e6eaee', 0.7)
    cv.paint(cv.line(T([(7, 27.5), (7, 33.0)]), 0.35), '#5a6064', 0.6)
    # heap of earth around the blade
    earth = cv.poly(spline([(0.3, G + 0.2), (1.8, 34.0), (4.5, 33.0), (7.2, 33.3), (10.0, 32.9), (12.8, 33.9), (14.6, G + 0.2)], n=8))
    cv.shade(earth, Tex('#7a5a3a', 0.4, 0.3, 7), r=0.8, spec=0.05, tex=0.3, tscale=0.2, tseed=9)
    for x, y, r_ in ((3.0, 33.9, 0.5), (10.6, 33.6, 0.45), (6.0, 33.4, 0.35)):
        cv.shade(cv.ellipse(x, y, r_, r_ * 0.8), '#8a8078', r=0.2, spec=0.2)
    return cv


@sprite('earth', 26)
def earth():
    cv = Canvas(64, 28, seed=29)
    cv.ground = 27.0
    G = 27.0
    rng = np.random.default_rng(29)
    prof = [(0.5, G + 0.3), (4, 22.5), (9, 16.5), (14, 10.5), (19, 5.6), (24, 2.2), (28, 1.4), (32, 2.6), (37, 5.0), (42, 9.5), (48, 14.5), (54, 19.0), (59, 23.5), (63.5, G + 0.3)]
    prof = [(x + (rng.normal(0, 0.4) if 0 < i < len(prof) - 1 else 0), y + (rng.normal(0, 0.4) if 0 < i < len(prof) - 1 else 0)) for i, (x, y) in enumerate(prof)]
    heap = cv.poly(spline(prof, n=10))
    cv.paint(cv.feather(cv.rect(0, G - 1.2, 64, G + 1), 0.7) * 0 + cv.feather(cv.ellipse(32, G, 33, 1.6), 0.8), (0, 0, 0), 0.35)
    col = Tex(Lin(20, 0, 44, 27, '#9a7048', '#6a4a2c', '#3a2614'), 0.5, 0.6, 3)
    cv.shade(heap, col, r=5.0, spec=0.05, rim=0.25, tex=0.35, tscale=0.25, tseed=5)
    cv.paint(cv.feather((cv.noise(1.4, 7) > 0.6).astype(np.float32), 0.6) * heap, '#2a1a0c', 0.25)
    # stones, clods and rubble
    pts = []
    for i in range(70):
        x = rng.uniform(3, 61)
        top = np.interp(x, [p[0] for p in prof], [p[1] for p in prof])
        y = rng.uniform(top + 1.0, G - 0.4)
        pts.append((x, y))
    pts.sort(key=lambda p: p[1])
    for i, (x, y) in enumerate(pts):
        r_ = rng.uniform(0.4, 1.5) * (1.3 if y > 20 else 1.0)
        kind = rng.random()
        if kind < 0.35:   # angular rubble (concrete / brick)
            n = rng.integers(4, 7)
            poly = [(x + r_ * math.cos(a) * rng.uniform(0.7, 1.3), y + r_ * 0.75 * math.sin(a) * rng.uniform(0.7, 1.3)) for a in np.sort(rng.uniform(0, 2 * math.pi, n))]
            c = ['#8a8680', '#a09a90', '#9a5a3a', '#6a6660'][rng.integers(0, 4)]
            m = cv.poly(poly)
            cv.paint(cv.feather(cv.ellipse(x + 0.2, y + r_ * 0.6, r_ * 1.1, r_ * 0.35), 0.2), (0, 0, 0), 0.35)
            cv.shade(m, c, r=0.35, spec=0.15, rim=0.2, tex=0.2, tscale=0.15)
        elif kind < 0.7:  # pebbles
            m = cv.ellipse(x, y, r_ * 0.7, r_ * 0.5, rot=rng.uniform(-0.5, 0.5))
            cv.shade(m, ['#6a6058', '#4a423a', '#8a7a68'][rng.integers(0, 3)], r=0.3, spec=0.3)
        else:  # clods of earth
            m = cv.ellipse(x, y, r_ * 0.9, r_ * 0.6, rot=rng.uniform(-0.5, 0.5))
            cv.shade(m, '#7a5434', r=0.4, spec=0.05, tex=0.3, tscale=0.15)
    # roots / straw
    for i in range(6):
        x = rng.uniform(10, 54)
        top = np.interp(x, [p[0] for p in prof], [p[1] for p in prof])
        y = top + rng.uniform(1, 6)
        cv.paint(cv.line(bez((x, y), (x + rng.uniform(-2, 2), y - 1.2), (x + rng.uniform(-3, 3), y - 0.4), n=12), 0.18), '#c8a868', 0.7)
    return cv


TD = dict(bx0=6.5, bx1=37.5, fx0=1.0, fx1=43.0)


def trapdoor_frame(cv, top, bot):
    """Returns the four corner points of the trapdoor footprint."""
    return [(TD['bx0'], top), (TD['bx1'], top), (TD['fx1'], bot), (TD['fx0'], bot)]


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def quad_pt(q, u, v):
    """Bilinear point in quad q (back-left, back-right, front-right, front-left), u across, v back->front."""
    return lerp2(lerp2(q[0], q[1], u), lerp2(q[3], q[2], u), v)


@sprite('trapdoor', 10)
def trapdoor():
    cv = Canvas(44, 11.5, seed=30)
    cv.ground = 10.6
    q = trapdoor_frame(cv, 0.8, 10.2)
    outer = cv.poly([(q[0][0] - 0.8, q[0][1] - 0.5), (q[1][0] + 0.8, q[1][1] - 0.5), (q[2][0] + 0.9, q[2][1] + 0.4), (q[3][0] - 0.9, q[3][1] + 0.4)])
    cv.paint(cv.feather(outer, 0.3), '#2a2018', 0.85)
    door = cv.poly(q)
    cv.shade(door, Tex(Lin(0, 0.8, 0, 10.2, '#8a6a44', '#a87e50', '#7a5432'), 0.3, 1.0, 3, aniso=(0.4, 6)), r=0.5, spec=0.08, rim=0.15)
    # plank seams converging
    segs = [[quad_pt(q, u, 0), quad_pt(q, u, 1)] for u in np.linspace(0, 1, 7)[1:-1]]
    cv.paint(cv.lines(segs, 0.2) * door, '#2a1a0c', 0.8)
    cv.paint(cv.lines([[(a[0] + 0.25, a[1]), (b[0] + 0.3, b[1])] for a, b in segs], 0.12) * door, '#d8b080', 0.35)
    # iron straps
    for v in (0.22, 0.72):
        w = 0.09
        strap = cv.poly([quad_pt(q, 0, v - w), quad_pt(q, 1, v - w), quad_pt(q, 1, v + w), quad_pt(q, 0, v + w)])
        cv.shade(strap, Tex('#4a4440', 0.3, 0.3, 5), r=0.25, spec=0.4)
        for u in np.linspace(0.06, 0.94, 7):
            p = quad_pt(q, u, v)
            cv.shade(cv.ellipse(p[0], p[1], 0.38, 0.26), '#8a8078', r=0.12, spec=0.6)
    # hasp, ring and padlock at the front edge
    hp = quad_pt(q, 0.5, 0.86)
    hasp = cv.rrect(hp[0] - 1.0, hp[1] - 1.4, hp[0] + 1.0, hp[1] + 1.2, 0.3)
    cv.shade(hasp, '#3e3a36', r=0.25, spec=0.4)
    ring = cv.ellipse(hp[0] - 4.2, hp[1] - 0.6, 1.7, 0.75) * (1 - cv.ellipse(hp[0] - 4.2, hp[1] - 0.6, 1.15, 0.38))
    cv.paint(cv.feather(cv.ellipse(hp[0] - 4.0, hp[1] - 0.3, 1.8, 0.8), 0.2) * (1 - ring), (0, 0, 0), 0.25)
    cv.shade(ring, '#5a5450', r=0.2, spec=0.6)
    cv.shade(cv.rect(hp[0] - 4.5, hp[1] - 1.6, hp[0] - 3.9, hp[1] - 1.1), '#3a3632', r=0.1)
    shackle = cv.line(bez((hp[0] - 0.65, hp[1] + 0.6), (hp[0] - 0.7, hp[1] - 1.4), (hp[0] + 0.7, hp[1] - 1.4), (hp[0] + 0.65, hp[1] + 0.6), n=20), 0.35)
    cv.shade(shackle, '#c0c4c8', r=0.12, spec=0.7)
    lock = cv.rrect(hp[0] - 1.25, hp[1] + 0.3, hp[0] + 1.25, hp[1] + 2.3, 0.35)
    cv.shade(lock, Lin(0, hp[1], 0, hp[1] + 2.3, '#e0b850', '#9a7420'), r=0.4, spec=0.7, shin=20)
    cv.paint(cv.ellipse(hp[0], hp[1] + 1.25, 0.22, 0.3), '#2a1a08', 0.9)
    return cv


@sprite('trapdoor_open', 22)
def trapdoor_open():
    cv = Canvas(44, 23.5, seed=30)
    cv.ground = 22.6
    off = 12.0
    q = trapdoor_frame(cv, 0.8 + off, 10.2 + off)
    outer = cv.poly([(q[0][0] - 0.8, q[0][1] - 0.5), (q[1][0] + 0.8, q[1][1] - 0.5), (q[2][0] + 0.9, q[2][1] + 0.4), (q[3][0] - 0.9, q[3][1] + 0.4)])
    cv.paint(cv.feather(outer, 0.3), '#2a2018', 0.9)
    hole = cv.poly(q)
    cv.paint(hole, Lin(0, q[0][1], 0, q[2][1], '#000000', '#0c0806', '#2a2018'))
    # inner walls of the shaft
    cv.paint(cv.poly([q[3], q[2], (q[2][0] - 2.4, q[2][1] - 2.6), (q[3][0] + 2.4, q[3][1] - 2.6)]), Lin(0, q[2][1] - 2.6, 0, q[2][1], '#100a06', '#3a2c20'), 0.0)
    cv.paint(cv.poly([q[0], q[3], (q[3][0] + 3.0, q[3][1]), (q[0][0] + 1.2, q[0][1])]), Lin(q[3][0], 0, q[3][0] + 3, 0, '#4a3a2c', '#0a0604'), 0.85)
    cv.paint(cv.poly([q[1], q[2], (q[2][0] - 3.0, q[2][1]), (q[1][0] - 1.2, q[1][1])]), Lin(q[2][0], 0, q[2][0] - 3, 0, '#2e2218', '#050302'), 0.85)
    # ladder top: two rails and rungs rising from the dark
    for x in (17.2, 26.8):
        rail = cv.rect(x - 0.6, q[0][1] - 0.8, x + 0.6, q[2][1] - 0.2)
        cv.shade(rail, Lin(0, q[0][1], 0, q[2][1], '#a07850', '#3a2a1a', '#0a0604'), r=0.3, spec=0.1)
        cv.shade(cv.ellipse(x, q[0][1] - 0.8, 0.6, 0.3), '#c09a6a', r=0.15)
    for y in np.arange(q[0][1] + 1.0, q[2][1] - 1.0, 2.6):
        t = (y - q[0][1]) / (q[2][1] - q[0][1])
        rung = cv.rect(17.6, y, 26.4, y + 0.75)
        cv.shade(rung, mix('#8a6440', '#0a0604', t * 1.1 if t < 0.9 else 1), r=0.25, spec=0.08)
    cv.paint(cv.feather(hole, 1.0) * cv.rect(0, q[3][1] - 3, 44, 30), (0, 0, 0), 0.0)
    # the door, flipped open, standing on its back hinge (we see its underside)
    top_y = 0.4
    d = [(q[0][0] + 0.4, top_y), (q[1][0] - 0.4, top_y), (q[1][0] + 0.2, q[1][1] - 0.2), (q[0][0] - 0.2, q[0][1] - 0.2)]
    door = cv.poly(d)
    cv.shade(door, Tex(Lin(0, top_y, 0, q[0][1], '#6a5034', '#8a6844', '#4a3420'), 0.3, 1.0, 3, aniso=(0.4, 6)), r=0.5, spec=0.06, rim=0.15)
    segs = [[quad_pt(d, u, 0), quad_pt(d, u, 1)] for u in np.linspace(0, 1, 7)[1:-1]]
    cv.paint(cv.lines(segs, 0.2) * door, '#20140a', 0.8)
    # Z brace battens on the underside
    for v in (0.15, 0.8):
        b = cv.poly([quad_pt(d, 0.03, v - 0.06), quad_pt(d, 0.97, v - 0.06), quad_pt(d, 0.97, v + 0.06), quad_pt(d, 0.03, v + 0.06)])
        cv.shade(b, '#7a5a38', r=0.3, spec=0.08)
    z = cv.poly([quad_pt(d, 0.05, 0.74), quad_pt(d, 0.14, 0.74), quad_pt(d, 0.95, 0.22), quad_pt(d, 0.86, 0.22)])
    cv.shade(z, '#7a5a38', r=0.3, spec=0.08)
    # hinges at the base
    for u in (0.2, 0.8):
        p = quad_pt(d, u, 1.0)
        cv.shade(cv.rrect(p[0] - 1.6, p[1] - 1.4, p[0] + 1.6, p[1] + 0.5, 0.3), '#3e3a36', r=0.25, spec=0.4)
    # open padlock lying by the front edge
    hp = quad_pt(q, 0.72, 1.0)
    lock = cv.rrect(hp[0] - 1.1, hp[1] - 1.6, hp[0] + 1.1, hp[1] + 0.1, 0.35)
    cv.shade(cv.line(bez((hp[0] + 0.5, hp[1] - 1.5), (hp[0] + 0.6, hp[1] - 3.2), (hp[0] + 2.4, hp[1] - 3.0), (hp[0] + 2.0, hp[1] - 1.8), n=20), 0.32), '#c0c4c8', r=0.12, spec=0.7)
    cv.shade(lock, Lin(0, hp[1] - 1.6, 0, hp[1], '#e0b850', '#9a7420'), r=0.4, spec=0.7, shin=20)
    return cv


# ---- creatures -------------------------------------------------------------------------------

def scales_field(base, k=2.2, amt=0.18, rot=0.5):
    """Scale-like cell pattern multiplied into a colour/field."""
    def f(R):
        c = field_eval(base, R)
        X = R.X * math.cos(rot) - R.Y * math.sin(rot)
        Y = R.X * math.sin(rot) + R.Y * math.cos(rot)
        p = np.abs(np.sin(X * k * math.pi)) * np.abs(np.sin((Y * k + 0.5 * np.floor(X * k)) * math.pi))
        return c * (1 - amt + amt * 2 * np.sqrt(p))[..., None]
    return f


SPIDER_DARK = '#2a1c14'


def spider_leg(cv, pts, w0, w1, hair_seed, knee_col='#c8783a'):
    path = spline(pts, n=12)
    m = cv.tube(path, w0, w1)
    cv.shade(m, Lin(0, 0, 0, 28, '#4a3226', '#1e140e'), r=0.6, spec=0.25, shin=12, rim=0.3)
    # banded joints
    for j in (1, 2):
        x, y = pts[j]
        band = cv.circle(x, y, w0 * (0.62 - 0.1 * j)) * m
        cv.shade(band, knee_col, r=0.3, spec=0.2, alpha=0.85)
    # bristles sticking out of the leg
    out = np.clip(cv.feather(m, 0.15) - m * 0.0, 0, 1)
    cv.hairs(m, int(260 * w0), 0.9, 0.11, '#8a6a4a', seed=hair_seed, angle=None, jitter=3.0, alpha=0.75)
    cv.hairs(m, int(120 * w0), 1.1, 0.1, '#0e0a08', seed=hair_seed + 1, angle=None, jitter=3.0, alpha=0.8)
    return m


@sprite('spider', 26)
def spider():
    cv = Canvas(50, 30, seed=31)
    cv.ground = 28.0
    G = 28.0
    cx = 25.0
    # legs (front pair last so it overlaps)
    legs = [
        # (root, knee, ankle, foot), widths
        ([(3.6, 13.5), (13.0, 3.2), (17.5, 11.5), (20.5, G - 0.2)], 2.3, 1.0),   # 1st pair: forward, feet near the middle
        ([(4.0, 14.5), (15.5, 6.0), (20.5, 15.5), (22.5, G - 1.0)], 2.2, 1.0),
        ([(3.8, 15.8), (16.0, 10.0), (21.5, 18.8), (23.3, G - 3.0)], 2.1, 0.95),
        ([(3.0, 17.0), (13.0, 14.5), (17.8, 21.5), (19.0, G - 5.4)], 2.0, 0.9),
    ]
    for i in (3, 2, 1, 0):
        pts, w0, w1 = legs[i]
        for sgn in (-1, 1):
            p = [(cx + sgn * x, y) for x, y in pts]
            spider_leg(cv, p, w0, w1, 100 + i * 10 + (sgn > 0))
    # abdomen (behind and above)
    ab = cv.ellipse(cx, 8.0, 6.4, 5.6)
    cv.shade(ab, Rad(cx - 2, 5, 8, '#5a3e2c', '#2c1e16', '#120c08'), r=2.2, spec=0.15)
    cv.hairs(ab, 2600, 1.0, 0.12, '#a07a52', seed=5, angle=radial(cx, 8.0, 0.0), jitter=0.6, alpha=0.55)
    cv.hairs(ab, 1200, 0.9, 0.11, '#c8622a', seed=6, angle=radial(cx, 8.0, 0.0), jitter=0.6, alpha=0.4)
    # cephalothorax
    ce = cv.ellipse(cx, 14.6, 5.2, 4.4)
    cv.shade(ce, Rad(cx - 2, 12.5, 6.5, '#6a4a34', '#34241a', '#140e0a'), r=1.8, spec=0.25, shin=14)
    cv.hairs(ce, 1500, 0.8, 0.11, '#b08a60', seed=7, angle=radial(cx, 14.6, 0.0), jitter=0.5, alpha=0.5)
    cv.hairs(np.clip(ab + ce, 0, 1) * (1 - cv.ellipse(cx, 11.5, 6, 9)) + cv.feather(ab, 0.2) * 0, 400, 1.2, 0.12, '#7a5a40', seed=8, angle=radial(cx, 11, 0), jitter=0.4, alpha=0.8)
    # pedipalps
    for sgn in (-1, 1):
        p = spline([(cx + sgn * 2.6, 16.2), (cx + sgn * 5.2, 17.8), (cx + sgn * 4.4, 21.6), (cx + sgn * 3.4, 23.0)], n=10)
        m = cv.tube(p, 1.6, 1.0)
        cv.shade(m, '#3a2a1e', r=0.5, spec=0.25)
        cv.hairs(m, 300, 0.8, 0.1, '#9a7650', seed=20 + sgn, jitter=3, alpha=0.7)
    # chelicerae with fangs
    for sgn in (-1, 1):
        ch = cv.ellipse(cx + sgn * 1.45, 18.6, 1.65, 2.4)
        cv.shade(ch, Rad(cx + sgn * 1.4 - 0.6, 17.2, 3, '#5a4030', '#2a1c14'), r=0.8, spec=0.2)
        cv.hairs(ch, 300, 0.7, 0.1, '#b89068', seed=30 + sgn, angle=lambda x, y: math.pi / 2, jitter=0.7, alpha=0.6)
        fang = cv.poly(bez((cx + sgn * 2.4, 20.2), (cx + sgn * 2.2, 22.8), (cx + sgn * 0.8, 23.6), n=12) + bez((cx + sgn * 0.8, 23.6), (cx + sgn * 1.6, 22.4), (cx + sgn * 0.7, 20.6), n=12))
        cv.shade(fang, '#0c0806', r=0.3, spec=0.9, shin=30, rim=0.1)
    # eyes: a cluster of glossy beads with a red glint
    for ex, ey, er in ((-0.75, 11.3, 0.62), (0.75, 11.3, 0.62), (-2.0, 11.0, 0.42), (2.0, 11.0, 0.42), (-1.5, 10.1, 0.36), (1.5, 10.1, 0.36), (-2.4, 12.1, 0.34), (2.4, 12.1, 0.34)):
        e = cv.circle(cx + ex, ey, er)
        cv.shade(e, '#060404', r=er * 0.5, spec=0.0, rim=0.0, amb=1.0, diff=0)
        cv.paint(cv.circle(cx + ex - er * 0.15, ey + er * 0.15, er * 0.55) * e, '#7a0c0c', 0.6)
        cv.hl(cx + ex - er * 0.35, ey - er * 0.35, er * 0.3, er * 0.24, 0.95, soft=0.2)
    return cv


@sprite('spider_dead', 8)
def spider_dead():
    cv = Canvas(30, 10, seed=32)
    cv.ground = 9.0
    G = 9.0
    cx = 15.0
    stain = cv.feather(cv.ellipse(cx, 7.4, 10.5, 1.5), 0.6)
    cv.paint(stain, '#2a3014', 0.45)
    rng = np.random.default_rng(32)
    for sgn in (-1, 1):
        for i in range(4):
            a0 = 3.0 + i * 2.2
            pts = [(cx + sgn * 2.0, 7.3 - i * 0.2), (cx + sgn * (a0 + 1.0), 6.6 - i * 0.7 + rng.uniform(-0.5, 0.5)),
                   (cx + sgn * (a0 + 3.2), 7.2 - (i % 2) * 2.0), (cx + sgn * (a0 + 2.0), 8.4 - (i % 2) * 2.4 + rng.uniform(-0.3, 0.3))]
            m = cv.tube(spline(pts, n=8), 1.0, 0.5)
            cv.shade(m, '#2a1c14', r=0.3, spec=0.2)
            cv.paint(cv.circle(*pts[1], 0.4) * m, '#b0682e', 0.8)
            cv.hairs(m, 120, 0.5, 0.08, '#8a6a4a', seed=40 + i + 10 * (sgn > 0), jitter=3, alpha=0.6)
    body = cv.ellipse(cx, 7.3, 4.8, 1.6)
    cv.shade(body, Rad(cx - 1.5, 6.4, 5, '#4a3424', '#1e140e'), r=0.8, spec=0.2)
    ab = cv.ellipse(cx + 1.6, 7.1, 3.2, 1.4)
    cv.shade(ab, '#2e2016', r=0.7, spec=0.15)
    cv.hairs(np.maximum(body, ab), 900, 0.6, 0.1, '#9a7654', seed=44, jitter=3, alpha=0.5)
    # curled legs pointing up
    for sgn, x in ((-1, 12.0), (1, 18.2)):
        m = cv.tube(spline([(x, 6.6), (x + sgn * 0.6, 4.2), (x + sgn * 2.0, 2.6), (x + sgn * 2.6, 3.6)], n=8), 0.9, 0.45)
        cv.shade(m, '#2a1c14', r=0.3, spec=0.2)
        cv.hairs(m, 90, 0.5, 0.08, '#8a6a4a', seed=50 + sgn, jitter=3, alpha=0.6)
    return cv


COBRA_BACK = '#5e5a2c'
COBRA_BELLY = '#e2cf8c'


def snake_tube(cv, path, w0, w1, belly=0.0, seed=0, col=None):
    m = cv.tube(path, w0, w1)
    base = col or Lin(0, 0, 0, 40, '#6e6a34', '#4a4622')
    cv.shade(m, scales_field(Tex(base, 0.2, 1.2, seed), k=2.8, amt=0.16), r=w0 * 0.35, spec=0.35, shin=16, rim=0.35)
    # dark bands across the back
    p = np.array(path)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    bands = []
    for t in np.arange(1.5, s[-1], 3.2):
        i = min(np.searchsorted(s, t), len(p) - 1)
        i0 = max(i - 1, 0)
        d = p[i] - p[i0]
        ln = np.hypot(*d) or 1
        nx, ny = -d[1] / ln, d[0] / ln
        x, y = p[i]
        w = np.interp(t, [0, s[-1]], [w0, w1])
        bands.append([(x - nx * w * 0.6, y - ny * w * 0.6), (x + nx * w * 0.6, y + ny * w * 0.6)])
    cv.paint(cv.lines(bands, 0.55) * m, '#2a2612', 0.45)
    return m


@sprite('cobra', 36)
def cobra():
    cv = Canvas(34, 38, seed=33)
    cv.ground = 37.0
    G = 37.0
    cx = 17.0
    cv.shadow(cx, G, 13.5, 1.6, 0.45)
    # coils on the ground: back coil, tail, front coil
    snake_tube(cv, ell_pts(cx + 1.0, 32.6, 10.5, 2.6, n=80, a0=math.pi * 1.05, a1=math.pi * 2.0), 3.6, 3.6, seed=1)
    snake_tube(cv, bez((cx + 11.0, 33.4), (cx + 15.5, 35.5), (cx + 13.0, 36.4), (cx + 9.0, 36.2), n=30), 3.0, 0.6, seed=2)
    snake_tube(cv, ell_pts(cx + 0.5, 33.3, 11.0, 2.4, n=80, a0=0.0, a1=math.pi * 0.98), 3.9, 3.9, seed=3)
    snake_tube(cv, ell_pts(cx - 0.5, 32.0, 8.0, 1.9, n=60, a0=math.pi * 0.95, a1=math.pi * 0.25 + math.pi * 2), 3.6, 3.6, seed=4)
    # rising body
    neck = bez((cx + 6.0, 33.4), (cx + 0.5, 32.5), (cx - 2.2, 27.0), (cx + 0.6, 20.5), (cx, 15.0), n=60)
    m = cv.tube(neck, 4.2, 3.6)
    cv.shade(m, scales_field(Lin(cx - 2, 0, cx + 2.5, 0, '#f2e2a8', COBRA_BELLY, '#a8944e'), k=2.4, amt=0.1, rot=0), r=1.2, spec=0.3, rim=0.35)
    belly_lines = [[(x - 1.6, y), (x + 1.6, y)] for x, y in neck[8:-4:3]]
    cv.paint(cv.lines(belly_lines, 0.12) * m, '#8a7a40', 0.55)
    # hood (front view): broad, flattened, with dark throat bands
    hood = cv.poly(spline([(cx, 5.0), (cx + 5.4, 6.4), (cx + 7.4, 10.5), (cx + 6.2, 15.5), (cx + 2.6, 19.8), (cx, 21.0),
                           (cx - 2.6, 19.8), (cx - 6.2, 15.5), (cx - 7.4, 10.5), (cx - 5.4, 6.4)], n=10, closed=True))
    cv.shade(hood, scales_field(Lin(cx - 7, 0, cx + 7, 0, '#7a7440', '#5a5628', '#3a3618'), k=2.6, amt=0.18), r=1.4, spec=0.3, rim=0.4)
    inner = cv.poly(spline([(cx, 6.4), (cx + 4.0, 8.2), (cx + 5.0, 11.5), (cx + 3.6, 16.8), (cx + 1.6, 19.6), (cx, 20.2),
                            (cx - 1.6, 19.6), (cx - 3.6, 16.8), (cx - 5.0, 11.5), (cx - 4.0, 8.2)], n=10, closed=True))
    cv.shade(inner, scales_field(Lin(0, 6, 0, 20, '#f6e8b8', COBRA_BELLY, '#b49c58'), k=2.4, amt=0.12, rot=0), r=1.0, spec=0.25, rim=0.2, bulge=0.6)
    for y, w in ((12.6, 1.0), (15.0, 0.75)):
        cv.paint(cv.feather(cv.rect(cx - 6, y - w / 2, cx + 6, y + w / 2), 0.2) * inner, '#2c2412', 0.85)
    cv.paint(cv.lines([[(cx - 4.5, y), (cx + 4.5, y)] for y in np.arange(8.0, 20, 0.85)], 0.08) * inner, '#8a7438', 0.5)
    # head
    head = cv.poly(spline([(cx, 0.4), (cx + 2.6, 1.0), (cx + 3.1, 3.4), (cx + 2.0, 6.6), (cx, 7.4), (cx - 2.0, 6.6), (cx - 3.1, 3.4), (cx - 2.6, 1.0)], n=10, closed=True))
    cv.shade(head, scales_field(Rad(cx - 1, 1.5, 6, '#8a844a', '#5e5a2c', '#34301a'), k=3.2, amt=0.12), r=1.0, spec=0.45, shin=18)
    cv.paint(cv.lines([[(cx - 2.4, 2.2), (cx, 1.4), (cx + 2.4, 2.2)]], 0.12) * head, '#2a2612', 0.5)
    # mouth slightly open with fangs, forked tongue
    mouth = cv.poly(bez((cx - 1.6, 5.6), (cx, 6.4), (cx + 1.6, 5.6), n=12) + bez((cx + 1.4, 5.9), (cx, 7.6), (cx - 1.4, 5.9), n=12))
    cv.paint(mouth, '#4a0c10')
    for sgn in (-1, 1):
        cv.paint(cv.poly([(cx + sgn * 0.9, 5.9), (cx + sgn * 0.55, 5.9), (cx + sgn * 0.7, 7.0)]), '#f4f0e0')
    tongue = cv.lines([[(cx, 6.8), (cx, 8.6), (cx - 0.6, 9.6)], [(cx, 8.6), (cx + 0.6, 9.6)]], 0.2)
    cv.paint(tongue, '#d0283a')
    # eyes: glinting, menacing
    for sgn in (-1, 1):
        e = cv.ellipse(cx + sgn * 2.05, 3.2, 0.75, 0.6, rot=sgn * 0.4)
        cv.shade(e, '#e8b020', r=0.25, spec=0.2, rim=0.2)
        cv.paint(cv.ellipse(cx + sgn * 2.05, 3.2, 0.18, 0.5), '#080404')
        cv.hl(cx + sgn * 2.05 - 0.25, 2.9, 0.18, 0.14, 0.95, soft=0.2)
        brow = cv.line([(cx + sgn * 1.3, 2.3), (cx + sgn * 2.9, 2.6)], 0.35)
        cv.paint(brow, '#2a2612', 0.8)
    cv.paint(cv.circle(cx - 0.6, 4.6, 0.2), '#141008')
    cv.paint(cv.circle(cx + 0.6, 4.6, 0.2), '#141008')
    return cv


@sprite('cobra_dead', 6)
def cobra_dead():
    cv = Canvas(30, 8, seed=34)
    cv.ground = 7.2
    G = 7.2
    cv.shadow(15, G, 13.5, 0.9, 0.45)
    snake_tube(cv, ell_pts(14.0, 4.4, 9.0, 1.7, n=80, a0=math.pi, a1=2 * math.pi), 2.6, 2.6, seed=5)
    snake_tube(cv, bez((5.4, 4.6), (3.0, 6.8), (8.0, 6.6), (12.0, 6.0), (16.0, 6.4), n=30), 2.4, 2.6, seed=6)
    # belly-up section
    b = cv.tube(ell_pts(14.0, 4.4, 9.0, 1.7, n=60, a0=0.05, a1=math.pi * 0.62), 2.6, 2.6)
    cv.shade(b, scales_field(COBRA_BELLY, k=2.4, amt=0.12, rot=0), r=0.8, spec=0.3)
    cv.paint(cv.lines([[(x, 4.9), (x + 0.2, 6.6)] for x in np.arange(11, 23, 0.8)], 0.1) * b, '#8a7438', 0.5)
    snake_tube(cv, bez((20.5, 4.6), (16.0, 2.0), (10.0, 3.0), (11.0, 4.0), n=30), 2.2, 1.8, seed=7)
    snake_tube(cv, bez((22.0, 5.6), (25.5, 7.4), (27.5, 6.4), (28.6, 6.0), n=20), 2.2, 0.5, seed=8)
    # limp head with half-flattened hood
    hood = cv.ellipse(4.4, 5.0, 2.6, 1.7, rot=0.3)
    cv.shade(hood, '#5e5a2c', r=0.7, spec=0.25)
    head = cv.ellipse(2.4, 5.8, 1.7, 1.0, rot=0.25)
    cv.shade(head, '#6a6434', r=0.5, spec=0.4)
    cv.paint(cv.lines([[(1.7, 5.0), (2.5, 5.6)], [(2.5, 5.0), (1.7, 5.6)]], 0.16), '#1a1408', 0.9)
    cv.paint(cv.lines([[(0.9, 6.4), (0.1, 6.9)], [(0.5, 6.65), (0.1, 6.3)]], 0.13), '#c02838', 0.9)
    return cv


PLANT_GREEN = '#3e7a2a'


def plant_leaf(cv, base, tip, width, curl=0.0, col='#3f7f2c', dark='#1e4416', seed=0, wilt=0.0):
    (bx, by), (tx, ty) = base, tip
    dx, dy = tx - bx, ty - by
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    mid = (bx + dx * 0.5 + nx * curl, by + dy * 0.5 + ny * curl)
    spine = bez(base, mid, tip, n=40)
    left, right = [], []
    for i, (x, y) in enumerate(spine):
        t = i / (len(spine) - 1)
        w = width * math.sin(math.pi * min(1, t * 1.05)) ** 0.8 * (1 - 0.3 * t)
        jag = 1 + 0.12 * math.sin(t * 40 + seed)
        left.append((x + nx * w * jag, y + ny * w * jag))
        right.append((x - nx * w, y - ny * w))
    m = cv.poly(left + right[::-1])
    c = mix(col, '#9a7a2a', wilt)
    d = mix(dark, '#4a3014', wilt)
    cv.shade(m, Lin(bx, by, tx, ty, d, c, mix(c, '#c8d870', 0.25 - 0.2 * wilt)), r=width * 0.35, spec=0.25, shin=12, rim=0.3, tex=0.12, tscale=0.6, tseed=seed)
    cv.paint(cv.line(spine[2:-4], width * 0.12) * m, mix('#a8c860', '#d8c080', wilt), 0.6)
    veins = []
    for i in range(4, len(spine) - 6, 4):
        x, y = spine[i]
        t = i / (len(spine) - 1)
        w = width * math.sin(math.pi * t) * 0.8
        veins.append([(x, y), (x + nx * w + dx / L * w * 0.6, y + ny * w + dy / L * w * 0.6)])
        veins.append([(x, y), (x - nx * w + dx / L * w * 0.6, y - ny * w + dy / L * w * 0.6)])
    cv.paint(cv.lines(veins, width * 0.05) * m, mix('#8ab850', '#c0a060', wilt), 0.35)
    if wilt:
        cv.paint(cv.feather((cv.noise(0.8, seed + 70) > 0.6).astype(np.float32), 0.2) * m, '#5a3a14', 0.5 * wilt)
    return m


def plant_base_leaves(cv, cx, G, wilt=0.0):
    leaves = [((cx - 1, G - 1.0), (cx - 21, G - 5.0 + 4 * wilt), 3.4, -3.0),
              ((cx + 1, G - 1.0), (cx + 22, G - 4.0 + 3.6 * wilt), 3.4, 3.0),
              ((cx - 1, G - 2.0), (cx - 13, G - 15.0 + 11 * wilt), 2.8, -2.5),
              ((cx + 1, G - 2.0), (cx + 14, G - 14.0 + 10 * wilt), 2.8, 2.5),
              ((cx, G - 0.6), (cx - 9, G - 0.4), 2.2, 1.0),
              ((cx, G - 0.6), (cx + 10, G - 0.3), 2.2, -1.0)]
    for i, (b, t, w, c) in enumerate(leaves):
        if wilt:
            c = c * 1.8 + (2.5 if t[0] > cx else -2.5)
        plant_leaf(cv, b, t, w, c, seed=i, wilt=wilt)


def teeth_along(cv, edge, direction, length, n, col='#f2ead2', seed=0):
    """Triangular teeth on a polyline edge, pointing in the normal direction (sign) of the edge."""
    rng = np.random.default_rng(seed)
    p = np.array(edge)
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    polys = []
    for k in range(n):
        t = (k + 0.5) / n * s[-1]
        i = min(np.searchsorted(s, t), len(p) - 1)
        d = p[i] - p[max(i - 1, 0)]
        ln = np.hypot(*d) or 1
        tx, ty = d / ln
        nx, ny = -ty * direction, tx * direction
        x, y = p[i]
        L = length * rng.uniform(0.7, 1.15) * (0.6 + 0.4 * math.sin(math.pi * (k + 0.5) / n))
        hw = s[-1] / n * 0.42
        tipx, tipy = x + nx * L + tx * L * 0.15, y + ny * L + ty * L * 0.15
        polys.append([(x - tx * hw, y - ty * hw), (x + tx * hw, y + ty * hw), (tipx, tipy)])
    m = cv.poly(*polys)
    cv.shade(m, Lin(0, 0, 0, 1, col, col), r=0.35, spec=0.5, shin=20, rim=0.35)
    return m


@sprite('plant', 64)
def plant():
    cv = Canvas(62, 68, ss=3, seed=35)
    cv.ground = 66.0
    G = 66.0
    cx = 30.0
    cv.anchor = cx
    cv.shadow(cx, G, 22, 2.0, 0.45)
    # tendrils behind
    for i, (pts, w) in enumerate((([(cx + 1, 50), (cx + 12, 44), (cx + 20, 36), (cx + 24, 28), (cx + 21.5, 25.5), (cx + 20.5, 28)], 1.2),
                                  ([(cx - 1, 54), (cx - 10, 49), (cx - 19, 46), (cx - 25, 40), (cx - 23, 37), (cx - 21.5, 39)], 1.1),
                                  ([(cx, 46), (cx - 6, 40), (cx - 15, 37), (cx - 20, 31), (cx - 17.5, 29.5), (cx - 17, 31.5)], 0.9))):
        m = cv.tube(spline(pts, n=10), w, 0.3)
        cv.shade(m, '#4a7e2a', r=0.4, spec=0.2)
        for j in range(3, len(pts) - 2):
            x, y = pts[j]
            cv.shade(cv.poly([(x - 0.4, y), (x + 0.4, y), (x + 1.4, y - 1.2)]), '#c8d890', r=0.2)
    # thick stalk
    stalk = bez((cx, G - 1), (cx - 4, 52), (cx + 7, 42), (cx + 3, 32), (cx + 5.5, 24), n=60)
    m = cv.tube(stalk, 6.0, 4.0)
    cv.shade(m, Tex(Lin(cx - 4, 0, cx + 8, 0, '#6aa040', '#3e7a2a', '#1e4416'), 0.15, 2.0, 3, aniso=(0.3, 4)), r=1.8, spec=0.3, shin=14, rim=0.35)
    stri = [[(x + k * 0.9, y) for x, y in stalk[5:-5]] for k in (-1.5, 0, 1.5)]
    cv.paint(cv.lines(stri, 0.18) * m, '#1c3a12', 0.4)
    # thorns on the stalk
    for (x, y), sgn in zip(stalk[8:-8:7], (1, -1, 1, -1, 1, -1, 1)):
        th = cv.poly([(x + sgn * 1.8, y - 0.7), (x + sgn * 1.8, y + 0.7), (x + sgn * 3.6, y - 1.4)])
        cv.shade(th, '#d8d0a0', r=0.25, spec=0.3)
    # a small leaf on the stalk
    plant_leaf(cv, (cx + 3, 44), (cx + 15, 38), 2.4, -2.0, seed=11)
    plant_leaf(cv, (cx + 0, 49), (cx - 11, 44), 2.2, 2.0, seed=12)
    plant_base_leaves(cv, cx, G)
    # ---- the head: two toothed jaws opening to the left
    hx, hy = cx + 7.5, 23.0
    up_outer = bez((hx, hy), (hx + 3, 6), (hx - 12, -1.5), (hx - 27, 6.5), n=50)
    up_inner = bez((hx - 27, 6.5), (hx - 18, 13.5), (hx - 9, 16.5), (hx, hy), n=50)
    lo_outer = bez((hx, hy), (hx + 3, 40), (hx - 16, 41), (hx - 26, 30.5), n=50)
    lo_inner = bez((hx - 26, 30.5), (hx - 17, 25.5), (hx - 9, 24.5), (hx, hy), n=50)
    # throat
    throat = cv.poly(up_inner + lo_inner[::-1])
    cv.paint(throat, Rad(hx - 2, hy, 26, '#060002', '#3a0610', '#8a1622', '#b02a36'))
    cv.paint(cv.feather(cv.ellipse(hx - 4, hy, 9, 4.5), 1.8) * throat, '#000000', 0.8)
    cv.paint(cv.feather(np.clip(cv.tube(up_inner, 5.0, caps=False) + cv.tube(lo_inner, 5.0, caps=False), 0, 1), 1.0) * throat, '#c0303e', 0.5)
    # a saliva strand
    s_ = cv.line(bez((hx - 19.5, 13.6), (hx - 18.0, 20.5), (hx - 18.5, 26.4), n=16), 0.25)
    cv.paint(s_ * throat, '#d8f0b0', 0.45)
    # lips (inner surface of each jaw, pink-red with veins)
    for outer, inner_, sgn in ((up_outer, up_inner, 1), (lo_outer, lo_inner, -1)):
        jaw = cv.poly(outer + inner_)
        cv.shade(jaw, Tex(Lin(hx - 25, hy - 16 * sgn, hx, hy, '#8acc4a', '#4a8a2a', '#22521a'), 0.15, 1.2, 7 + sgn), r=2.2, spec=0.35, shin=14, rim=0.35)
        # purple speckles
        sp = (cv.noise(0.6, 50 + sgn) > 0.7).astype(np.float32)
        cv.paint(cv.feather(sp, 0.12) * jaw, '#5a1a3a', 0.5)
        lip = cv.tube(inner_, 2.8, 2.8, caps=False) * jaw
        cv.shade(lip, Lin(0, hy - 12, 0, hy + 12, '#f05a6a', '#c0202e', '#e04a5a'), r=0.6, spec=0.45, shin=20, rim=0.2)
        cv.paint(cv.lines([[(x, y), (x + 0.8, y + sgn * 1.0)] for x, y in inner_[3:-6:4]], 0.12) * lip, '#7a0a18', 0.6)
        # bristles on the outer rim
        p = np.array(outer)
        segs = []
        for i in range(4, len(outer) - 3, 3):
            d = p[i + 1] - p[i - 1]
            ln = np.hypot(*d)
            nx, ny = d[1] / ln * sgn, -d[0] / ln * sgn
            nx, ny = -nx, -ny
            x, y = p[i]
            segs.append([(x, y), (x + nx * 3.2 - d[0] / ln * 1.0, y + ny * 3.2 - d[1] / ln * 1.0)])
        cv.paint(cv.lines(segs, 0.3), '#a8c060', 1.0)
        cv.paint(cv.lines([[s[0], ((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2)] for s in segs], 0.3), '#4a7a24', 0.6)
    # teeth
    teeth_along(cv, up_inner[2:-6], -1, 3.4, 10, seed=1)
    teeth_along(cv, lo_inner[2:-6], -1, 3.0, 9, seed=2)
    # hinge bulb
    cv.shade(cv.ellipse(hx + 0.5, hy, 3.2, 3.6), Lin(0, hy - 4, 0, hy + 4, '#5a9a34', '#2a5a1c'), r=1.0, spec=0.3)
    return cv


@sprite('plant_cut', 18)
def plant_cut():
    cv = Canvas(50, 20, seed=36)
    cv.ground = 19.0
    G = 19.0
    cx = 25.0
    cv.shadow(cx, G, 19, 1.4, 0.45)
    plant_base_leaves(cv, cx, G, wilt=0.8)
    stalk = bez((cx, G - 0.5), (cx - 1.5, G - 6), (cx + 0.8, G - 10), n=30)
    m = cv.tube(stalk, 6.0, 5.6, caps=False)
    m = m * (1 - cv.poly([(cx - 6, G - 13), (cx + 6, G - 13), (cx + 6, G - 11.4), (cx - 6, G - 9.0)]))
    cv.shade(m, Tex(Lin(cx - 4, 0, cx + 4, 0, '#7a9a40', '#4a6a24', '#28401a'), 0.18, 1.5, 3, aniso=(0.3, 4)), r=1.8, spec=0.25, rim=0.3)
    cv.paint(cv.lines([[(x + k, y) for x, y in stalk[3:-4]] for k in (-1.5, 0, 1.5)], 0.18) * m, '#1c3a12', 0.4)
    # slanted cut face
    face = cv.ellipse(cx + 0.7, G - 10.25, 2.95, 1.25, rot=-0.2)
    cv.shade(face, Rad(cx, G - 10.6, 3.2, '#f2f0c0', '#cfd88a', '#8aa04a'), r=0.5, spec=0.25, rim=0.15)
    ring = ell_pts(cx + 0.7, G - 10.25, 1.9, 0.75, rot=-0.2, n=30)
    for (x, y) in ring[::3]:
        cv.paint(cv.circle(x, y, 0.2), '#7a8a3a', 0.8)
    cv.paint(cv.feather(cv.ellipse(cx + 0.4, G - 10.1, 0.8, 0.35, rot=-0.2), 0.1), '#9aa850', 0.8)
    # oozing sap drip
    d = cv.tube([(cx + 3.4, G - 10.6), (cx + 3.5, G - 7.6)], 0.5, 0.75)
    cv.shade(d, '#c8e070', r=0.2, spec=0.8, shin=30, alpha=0.85)
    # broken drooping tendril
    t = cv.tube(spline([(cx - 2.6, G - 8), (cx - 6, G - 7.5), (cx - 8, G - 4.5), (cx - 7.5, G - 2.2)], n=10), 0.9, 0.35)
    cv.shade(t, '#6a7a30', r=0.3, spec=0.2)
    return cv


BONE = '#e8dcc0'


def bone(cv, a, b, w, knob=1.6):
    m = cv.tube([a, b], w)
    for (x, y) in (a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        m = np.maximum(m, cv.circle(x + nx * w * 0.35, y + ny * w * 0.35, w * knob * 0.42))
        m = np.maximum(m, cv.circle(x - nx * w * 0.35, y - ny * w * 0.35, w * knob * 0.42))
    cv.shade(m, Lin(0, 0, 0, 18, '#f6eedc', BONE, '#a89878'), r=w * 0.45, spec=0.25, shin=14, rim=0.35)
    return m


@sprite('skeleton', 16)
def skeleton():
    cv = Canvas(64, 18, seed=37)
    cv.ground = 17.0
    G = 17.0
    cv.shadow(32, G, 30, 1.6, 0.45)
    rag = Tex('#9a8a5a', 0.3, 0.5, 4)
    # far arm (behind ribs)
    bone(cv, (20.0, 13.8), (26.5, 15.6), 0.9)
    bone(cv, (26.5, 15.6), (31.5, 15.8), 0.8)
    # leg bones (far leg flat, near leg with raised knee)
    bone(cv, (37.5, 14.4), (46.5, 15.2), 1.25)
    bone(cv, (46.5, 15.2), (55.5, 15.6), 1.05)
    for i in range(4):
        bone(cv, (55.8, 15.0 + i * 0.3), (58.6, 14.3 + i * 0.75), 0.45, knob=1.3)
    # ragged shorts remnants
    shorts = cv.poly([(33.0, 10.8), (38.6, 10.5), (42.8, 12.4), (44.0, 15.9), (41.5, 15.0), (40.0, 16.2), (37.6, 15.4), (35.0, 16.4), (33.0, 15.0)])
    cv.shade(shorts, Tex('#8a7a4a', 0.3, 0.4, 6), r=0.9, spec=0.06, tex=0.25, tscale=0.15)
    # pelvis
    pel = cv.poly(spline([(33.0, 10.6), (36.2, 9.6), (38.6, 11.4), (37.0, 13.6), (34.0, 13.4)], n=8, closed=True))
    pel = pel * (1 - cv.ellipse(35.8, 11.7, 0.8, 0.6))
    cv.shade(pel, BONE, r=0.6, spec=0.2, rim=0.4)
    # near leg: femur up to the knee, tibia down to the foot
    bone(cv, (37.0, 12.0), (44.8, 7.6), 1.35)
    bone(cv, (44.8, 7.6), (51.0, 14.6), 1.1)
    cv.shade(cv.ellipse(44.8, 7.8, 0.9, 0.75), '#f0e6cc', r=0.3, spec=0.3)
    for i in range(4):
        bone(cv, (51.2, 14.6 + i * 0.25), (54.6 - i * 0.3, 15.4 + i * 0.4), 0.45, knob=1.3)
    # spine
    for i, x in enumerate(np.arange(23.2, 33.2, 0.95)):
        v = cv.ellipse(x, 13.9 - 0.15 * math.sin(i * 0.6), 0.5, 0.75)
        cv.shade(v, BONE, r=0.25, spec=0.2, rim=0.3)
    # ribcage: arcs rising from the spine
    ribs = []
    for i, x in enumerate(np.arange(21.5, 30.5, 1.25)):
        h = 4.6 - abs(i - 2.5) * 0.45
        ribs.append(bez((x, 13.6), (x - 0.4, 13.6 - h), (x + 2.8, 13.6 - h * 1.05), (x + 3.0, 13.2 - h * 0.25), n=24))
    rm = cv.lines(ribs, 0.55)
    cv.paint(cv.feather(cv.ellipse(26.5, 11.3, 5.5, 2.4), 0.6), '#1a140c', 0.55)
    cv.shade(rm, Lin(0, 8, 0, 14, '#fbf3e0', BONE, '#9a8a6a'), r=0.25, spec=0.3, rim=0.3)
    # tattered shirt over part of the ribs
    shirt = cv.poly([(19.0, 9.6), (24.2, 8.0), (25.6, 9.2), (24.6, 10.8), (25.8, 12.6), (23.4, 12.0), (22.6, 14.6), (20.8, 13.2), (18.6, 14.8)])
    holes = cv.ellipse(21.8, 11.0, 0.8, 0.5)
    cv.shade(shirt * (1 - holes), Tex('#b8a676', 0.3, 0.4, 7), r=0.6, spec=0.06, tex=0.25, tscale=0.15)
    shirt2 = cv.poly([(28.4, 9.8), (31.5, 10.6), (32.8, 13.8), (30.6, 12.8), (29.4, 14.2), (28.8, 12.0)])
    cv.shade(shirt2, Tex('#a89666', 0.3, 0.4, 8), r=0.5, spec=0.06)
    # near arm across the chest, hand on the ground
    bone(cv, (20.6, 11.0), (25.8, 8.6), 0.95)
    bone(cv, (25.8, 8.6), (31.0, 11.4), 0.85)
    for i in range(4):
        bone(cv, (31.2, 11.4 + i * 0.25), (33.0 + i * 0.25, 12.2 + i * 0.5), 0.35, knob=1.3)
    # skull (side view, facing up-left), jaw dropped
    k, ox, oy = 0.74, 19.5, 14.6
    S = lambda pts: [(ox + (x - ox) * k, oy + (y - oy) * k) for x, y in pts]
    skull = cv.poly(S(spline([(12.4, 7.0), (15.0, 5.4), (18.6, 5.8), (20.4, 8.6), (19.8, 11.6), (17.2, 12.8), (14.6, 12.6), (13.4, 11.0), (12.2, 10.2)], n=8, closed=True)))
    cv.shade(skull, Rad(16.0, 9.0, 5.5, '#fbf4e2', BONE, '#a08e6a'), r=1.0, spec=0.3, shin=14, rim=0.35)
    jaw = cv.poly(S([(13.6, 11.6), (17.8, 12.6), (18.4, 14.2), (16.8, 15.4), (13.8, 14.4)]))
    cv.shade(jaw, BONE, r=0.45, spec=0.2, rim=0.4)
    (ex, ey), = S([(14.6, 9.2)])
    cv.paint(cv.ellipse(ex, ey, 1.2 * k, 1.05 * k), '#1a120a')
    cv.paint(cv.poly(S([(12.6, 11.4), (13.4, 11.0), (13.3, 12.2)])), '#1a120a')
    cv.paint(cv.lines([S([(x, 11.4), (x, 12.3)]) for x in np.arange(13.9, 17.2, 0.55)] + [S([(x, 12.9), (x, 13.7)]) for x in np.arange(14.3, 17.2, 0.55)], 0.14), '#5a4a32', 0.7)
    cv.paint(cv.line(S(bez((17.0, 6.2), (18.4, 8.0), (17.0, 9.6), n=12)), 0.1), '#8a7a5a', 0.6)
    # pith helmet beside the skull
    draw_helmet(cv, 7.6, 16.7, 0.8, col='#bfae7c', seed=3)
    return cv


# ---- architecture: grilles, door, well, statues ----------------------------------------------

IRON = Lin(0, 0, 0, 74, '#5a5e66', '#3a3d44', '#24262a')


def arch_top(x, cx, r, spring):
    """y of a semicircular arch (centre cx, radius r, springing line y=spring) at x."""
    dx = np.clip(x - cx, -r, r)
    return spring - math.sqrt(max(r * r - dx * dx, 0.0))


def gate_leaf(cv, M, x0, x1, cx, r, spring, G, bars, cross, bar_w=1.15, col=IRON, rust=0.0, broken=False, seed=0):
    """Iron grille leaf drawn through mapping M (x, y) -> screen; bars at given x, crossbars at given y."""
    rng = np.random.default_rng(seed)
    allm = np.zeros((cv.H, cv.W), np.float32)
    segs = []
    for x in bars:
        top = arch_top(x, cx, r, spring) if r else spring
        ys = np.linspace(top, G, 40)
        segs.append([M(x, y) for y in ys])
    for y in cross:
        xs = [x for x in np.linspace(x0, x1, 60) if (arch_top(x, cx, r, spring) if r else spring) <= y]
        if xs:
            segs.append([M(x, y) for x in xs])
    m = cv.lines(segs, bar_w)
    cv.paint(cv.feather(m, 0.4), (0, 0, 0), 0.0)
    cv.shade(m, col, r=bar_w * 0.4, spec=0.55, shin=22, rim=0.35, tex=0.15 + rust * 0.2, tscale=0.4, tseed=seed)
    # spear points on top of each bar for the arched gate
    return m


def grille_draw(open_):
    cv = Canvas(58, 74, ss=2, seed=40)
    cv.ground = 73.0
    G = 73.0
    cx, r, spring = 29.0, 24.0, 26.0
    x0, x1 = cx - r, cx + r
    bars = list(np.arange(x0 + 3.0, x1 - 1.0, 3.6))
    cross = [16.0, 42.0, 66.0]
    if open_:
        # leaf swung into the tunnel, hinged on the left: foreshortened, far edge smaller
        def M(x, y):
            u = (x - x0) / (x1 - x0)
            hz = 40.0
            return (x0 + u * 19.0, hz + (y - hz) * (1 - 0.2 * u))
    else:
        def M(x, y):
            return (x, y)
    leaf = gate_leaf(cv, M, x0, x1, cx, r, spring, G - 0.8, bars, cross, bar_w=0.8 if open_ else 1.15, seed=1)
    # rivets at the crossings
    riv = []
    for x in bars:
        for y in cross:
            if arch_top(x, cx, r, spring) <= y:
                riv.append(M(x, y))
    for (x, y) in riv:
        cv.shade(cv.circle(x, y, 0.85 if not open_ else 0.5), '#6a6e76', r=0.3, spec=0.7)
    # leaf edge bars (hinge stile and lock stile)
    sw = 1.1 if open_ else 1.5
    stile = cv.lines([[M(x0 + 0.9, max(arch_top(x0 + 0.9, cx, r, spring), 0) + 0.0), M(x0 + 0.9, G - 0.6)],
                      [M(x1 - 0.9, arch_top(x1 - 0.9, cx, r, spring)), M(x1 - 0.9, G - 0.6)]], sw)
    arcpts = [M(x, arch_top(x, cx, r, spring) + 0.9) for x in np.linspace(x0 + 0.9, x1 - 0.9, 80)]
    stile = np.maximum(stile, cv.line(arcpts, sw * 0.93))
    cv.shade(stile, IRON, r=0.6, spec=0.55, shin=22, rim=0.3)
    # lock box on the free stile
    lx, ly = M(x1 - 2.4, 44.0)
    lk = cv.rrect(lx - 2.0, ly - 2.4, lx + 1.6, ly + 2.4, 0.4) if not open_ else cv.rrect(lx - 0.7, ly - 2.0, lx + 0.6, ly + 2.0, 0.3)
    cv.shade(lk, '#4a4c52', r=0.5, spec=0.5)
    if not open_:
        cv.paint(np.maximum(cv.circle(lx - 0.2, ly - 0.5, 0.5), cv.rect(lx - 0.45, ly - 0.4, lx + 0.05, ly + 1.0)), '#060606')
    # fixed frame: the arch band and the threshold
    band = [(x, arch_top(x, cx, r + 1.2, spring)) for x in np.linspace(x0 - 1.2, x1 + 1.2, 120)]
    frame = cv.line([(x0 - 1.2, G)] + band + [(x1 + 1.2, G)], 2.4, caps=False)
    cv.shade(frame, IRON, r=0.9, spec=0.5, shin=20, rim=0.3, tex=0.1, tscale=0.5)
    cv.paint(cv.line([(x0 - 1.6, G - 0.1)] + [(x, y - 0.6) for x, y in band] + [(x1 + 1.6, G - 0.1)], 0.3, caps=False), '#9aa0aa', 0.35)
    sill = cv.rect(x0 - 2.4, G - 1.2, x1 + 2.4, G)
    cv.shade(sill, IRON, r=0.4, spec=0.4)
    # hinges on the left
    for y in (20.0, 60.0):
        hx, hy = M(x0, y)
        cv.shade(cv.rrect(x0 - 2.4, hy - 1.6, x0 + 1.4, hy + 1.6, 0.6), '#4a4c52', r=0.5, spec=0.5)
    # bolts on the frame
    for t in np.linspace(0.06, 0.94, 9):
        x, y = band[int(t * (len(band) - 1))]
        cv.shade(cv.circle(x, y, 0.6), '#7a7e86', r=0.25, spec=0.7)
    return cv


@sprite('grille', 72)
def grille():
    return grille_draw(False)


@sprite('grille_open', 72)
def grille_open():
    return grille_draw(True)


RUST = Lin(0, 0, 0, 74, '#8a4a24', '#6a3418', '#4a2410')


def rusty_draw(broken):
    cv = Canvas(58, 74, ss=2, seed=41)
    cv.ground = 73.0
    G = 73.0
    x0, x1, top = 4.0, 54.0, 3.0
    rng = np.random.default_rng(41)
    bars = list(np.linspace(x0 + 4.5, x1 - 4.5, 8))
    cross = [14.0, 30.0, 47.0, 63.0]
    hcx, hcy = 29.0, 45.0     # centre of the smashed hole

    def bend(x, y):
        if not broken:
            return x, y
        d = x - hcx
        w = math.exp(-((y - hcy) / 13.0) ** 2)
        push = (7.5 if abs(d) < 8 else 3.0 if abs(d) < 14 else 0.6) * w
        return x + math.copysign(push, d if d else 1) + 0.25 * math.sin(y * 0.4), y + (abs(d) < 8) * 1.5 * w

    segs = []
    stubs = []
    for i, x in enumerate(bars):
        ys = np.linspace(top, G - 0.6, 60)
        pts = [bend(x + 0.05 * math.sin(y * 0.12 + i), y) for y in ys]
        if broken and i == 3:
            # snapped bar: two stubs, the lower one bent forward/out
            segs.append([p for p, y in zip(pts, ys) if y < 33])
            lower = [p for p, y in zip(pts, ys) if y > 55]
            segs.append([(lower[0][0] - 2.5, lower[0][1] - 3.0)] + lower)
        else:
            segs.append(pts)
    for j, y in enumerate(cross):
        xs = np.linspace(x0, x1, 80)
        pts = [bend(x, y + 0.06 * math.sin(x * 0.2 + j)) for x in xs]
        if broken and j == 2:
            segs.append([p for p, x in zip(pts, xs) if x < hcx - 6])
            segs.append([p for p, x in zip(pts, xs) if x > hcx + 6])
            stubs.append([(hcx - 6.5 - 7.5, y), (hcx - 4.5 - 7.5, y - 2.5)])
        elif broken and j == 1:
            segs.append([(x, y + max(0, 6 - abs(x - hcx)) * 0.7) for x, y in pts])
        else:
            segs.append(pts)
    m = cv.lines(segs, 1.7)
    if stubs:
        m = np.maximum(m, cv.lines(stubs, 1.6))
    cv.shade(m, Tex(RUST, 0.3, 1.2, 8), r=0.6, spec=0.3, shin=14, rim=0.35, tex=0.2, tscale=0.6, tseed=3)
    flakes = cv.feather((cv.noise(0.9, 51) > 0.7).astype(np.float32), 0.1) * m
    cv.paint(flakes, '#b8642a', 0.55)
    cv.paint(cv.feather((cv.noise(1.1, 52) > 0.74).astype(np.float32), 0.12) * m, '#3a2014', 0.45)
    # rivets
    for x in bars:
        for y in cross:
            px, py = bend(x, y)
            if broken and abs(x - hcx) < 8 and abs(y - hcy) < 10:
                continue
            cv.shade(cv.circle(px, py, 0.95), '#7a3c1a', r=0.3, spec=0.4, tex=0.3, tscale=0.2)
    # heavy frame (set in the rock)
    fr = cv.line([(x0, G), (x0, top + 2.0), (x0 + 2.0, top), (x1 - 2.0, top), (x1, top + 2.0), (x1, G)], 2.8, caps=False)
    cv.shade(fr, Tex(RUST, 0.3, 1.2, 9), r=0.9, spec=0.3, shin=14, rim=0.3, tex=0.2, tscale=0.6, tseed=5)
    cv.paint(cv.feather((cv.noise(0.9, 53) > 0.7).astype(np.float32), 0.1) * fr, '#b8642a', 0.5)
    for y in np.linspace(top + 4, G - 4, 7):
        for x in (x0, x1):
            cv.shade(cv.circle(x, y, 0.8), '#5a2c14', r=0.3, spec=0.3)
    # rust streaks running down
    streak = cv.feather((cv.noise(1.0, 54, (0.15, 4)) > 0.65).astype(np.float32), 0.2) * m
    cv.paint(streak, '#4a1e0c', 0.5)
    if broken:
        # fragments lying at the foot
        for (fx, fy, a, L) in ((22.0, G - 0.8, 0.15, 6.5), (33.5, G - 0.9, -0.3, 4.5), (28.0, G - 0.7, 0.05, 3.0)):
            p = [(fx - L / 2 * math.cos(a), fy - L / 2 * math.sin(a)), (fx + L / 2 * math.cos(a), fy + L / 2 * math.sin(a))]
            frag = cv.line(p, 1.3)
            cv.shade(frag, RUST, r=0.4, spec=0.3, tex=0.4, tscale=0.3)
        # bright fresh metal at the breaks
        for p in (bend(bars[3], 33.0), bend(bars[3], 55.0)):
            cv.paint(cv.circle(p[0], p[1], 0.6), '#c8c0b0', 0.8)
    return cv


@sprite('rusty_grille', 72)
def rusty_grille():
    return rusty_draw(False)


@sprite('rusty_broken', 72)
def rusty_broken():
    return rusty_draw(True)


STONE = Tex(Lin(0, 0, 0, 80, '#a8a296', '#8a8478', '#5e5a52'), 0.15, 1.5, 9)


def stone_blocks(cv, polys, base=STONE, seed=0, jitter=0.12):
    rng = np.random.default_rng(seed)
    for pts in polys:
        m = cv.poly(pts)
        k = rng.uniform(1 - jitter, 1 + jitter)
        tint = mix('#ffffff', ['#c8b8a0', '#a8b0b8', '#b8b0a0'][rng.integers(0, 3)], 0.4)
        col = (lambda b, k, t: (lambda R: field_eval(b, R) * k * t))(base, k, tint)
        cv.shade(m, col, r=0.8, spec=0.08, rim=0.45, tex=0.25, tscale=0.3, tseed=int(rng.integers(0, 50)))


def door_draw(open_):
    cv = Canvas(54, 80, ss=2, seed=42)
    cv.ground = 79.0
    G = 79.0
    cx, r, spring = 27.0, 17.0, 27.0
    x0, x1 = cx - r, cx + r
    # stone frame: jamb blocks and voussoirs
    blocks = []
    y = G
    k = 0
    while y > spring:
        h = 7.5 if k % 2 == 0 else 6.0
        y1 = max(spring, y - h)
        wl = 7.0 if k % 2 == 0 else 5.5
        blocks.append([(x0 - wl, y1 + 0.25), (x0 - 0.2, y1 + 0.25), (x0 - 0.2, y - 0.25), (x0 - wl, y - 0.25)])
        blocks.append([(x1 + 0.2, y1 + 0.25), (x1 + wl, y1 + 0.25), (x1 + wl, y - 0.25), (x1 + 0.2, y - 0.25)])
        y = y1
        k += 1
    nv = 9
    R2 = r + 7.0
    for i in range(nv):
        a0 = math.pi + i * math.pi / nv + 0.012
        a1 = math.pi + (i + 1) * math.pi / nv - 0.012
        pts = [(cx + r * math.cos(a), spring + r * math.sin(a)) for a in np.linspace(a0, a1, 8)]
        pts += [(cx + R2 * math.cos(a), spring + R2 * math.sin(a)) for a in np.linspace(a1, a0, 8)]
        blocks.append(pts)
    cv.paint(cv.feather(cv.poly([(x0 - 7.4, G), (x0 - 7.4, spring)] + [(cx + (R2 + 0.4) * math.cos(a), spring + (R2 + 0.4) * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 60)] + [(x1 + 7.4, spring), (x1 + 7.4, G)]), 0.2), '#2a2620', 0.9)
    stone_blocks(cv, blocks, seed=3)
    # keystone accent
    opening = cv.poly([(x0, G)] + [(cx + r * math.cos(a), spring + r * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 80)] + [(x1, G)])
    if open_:
        cv.paint(opening, Rad(cx, G - 20, 40, '#0a0806', '#000000'))
        # the leaf swung inwards: narrow, foreshortened, darker, hinged on the left
        def M(x, y):
            u = (x - x0) / (x1 - x0)
            hz = 46.0
            return (x0 + u * 9.0, hz + (y - hz) * (1 - 0.16 * u))
        dark = 0.45
    else:
        def M(x, y):
            return (x, y)
        dark = 0.0
    leaf_out = [M(x0, G)] + [M(cx + r * math.cos(a), spring + r * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 80)] + [M(x1, G)]
    leaf = cv.poly(leaf_out)
    wood = Tex(Lin(0, 0, 0, 80, mix('#7a4a26', '#000000', dark), mix('#5a3418', '#000000', dark), mix('#3a200e', '#000000', dark)), 0.3, 1.2, 4, aniso=(0.3, 8))
    cv.shade(leaf, wood, r=0.6, spec=0.08, rim=0.3, tex=0.2, tscale=0.6, tseed=7, aniso=(0.3, 8))
    # planks
    ps = [[M(x, arch_top(x, cx, r, spring)), M(x, G)] for x in np.linspace(x0, x1, 7)[1:-1]]
    cv.paint(cv.lines(ps, 0.35) * leaf, '#1a0c04', 0.85)
    cv.paint(cv.lines([[(a[0] + 0.4, a[1]), (b[0] + 0.4, b[1])] for a, b in ps], 0.2) * leaf, mix('#c08a58', '#000000', dark), 0.35)
    # iron bands with studs
    for yb in (spring - 4.0, 46.0, 70.0):
        xs = [x for x in np.linspace(x0, x1, 40) if arch_top(x, cx, r, spring) < yb - 1.3]
        band = cv.line([M(x, yb) for x in xs], 2.3, caps=False) * leaf
        cv.shade(band, '#3a3836', r=0.5, spec=0.45, shin=20, tex=0.2, tscale=0.4)
        for x in np.linspace(xs[0] + 1.5, xs[-1] - 1.5, 9 if yb > spring else 5):
            px, py = M(x, yb)
            cv.shade(cv.circle(px, py, 0.75 if not open_ else 0.5), '#8a8682', r=0.3, spec=0.7)
    # studs grid between bands
    for yb in (36.0, 58.0):
        for x in np.linspace(x0 + 3, x1 - 3, 6):
            px, py = M(x, yb)
            cv.shade(cv.circle(px, py, 0.6 if not open_ else 0.4), '#6a6662', r=0.25, spec=0.6)
    if not open_:
        # ring handle and lock plate
        cv.shade(cv.rrect(x1 - 7.5, 49.0, x1 - 3.5, 57.0, 0.6), '#3a3836', r=0.5, spec=0.5)
        cv.paint(np.maximum(cv.circle(x1 - 5.5, 53.6, 0.6), cv.poly([(x1 - 5.9, 53.8), (x1 - 5.1, 53.8), (x1 - 4.9, 55.6), (x1 - 6.1, 55.6)])), '#050302')
        ring = cv.circle(x1 - 11.0, 53.0, 2.8) * (1 - cv.circle(x1 - 11.0, 53.0, 2.0))
        cv.paint(cv.feather(cv.circle(x1 - 10.6, 53.6, 2.9), 0.3) * (1 - cv.circle(x1 - 10.6, 53.6, 1.8)), (0, 0, 0), 0.45)
        cv.shade(ring, '#5a5652', r=0.4, spec=0.7, shin=20)
        cv.shade(cv.circle(x1 - 11.0, 50.0, 0.9), '#3a3836', r=0.3, spec=0.5)
    else:
        cv.paint(cv.feather(cv.poly([M(x1, G), M(x1, 30), (x1 - 4, 30), (x1 - 4, G)]), 1.5) * opening, (0, 0, 0), 0.5)
    # threshold stone
    th = cv.rect(x0 - 7.4, G - 1.6, x1 + 7.4, G)
    cv.shade(th, STONE, r=0.5, spec=0.08, rim=0.3, tex=0.25, tscale=0.3)
    return cv


@sprite('door', 78)
def door():
    return door_draw(False)


@sprite('door_open', 78)
def door_open():
    return door_draw(True)


def well_draw(rope):
    cv = Canvas(46, 42, ss=2, seed=43)
    cv.ground = 41.0
    G = 41.0
    cx, rx, ry, top = 23.0, 15.5, 4.2, 21.5
    cv.shadow(cx, G, 18, 2.0, 0.45)
    # posts behind the rim tops
    post_w = 2.2
    for px in (cx - rx + 1.6, cx + rx - 1.6):
        p = cv.rect(px - post_w / 2, 2.4, px + post_w / 2, top + 1.0)
        cv.shade(p, Tex(Lin(px - 1, 0, px + 1, 0, '#a8784a', '#6a4424'), 0.3, 0.8, int(px), aniso=(0.3, 6)), r=0.7, spec=0.1)
    # stone wall (cylinder)
    body = cv.poly(ell_pts(cx, top, rx, ry, n=60, a0=math.pi, a1=2 * math.pi) + ell_pts(cx, G - ry * 0.8, rx, ry * 0.8, n=60, a0=0, a1=math.pi))
    cv.shade(body, '#7a7468', r=2.0, spec=0.05, rim=0.3)
    rng = np.random.default_rng(43)
    rows = 6
    polys = []
    for i in range(rows):
        y0 = top + i * (G - ry * 0.8 - top) / rows
        y1 = top + (i + 1) * (G - ry * 0.8 - top) / rows
        n = 8
        off = (i % 2) * 0.5
        for j in range(n + 1):
            a0 = (j - off) / n * math.pi
            a1 = (j + 1 - off) / n * math.pi
            a0, a1 = max(a0, 0.0), min(a1, math.pi)
            if a1 - a0 < 0.05:
                continue
            g = 0.03
            def P(a, y, yr):
                return (cx - rx * math.cos(a), y + yr * math.sin(a))
            pts = [P(a, y0 + 0.25, ry * (1 - 0.2 * i / rows)) for a in np.linspace(a0 + g, a1 - g, 8)]
            pts += [P(a, y1 - 0.25, ry * (1 - 0.2 * (i + 1) / rows)) for a in np.linspace(a1 - g, a0 + g, 8)]
            polys.append(pts)
    cv.paint(body, '#3a362e', 1.0)
    stone_blocks(cv, polys, base=Tex(Lin(cx - rx, 0, cx + rx, 0, '#b8b2a4', '#9a9486', '#5a564e'), 0.15, 1.5, 9), seed=4, jitter=0.15)
    cv.paint(cv.feather((cv.noise(1.2, 60) > 0.66).astype(np.float32), 0.3) * body, '#4a6a2a', 0.35)
    # rim and dark opening
    rim = cv.ellipse(cx, top, rx + 0.6, ry + 0.5)
    cv.shade(rim, '#a8a294', r=0.6, spec=0.1, rim=0.2, tex=0.2, tscale=0.3)
    hole = cv.ellipse(cx, top + 0.3, rx - 1.6, ry - 1.0)
    cv.paint(hole, Lin(0, top - ry, 0, top + ry, '#000000', '#1a1612'))
    cv.paint(cv.feather(cv.ellipse(cx, top + ry - 1.6, rx - 2.5, 0.8), 0.5) * hole, '#3a342c', 0.6)
    # front parts of the posts (standing on the rim) + crossbeam
    for px in (cx - rx + 1.6, cx + rx - 1.6):
        p = cv.rect(px - post_w / 2, top - 2.0, px + post_w / 2, top + 1.6)
        cv.shade(p, Tex(Lin(px - 1, 0, px + 1, 0, '#a8784a', '#6a4424'), 0.3, 0.8, int(px), aniso=(0.3, 6)), r=0.7, spec=0.1)
        cv.paint(cv.feather(cv.ellipse(px, top + 1.6, 1.6, 0.5), 0.2), (0, 0, 0), 0.4)
    beam = cv.rect(cx - rx - 0.6, 1.2, cx + rx + 0.6, 3.8)
    cv.shade(beam, Tex(Lin(0, 1, 0, 4, '#b8885a', '#6a4424'), 0.3, 1.0, 7, aniso=(8, 0.3)), r=0.6, spec=0.1)
    # little roof braces
    for sgn in (-1, 1):
        br = cv.line([(cx + sgn * (rx - 1.6), 8.5), (cx + sgn * (rx - 6.0), 3.6)], 1.0)
        cv.shade(br, '#7a5030', r=0.3, spec=0.1)
    # pulley: bracket + wheel
    cv.shade(cv.rect(cx - 1.6, 3.4, cx + 1.6, 5.4), '#3a3836', r=0.3, spec=0.5)
    wheel = cv.circle(cx, 7.6, 2.9) * (1 - cv.circle(cx, 7.6, 0.0))
    cv.shade(wheel, '#6a4a2a', r=0.6, spec=0.2)
    cv.paint(cv.circle(cx, 7.6, 2.9) * (1 - cv.circle(cx, 7.6, 2.3)), '#3a2614', 0.8)
    for a in np.linspace(0, math.pi, 3, endpoint=False):
        cv.paint(cv.line([(cx - 2.3 * math.cos(a), 7.6 - 2.3 * math.sin(a)), (cx + 2.3 * math.cos(a), 7.6 + 2.3 * math.sin(a))], 0.35), '#4a3018', 0.9)
    cv.shade(cv.circle(cx, 7.6, 0.7), '#8a8682', r=0.3, spec=0.7)
    if rope:
        rope_path(cv, ell_pts(cx, 7.6, 2.65, 2.65, n=40, a0=math.pi, a1=2 * math.pi), 0.6, '#c8a86c', '#5a4424')
        rope_path(cv, [(cx + 2.65, 7.6), (cx + 2.65, top + 2.2)], 0.65, '#c8a86c', '#5a4424')
        cv.paint(cv.feather(cv.rect(cx + 2.0, top + 0.6, cx + 3.3, top + 2.4), 0.4), '#000000', 0.7)
        rope_path(cv, bez((cx - 2.65, 7.6), (cx - 4.0, 12), (cx - 3.0, 13.6), n=16), 0.6, '#c8a86c', '#5a4424')
    return cv


@sprite('well', 40)
def well():
    return well_draw(False)


@sprite('well_rope', 40)
def well_rope():
    return well_draw(True)


@sprite('statue', 76)
def statue():
    cv = Canvas(40, 78, ss=2, seed=44)
    cv.ground = 77.0
    G = 77.0
    cx = 20.0
    stone = Tex(Lin(0, 0, 40, 78, '#8a8a7e', '#5e6058', '#34362f'), 0.2, 2.0, 11)
    cv.shadow(cx, G, 18, 1.6, 0.5)
    # plinth
    pl = cv.poly([(3, G), (3, 70.5), (5, 68.5), (35, 68.5), (37, 70.5), (37, G)])
    cv.shade(pl, stone, r=1.0, spec=0.06, rim=0.3, tex=0.3, tscale=0.4, tseed=2)
    cv.paint(cv.lines([[(5, 72.5), (35, 72.5)]], 0.3), '#2a2620', 0.5)
    # squat body with short legs and arms hugging the belly
    body = cv.poly(spline([(cx - 11, 69), (cx - 13, 56), (cx - 12, 44), (cx, 40), (cx + 12, 44), (cx + 13, 56), (cx + 11, 69)], n=10))
    cv.shade(body, stone, r=3.0, spec=0.08, rim=0.4, tex=0.3, tscale=0.4, tseed=3)
    belly = cv.ellipse(cx, 58, 6.5, 6.0)
    cv.shade(belly, stone, r=2.0, spec=0.08, rim=0.3, tex=0.3, tscale=0.4, tseed=4)
    cv.paint(cv.circle(cx, 59.5, 0.9), '#2a2620', 0.8)
    for sgn in (-1, 1):
        arm = cv.tube(bez((cx + sgn * 11.5, 46), (cx + sgn * 14.5, 55), (cx + sgn * 9, 60), (cx + sgn * 3, 56), n=30), 4.4, 3.4)
        cv.shade(arm, stone, r=1.4, spec=0.08, rim=0.4, tex=0.3, tscale=0.4, tseed=5)
        hand = cv.ellipse(cx + sgn * 3.6, 55.8, 2.6, 1.9)
        cv.shade(hand, stone, r=0.8, spec=0.08, rim=0.4)
        cv.paint(cv.lines([[(cx + sgn * (2.5 + k), 54.6), (cx + sgn * (2.3 + k), 57.4)] for k in (0, 1.2, 2.4)], 0.25), '#2a2620', 0.6)
        leg = cv.rrect(cx + sgn * 5 - 3.4, 63, cx + sgn * 5 + 3.4, 69.2, 1.2)
        cv.shade(leg, stone, r=1.0, spec=0.06, rim=0.4)
        cv.paint(cv.lines([[(cx + sgn * 5 + k, 67.4), (cx + sgn * 5 + k, 69)] for k in (-1.5, 0, 1.5)], 0.25), '#2a2620', 0.6)
    # the big head
    head = cv.poly(spline([(cx - 13, 40), (cx - 15.5, 26), (cx - 14, 13), (cx - 8, 6.5), (cx, 5), (cx + 8, 6.5), (cx + 14, 13), (cx + 15.5, 26), (cx + 13, 40), (cx, 43)], n=10, closed=True))
    cv.shade(head, stone, r=3.5, spec=0.1, rim=0.4, tex=0.3, tscale=0.4, tseed=6)
    # headdress spikes
    for i, a in enumerate(np.linspace(-1.0, 1.0, 7)):
        bx, by = cx + 11.5 * math.sin(a), 9.5 - 3.8 * math.cos(a)
        tip = (cx + 17 * math.sin(a * 1.1), 6.0 - 6.0 * math.cos(a))
        sp = cv.poly([(bx - 1.8 * math.cos(a), by - 1.8 * math.sin(a) * 0.3), tip, (bx + 1.8 * math.cos(a), by + 1.8 * math.sin(a) * 0.3)])
        cv.shade(sp, stone, r=0.7, spec=0.08, rim=0.4)
    # heavy brow ridge
    # deep socket and the single huge staring eye
    cv.paint(cv.feather(cv.ellipse(cx, 22.0, 8.6, 6.4), 0.6), '#1a1612', 0.9)
    eye = cv.ellipse(cx, 22.2, 7.0, 5.0)
    cv.shade(eye, Rad(cx - 2, 20.5, 8, '#fff8e8', '#e8dcc4', '#9a8a70'), r=1.6, spec=0.4, shin=24, rim=0.3)
    veins = [bez((cx - 6.6, 21 + k), (cx - 5, 21.5 + k * 1.3), (cx - 3.5, 22 + k * 0.4), n=10) for k in (-1.4, 0.2, 1.6)]
    veins += [[(cx + 6.6 - (x - cx + 6.6), y) for x, y in v] for v in veins]
    cv.paint(cv.lines(veins, 0.12) * eye, '#c0302a', 0.55)
    iris = cv.circle(cx + 0.6, 22.6, 3.3)
    cv.glow(iris, '#ff3010', 1.2, 0.5)
    cv.shade(iris, Rad(cx + 0.6, 22.6, 3.3, '#ffd040', '#e05010', '#6a0806'), r=0.8, spec=0.0, rim=0.2)
    cv.paint(cv.ellipse(cx + 0.6, 22.6, 0.85, 2.7), '#080202')
    cv.hl(cx - 1.4, 20.6, 1.1, 0.7, 0.9, soft=0.3)
    # lids
    lid = cv.poly([(cx - 8, 22.0), (cx - 6, 18.4), (cx, 20.6), (cx + 6, 18.4), (cx + 8, 22.0), (cx + 6.5, 19.9), (cx, 22.0), (cx - 6.5, 19.9)])
    cv.shade(lid, stone, r=0.5, spec=0.08, rim=0.3)
    brow = cv.poly([(cx - 13.5, 13.0), (cx - 4, 15.4), (cx, 17.4), (cx + 4, 15.4), (cx + 13.5, 13.0), (cx + 12.5, 16.4), (cx + 4, 18.4), (cx, 19.8), (cx - 4, 18.4), (cx - 12.5, 16.4)])
    cv.paint(cv.feather(cv.poly([(x, y + 1.2) for x, y in [(cx - 12.5, 16.4), (cx - 4, 18.4), (cx, 19.8), (cx + 4, 18.4), (cx + 12.5, 16.4), (cx, 18.0)]]), 0.5), (0, 0, 0), 0.5)
    cv.shade(brow, stone, r=1.0, spec=0.1, rim=0.3)
    # nose and fanged grimace
    nose = cv.poly([(cx - 2.2, 26.8), (cx + 2.2, 26.8), (cx + 3.6, 31.0), (cx - 3.6, 31.0)])
    cv.shade(nose, stone, r=0.7, spec=0.08, rim=0.4)
    cv.paint(np.maximum(cv.ellipse(cx - 1.6, 30.8, 0.9, 0.5), cv.ellipse(cx + 1.6, 30.8, 0.9, 0.5)), '#1a1612')
    mouth = cv.poly(bez((cx - 10, 33.0), (cx - 4, 36.5), (cx + 4, 36.5), (cx + 10, 33.0), n=30) + bez((cx + 9, 34.5), (cx + 4, 41.5), (cx - 4, 41.5), (cx - 9, 34.5), n=30))
    cv.paint(mouth, Lin(0, 33, 0, 41, '#0a0806', '#2a2420'))
    fangs = []
    for i, x in enumerate(np.linspace(cx - 7.5, cx + 7.5, 7)):
        L = 3.2 if i in (1, 5) else 1.8
        yt = 34.0 + 1.3 * (1 - ((x - cx) / 9) ** 2)
        fangs.append([(x - 0.9, yt), (x + 0.9, yt), (x, yt + L)])
        yb = 39.8 - 1.0 * (1 - ((x - cx) / 9) ** 2) + 1.0
        if i % 2 == 0:
            fangs.append([(x - 0.8, yb), (x + 0.8, yb), (x, yb - 1.8)])
    cv.shade(cv.poly(*fangs) * cv.feather(mouth, 0.3), stone, r=0.4, spec=0.1, rim=0.3)
    # ears / side plugs
    for sgn in (-1, 1):
        ear = cv.ellipse(cx + sgn * 15.0, 26.0, 2.2, 4.4)
        cv.shade(ear, stone, r=0.8, spec=0.06, rim=0.4)
        cv.paint(cv.ellipse(cx + sgn * 15.0, 26.0, 0.8, 1.6), '#2a2620', 0.7)
    # carved cheek marks + cracks + moss
    cv.paint(cv.lines([[(cx + s_ * 6, 28), (cx + s_ * 9.5, 30.5)] for s_ in (-1, 1)] + [[(cx + s_ * 6, 30), (cx + s_ * 9.5, 32.5)] for s_ in (-1, 1)], 0.35), '#2a2620', 0.6)
    allm = np.clip(head + body + pl, 0, 1)
    cracks = [bez((cx + 9, 6.8), (cx + 7.5, 10), (cx + 10, 12.5), n=12), bez((cx - 12, 46), (cx - 10, 50), (cx - 12.5, 54), n=12), bez((22, 69), (24, 72), (21.5, 76), n=12)]
    cv.paint(cv.lines(cracks, 0.25) * allm, '#1a1612', 0.7)
    cv.paint(cv.feather((cv.noise(1.6, 70) > 0.68).astype(np.float32), 0.4) * allm, '#4a5a2a', 0.3)
    return cv


def buddha_draw(moved):
    cv = Canvas(70, 94, ss=2, seed=45)
    cv.ground = 93.0
    G = 93.0
    cx = 35.0
    stone = Tex(Lin(10, 0, 60, 93, '#c4bca8', '#9a9282', '#5e584e'), 0.15, 2.0, 13)
    cv.shadow(cx, G, 33, 1.8, 0.5)
    # plinth: two tiers and a lotus band
    t1 = cv.rect(2, 85, 68, G)
    cv.shade(t1, stone, r=1.0, spec=0.05, rim=0.35, tex=0.3, tscale=0.4, tseed=2)
    t2 = cv.rect(6, 77, 64, 85.4)
    cv.shade(t2, stone, r=1.0, spec=0.05, rim=0.35, tex=0.3, tscale=0.4, tseed=3)
    cv.paint(cv.lines([[(2, 85.2), (68, 85.2)], [(6, 77.2), (64, 77.2)]], 0.3), '#2a2620', 0.5)
    petals = []
    for x in np.arange(8.5, 63, 4.4):
        petals.append(spline([(x - 2.0, 84.6), (x - 1.6, 80.4), (x, 78.4), (x + 1.6, 80.4), (x + 2.0, 84.6)], n=6))
    cv.shade(cv.poly(*petals), stone, r=0.6, spec=0.08, rim=0.4)
    # crossed legs
    legs = cv.poly(spline([(8, 78), (9, 70), (18, 63.5), (35, 62), (52, 63.5), (61, 70), (62, 78)], n=10))
    cv.shade(legs, stone, r=3.0, spec=0.08, rim=0.4, tex=0.3, tscale=0.4, tseed=4)
    cv.paint(cv.lines([bez((12, 74), (24, 70), (40, 72.5), n=20), bez((58, 74), (46, 70), (30, 72.5), n=20)], 0.35) * legs, '#2a2620', 0.5)
    for sgn in (-1, 1):
        foot = cv.ellipse(cx + sgn * 9.5, 70.0, 5.2, 2.0, rot=-sgn * 0.12)
        cv.shade(foot, stone, r=0.9, spec=0.08, rim=0.35)
    # torso with robe
    torso = cv.poly(spline([(16, 66), (15, 50), (17, 38), (25, 31.5), (35, 30), (45, 31.5), (53, 38), (55, 50), (54, 66)], n=10))
    cv.shade(torso, stone, r=4.0, spec=0.08, rim=0.4, tex=0.3, tscale=0.4, tseed=5)
    # robe drape over the left shoulder
    drape = [bez((25, 32), (32, 44), (42, 50), (53, 52), n=24), bez((22, 36), (28, 48), (38, 56), (52, 58), n=24), bez((47, 33), (50, 42), (53, 50), n=16)]
    cv.paint(cv.lines(drape, 0.4) * torso, '#2a2620', 0.55)
    cv.paint(cv.lines([[(x + 0.5, y - 0.4) for x, y in d] for d in drape], 0.25) * torso, '#e0dacb', 0.35)
    # arms and hands in the lap (meditation)
    for sgn in (-1, 1):
        arm = cv.tube(bez((cx + sgn * 17.0, 38), (cx + sgn * 21.0, 50), (cx + sgn * 17.0, 61), (cx + sgn * 6.0, 63), n=30), 6.5, 5.0)
        cv.shade(arm, stone, r=2.0, spec=0.08, rim=0.4, tex=0.3, tscale=0.4, tseed=6)
    hands = cv.ellipse(cx, 63.0, 7.0, 2.8)
    cv.shade(hands, stone, r=1.0, spec=0.08, rim=0.4)
    cv.paint(cv.lines([[(cx - 4 + k * 1.6, 61.4), (cx - 4 + k * 1.6, 64.0)] for k in range(6)], 0.2) * hands, '#2a2620', 0.5)
    # neck + head
    neck = cv.rect(cx - 4.2, 26, cx + 4.2, 32)
    cv.shade(neck, stone, r=1.2, spec=0.06, rim=0.4)
    cv.paint(cv.lines([bez((cx - 4, 29), (cx, 30.2), (cx + 4, 29), n=10)], 0.25), '#2a2620', 0.45)
    for sgn in (-1, 1):
        ear = cv.poly(spline([(cx + sgn * 8.6, 13), (cx + sgn * 10.6, 14), (cx + sgn * 10.4, 22), (cx + sgn * 9.6, 27.5), (cx + sgn * 8.4, 26)], n=8))
        cv.shade(ear, stone, r=0.8, spec=0.06, rim=0.4)
    head = cv.poly(spline([(cx - 9, 10), (cx - 9.4, 17), (cx - 7.5, 24.5), (cx, 28.6), (cx + 7.5, 24.5), (cx + 9.4, 17), (cx + 9, 10), (cx, 4.6)], n=10, closed=True))
    cv.shade(head, stone, r=2.6, spec=0.12, rim=0.35, tex=0.25, tscale=0.4, tseed=7)
    # curly hair and ushnisha
    hair = cv.poly(bez((cx - 9.2, 12.4), (cx - 9, 3.4), (cx + 9, 3.4), (cx + 9.2, 12.4), n=30) + bez((cx + 9.2, 12.4), (cx + 4, 9.6), (cx - 4, 9.6), (cx - 9.2, 12.4), n=20))
    cv.shade(hair, stone, r=1.2, spec=0.06, rim=0.3)
    ush = cv.ellipse(cx, 3.6, 4.2, 3.0)
    cv.shade(ush, stone, r=1.0, spec=0.06, rim=0.35)
    curls = []
    rng = np.random.default_rng(45)
    for i in range(80):
        x = rng.uniform(cx - 9, cx + 9)
        y = rng.uniform(1.0, 12)
        curls.append((x, y))
    cm = np.zeros((cv.H, cv.W), np.float32)
    for (x, y) in curls:
        cm = np.maximum(cm, cv.circle(x, y, 0.55))
    cv.shade(cm * np.maximum(hair, ush), stone, r=0.3, spec=0.1, rim=0.5)
    # face: brows, nose, serene mouth, urna
    cv.paint(cv.lines([bez((cx - 7, 15.6), (cx - 4.5, 14.2), (cx - 1.4, 15.2), n=12), bez((cx + 7, 15.6), (cx + 4.5, 14.2), (cx + 1.4, 15.2), n=12)], 0.35), '#3a3630', 0.6)
    nose = cv.poly([(cx - 0.6, 15.8), (cx + 0.6, 15.8), (cx + 1.8, 21.6), (cx - 1.8, 21.6)])
    cv.shade(nose, stone, r=0.5, spec=0.08, rim=0.3)
    cv.paint(cv.line(bez((cx - 2.6, 24.0), (cx, 24.9), (cx + 2.6, 24.0), n=12), 0.3), '#3a3630', 0.7)
    cv.paint(cv.circle(cx, 13.4, 0.5), '#3a3630', 0.6)
    # closed left eye (viewer's left): carved lid
    cv.paint(cv.line(bez((cx - 6.6, 18.2), (cx - 4.4, 19.4), (cx - 2.0, 18.2), n=12), 0.4), '#2a2620', 0.85)
    # the jewel eye (viewer's right): big ruby in a gold setting
    jx, jy = cx + 4.3, 18.3
    cv.glow(cv.circle(jx, jy, 2.4), '#ff2030', 2.0, 0.6)
    cv.shade(cv.ellipse(jx, jy, 3.0, 2.4), '#c8a040', r=0.6, spec=0.7, shin=20)
    gem = cv.ellipse(jx, jy, 2.3, 1.75)
    cv.paint(gem, '#9a0414')
    for k, (a0, c) in enumerate(((0, '#ff4050'), (1, '#c00a20'), (2, '#ff8090'), (3, '#7a0010'), (4, '#e01830'), (5, '#ff5060'))):
        a = a0 * math.pi / 3
        b = (a0 + 1) * math.pi / 3
        cv.paint(cv.poly([(jx, jy), (jx + 2.3 * math.cos(a), jy + 1.75 * math.sin(a)), (jx + 2.3 * math.cos(b), jy + 1.75 * math.sin(b))]) * gem, c, 0.85)
    cv.paint(cv.ellipse(jx, jy, 1.0, 0.75), '#ff3a48', 0.9)
    cv.sparkle(jx - 0.9, jy - 0.7, 2.6, 1.0)
    # weathering: cracks and lichen
    allm = np.clip(head + torso + legs + t1 + t2, 0, 1)
    cracks = [bez((48, 40), (50, 46), (47.5, 52), n=12), bez((14, 86), (16, 89), (13, 92.5), n=12), bez((cx + 7, 7), (cx + 5.6, 9.5), (cx + 7.4, 11), n=8)]
    cv.paint(cv.lines(cracks, 0.25) * allm, '#1a1612', 0.7)
    cv.paint(cv.feather((cv.noise(2.0, 80) > 0.7).astype(np.float32), 0.4) * allm, '#5a6a3a', 0.25)
    if moved:
        # scraped dust and grit at the base after being pushed aside
        for x in (3.5, 66.5):
            cv.paint(cv.feather(cv.ellipse(x, G - 1.2, 3.6, 1.6), 0.8), '#c8b898', 0.55)
        rng = np.random.default_rng(46)
        for i in range(14):
            x = rng.choice([rng.uniform(0.5, 7), rng.uniform(63, 69.5)])
            cv.shade(cv.ellipse(x, G - rng.uniform(0.3, 0.8), rng.uniform(0.3, 0.6), rng.uniform(0.25, 0.4)), '#8a8274', r=0.2, spec=0.1)
        cv.paint(cv.lines([[(8, G - 0.4), (62, G - 0.4)]], 0.25), '#e8dcc0', 0.35)
    return cv


@sprite('buddha', 92)
def buddha():
    return buddha_draw(False)


@sprite('buddha_moved', 92)
def buddha_moved():
    return buddha_draw(True)


@sprite('ghost', 64)
def ghost():
    cv = Canvas(48, 68, ss=3, seed=50)
    cv.ground = 66.5
    lay = cv.layer()
    outline = [(24, 1.5), (31, 3.6), (34.6, 10.5), (35.2, 15.6), (40.5, 16.6), (46.2, 17.8), (42.6, 20.4), (45.4, 22.8), (40.0, 23.0), (35.4, 25.6),
               (36.0, 36.0), (38.4, 46.0), (40.6, 56.0), (38.6, 65.6), (33.6, 58.6), (29.6, 66.2), (25.0, 59.0), (20.0, 66.0), (15.6, 58.6),
               (10.2, 64.8), (10.6, 54.6), (12.6, 44.0), (13.6, 34.6), (12.4, 26.4), (7.6, 25.4), (2.4, 26.8), (4.6, 23.4), (1.4, 20.4),
               (8.0, 18.0), (13.2, 15.6), (13.6, 10.0), (17.2, 3.6)]
    body = lay.poly(spline(outline, n=10, closed=True))
    body = lay.feather(body, 0.35)
    lay.shade(body, Lin(0, 0, 0, 66, '#ffffff', '#dff0ff', '#a8c8f0'), r=3.0, spec=0.15, rim=0.25, amb=0.6, diff=0.5)
    # inner folds / wisps
    folds = [bez((20, 30), (18, 42), (19, 52), (17, 60), n=20), bez((28, 30), (30, 42), (29, 52), (31, 60), n=20), bez((24, 36), (24.5, 46), (23.5, 56), n=16)]
    lay.paint(lay.feather(lay.lines(folds, 0.7), 0.5) * body, '#8aa8d8', 0.45)
    lay.paint(lay.feather(lay.lines([bez((15, 18), (20, 22), (24, 20), n=12), bez((33, 18), (29, 22), (25, 20), n=12)], 0.5), 0.4) * body, '#9ab8e0', 0.35)
    # hollow, slanted eyes and a wailing mouth
    for sgn in (-1, 1):
        e = lay.poly(rot_pts(ell_pts(24 + sgn * 4.6, 12.8, 3.0, 2.0, n=40), -sgn * 0.42, 24 + sgn * 4.6, 12.8))
        lay.paint(lay.feather(e, 0.25), '#0a1030', 0.95)
        lay.paint(lay.feather(lay.circle(24 + sgn * 4.2, 13.2, 0.7), 0.3), '#6ae8ff', 0.9)
    mouth = lay.poly(spline([(24, 17.6), (26.8, 19.4), (27.0, 23.6), (24, 25.6), (21.0, 23.6), (21.2, 19.4)], n=8, closed=True))
    lay.paint(lay.feather(mouth, 0.3), Lin(0, 18, 0, 25, '#0a1030', '#1a2a5a'), 0.95)
    # fade towards the tattered bottom, then overall ~60% opacity
    fade = np.clip(1.0 - np.clip((np.arange(cv.H)[:, None] / cv.u - 40) / 30, 0, 1) * 0.75, 0, 1).astype(np.float32)
    lay.img *= fade[..., None]
    halo = cv.layer()
    halo.paint(np.clip(blur(body, 1.4 * cv.u), 0, 1) * fade, '#b8e4ff', 0.35)
    cv.over(halo, 1.0)
    cv.over(lay, 0.62)
    # eyes stay a bit more solid
    for sgn in (-1, 1):
        cv.glow(cv.circle(24 + sgn * 4.2, 13.2, 0.5), '#a8f4ff', 0.4, 0.5)
    return cv


def fur(cv, m, n, length, angle, seed, light='#6a625c', dark='#0c0a09', edge=True):
    cv.hairs(m, n, length, 0.16, light, seed=seed, angle=angle, jitter=0.35, clip=m, alpha=0.4)
    cv.hairs(m, n // 2, length, 0.16, dark, seed=seed + 1, angle=angle, jitter=0.35, clip=m, alpha=0.5)
    if edge:
        rim = np.clip(m - cv.feather(m, 0.6) * 0.0 - np.clip((blur(m, 0.6 * cv.u) - 0.5) * 2.2, 0, 1), 0, 1)
        cv.hairs(rim, n // 6, length * 0.8, 0.18, '#2a2624', seed=seed + 2, angle=angle, jitter=0.6, alpha=0.9)


@sprite('gorilla', 84)
def gorilla():
    cv = Canvas(68, 88, ss=2, seed=51)
    cv.ground = 86.0
    G = 86.0
    cx = 34.0
    FUR = Rad(cx - 8, 30, 60, '#4a4440', '#2a2624', '#141210')
    SKIN = '#3c3836'
    down = lambda x, y: math.pi / 2 + (x - cx) * 0.012
    cv.shadow(cx, G, 24, 2.0, 0.5)
    # legs
    for sgn in (-1, 1):
        leg = cv.tube(bez((cx + sgn * 8, 62), (cx + sgn * 15, 70), (cx + sgn * 14, 80), (cx + sgn * 12.5, 83), n=30), 13, 9)
        cv.shade(leg, FUR, r=3.0, spec=0.1, rim=0.4)
        fur(cv, leg, 900, 1.6, down, 10 + sgn)
        foot = cv.poly(spline([(cx + sgn * 6.5, G), (cx + sgn * 7.5, 81.5), (cx + sgn * 13, 80.5), (cx + sgn * 19.5, 82.6), (cx + sgn * 20.5, G)], n=8))
        cv.shade(foot, SKIN, r=1.2, spec=0.3, rim=0.3)
        cv.paint(cv.lines([[(cx + sgn * x, 84.0), (cx + sgn * x, G)] for x in (15.0, 16.8, 18.6)], 0.25), '#141210', 0.7)
    # torso
    torso = cv.poly(spline([(cx, 13), (cx + 13, 15.5), (cx + 23, 21.5), (cx + 25, 30), (cx + 21, 45), (cx + 17, 59), (cx + 12, 68), (cx, 71),
                            (cx - 12, 68), (cx - 17, 59), (cx - 21, 45), (cx - 25, 30), (cx - 23, 21.5), (cx - 13, 15.5)], n=10, closed=True))
    cv.shade(torso, FUR, r=5.0, spec=0.12, rim=0.4)
    fur(cv, torso, 5000, 2.0, lambda x, y: math.pi / 2 + (x - cx) * 0.03, 20)
    # bare chest
    for sgn in (-1, 1):
        pec = cv.ellipse(cx + sgn * 7.0, 38.5, 7.4, 6.2, rot=sgn * 0.15)
        cv.shade(pec, Rad(cx + sgn * 7 - 2, 36, 9, '#5a5450', SKIN, '#1e1c1a'), r=2.4, spec=0.18, shin=10, rim=0.3)
    belly = cv.feather(cv.ellipse(cx, 55, 10, 9), 1.5)
    cv.paint(belly, '#4a4440', 0.35)
    cv.hairs(cv.ellipse(cx, 55, 10, 9), 900, 1.6, 0.16, '#6a625c', seed=77, angle=lambda x, y: math.pi / 2 + (x - cx) * 0.06, jitter=0.35, alpha=0.4)
    # arms: shoulder -> elbow (out and down) -> fist on the chest
    for sgn in (-1, 1):
        up = cv.tube(bez((cx + sgn * 20, 24), (cx + sgn * 28.5, 30), (cx + sgn * 30, 42), (cx + sgn * 27.5, 50), n=30), 13, 10.5)
        cv.shade(up, FUR, r=3.2, spec=0.12, rim=0.4)
        fur(cv, up, 1400, 1.8, lambda x, y, s=sgn: math.pi / 2 - s * 0.35, 30 + sgn)
        fore = cv.tube(bez((cx + sgn * 27.5, 50), (cx + sgn * 24, 52), (cx + sgn * 15, 46), (cx + sgn * 10.5, 39.5), n=30), 11, 9.5)
        cv.shade(fore, FUR, r=3.0, spec=0.12, rim=0.4)
        fur(cv, fore, 1100, 1.6, lambda x, y, s=sgn: math.pi + (0.6 if s > 0 else -0.6) * -1 if s < 0 else -0.6, 40 + sgn)
        # fist: knuckles towards the centre, fingers curled, thumb on top
        fx, fy = cx + sgn * 8.4, 37.4
        fist = cv.rrect(fx - 5.2, fy - 4.6, fx + 5.2, fy + 4.4, 2.2)
        fist = np.maximum(fist, cv.ellipse(fx + sgn * 3.4, fy + 1.6, 3.6, 3.6))
        cv.paint(cv.feather(cv.rrect(fx - 5.0, fy - 4.0, fx + 5.6, fy + 5.4, 2.2), 0.6), (0, 0, 0), 0.45)
        cv.shade(fist, Rad(fx - 2, fy - 3, 9, '#6a6460', SKIN, '#1c1a18'), r=1.4, spec=0.3, shin=14, rim=0.35)
        for k in range(4):
            ky = fy - 3.4 + k * 2.25
            kn = cv.ellipse(fx - sgn * 4.2, ky, 1.6, 1.15)
            cv.shade(kn, '#5a5450', r=0.5, spec=0.35, rim=0.3)
            cv.paint(cv.line([(fx - sgn * 4.6, ky + 1.1), (fx + sgn * 1.2, ky + 1.1)], 0.28), '#121010', 0.75)
        thumb = cv.tube([(fx + sgn * 2.4, fy - 4.6), (fx - sgn * 2.0, fy - 3.6)], 2.2, 1.8)
        cv.shade(thumb, '#4e4844', r=0.6, spec=0.3, rim=0.3)
    # impact marks by the fists (chest beating)
    for sgn in (-1, 1):
        for k, (dx_, dy_) in enumerate(((16.5, 30.5), (17.6, 35.5), (15.6, 26.6))):
            seg = [(cx + sgn * dx_, dy_), (cx + sgn * (dx_ + 2.6), dy_ - 1.0 + k * 0.6)]
            cv.paint(cv.line(seg, 0.45), '#fff4d0', 0.75)
    # head
    head = cv.poly(spline([(cx, 1.0), (cx + 6, 3.4), (cx + 9.6, 9.6), (cx + 10.2, 17), (cx + 7.6, 25.6), (cx, 28.6),
                           (cx - 7.6, 25.6), (cx - 10.2, 17), (cx - 9.6, 9.6), (cx - 6, 3.4)], n=10, closed=True))
    cv.shade(head, FUR, r=2.6, spec=0.12, rim=0.4)
    fur(cv, head, 900, 1.2, lambda x, y: math.atan2(y - 14, x - cx), 50)
    face = cv.poly(spline([(cx, 8.5), (cx + 6.4, 9.6), (cx + 7.4, 15), (cx + 6.6, 22.5), (cx, 27.2), (cx - 6.6, 22.5), (cx - 7.4, 15), (cx - 6.4, 9.6)], n=10, closed=True))
    cv.shade(face, Rad(cx - 2, 14, 12, '#5e5854', '#3a3634', '#1a1816'), r=1.6, spec=0.35, shin=16, rim=0.3)
    # angry brow ridge
    brow = cv.poly([(cx - 7.6, 10.4), (cx - 2.0, 12.4), (cx, 13.6), (cx + 2.0, 12.4), (cx + 7.6, 10.4), (cx + 7.0, 12.6), (cx + 2.0, 14.4), (cx, 15.2), (cx - 2.0, 14.4), (cx - 7.0, 12.6)])
    for sgn in (-1, 1):
        sock = cv.ellipse(cx + sgn * 3.6, 15.0, 2.0, 1.2, rot=-sgn * 0.3)
        cv.paint(sock, '#0c0a08')
        cv.paint(cv.ellipse(cx + sgn * 3.4, 15.1, 0.9, 0.7), '#a0281a', 0.95)
        cv.paint(cv.circle(cx + sgn * 3.4, 15.1, 0.38), '#000000')
        cv.hl(cx + sgn * 3.4 - 0.3, 14.8, 0.25, 0.2, 0.95, soft=0.2)
    cv.paint(cv.feather(cv.poly([(x, y + 1.0) for x, y in [(cx - 7.0, 12.6), (cx - 2.0, 14.4), (cx, 15.2), (cx + 2.0, 14.4), (cx + 7.0, 12.6), (cx, 14.2)]]), 0.3), (0, 0, 0), 0.5)
    cv.shade(brow, '#3e3a38', r=0.8, spec=0.3, rim=0.3)
    # nose
    nose = cv.poly(spline([(cx - 1.4, 15.6), (cx + 1.4, 15.6), (cx + 3.6, 18.8), (cx + 2.4, 20.0), (cx - 2.4, 20.0), (cx - 3.6, 18.8)], n=6, closed=True))
    cv.shade(nose, '#4a4542', r=0.8, spec=0.4, rim=0.3)
    for sgn in (-1, 1):
        cv.paint(cv.ellipse(cx + sgn * 1.6, 19.0, 0.9, 0.6, rot=sgn * 0.4), '#0a0808')
    # roaring mouth with big canines
    mouth = cv.poly(spline([(cx - 5.2, 21.0), (cx, 20.6), (cx + 5.2, 21.0), (cx + 4.4, 25.0), (cx, 27.0), (cx - 4.4, 25.0)], n=8, closed=True))
    cv.paint(mouth, Lin(0, 21, 0, 27, '#1a0606', '#5a1418'))
    cv.paint(cv.ellipse(cx, 25.6, 3.0, 1.2) * mouth, '#b04a54', 0.9)
    teeth = [[(cx - 4.0, 21.0), (cx - 2.8, 21.0), (cx - 3.3, 23.9)], [(cx + 4.0, 21.0), (cx + 2.8, 21.0), (cx + 3.3, 23.9)],
             [(cx - 3.6, 26.0), (cx - 2.6, 26.0), (cx - 3.0, 23.6)], [(cx + 3.6, 26.0), (cx + 2.6, 26.0), (cx + 3.0, 23.6)],
             [(cx - 2.4, 20.9), (cx + 2.4, 20.9), (cx + 2.4, 21.7), (cx - 2.4, 21.7)]]
    cv.shade(cv.poly(*teeth) * cv.feather(mouth, 0.1), '#f0e8d0', r=0.25, spec=0.4, rim=0.2)
    return cv


@sprite('sage', 58)
def sage():
    cv = Canvas(54, 60, ss=2, seed=52)
    cv.ground = 59.0
    G = 59.0
    cx = 27.0
    ROBE = Lin(0, 20, 0, 59, '#c0603a', '#9a3c22', '#5a1e10')
    SHAWL = Lin(0, 20, 0, 59, '#e8b050', '#c88a2a', '#7a4e14')
    SKINC = '#c89068'
    BEARD = Lin(0, 14, 0, 46, '#ffffff', '#e8e6e0', '#b8b4ac')
    cv.shadow(cx, G, 24, 1.8, 0.5)
    # crossed legs
    legs = cv.poly(spline([(cx - 23, G), (cx - 24, 53), (cx - 19, 46.5), (cx - 8, 43.5), (cx + 8, 43.5), (cx + 19, 46.5), (cx + 24, 53), (cx + 23, G)], n=10))
    cv.shade(legs, ROBE, r=3.0, spec=0.1, rim=0.35, tex=0.12, tscale=0.6)
    cv.paint(cv.lines([bez((cx - 20, 55), (cx - 8, 50), (cx + 6, 52.5), n=20), bez((cx + 20, 55), (cx + 9, 50.5), (cx - 3, 54), n=20), bez((cx - 15, 49), (cx - 6, 47), (cx + 2, 48.5), n=12)], 0.35) * legs, '#3a1208', 0.55)
    for sgn in (-1, 1):
        foot = cv.poly(spline([(cx + sgn * 4, 52.5), (cx + sgn * 9, 50.6), (cx + sgn * 14, 51.4), (cx + sgn * 13, 53.6), (cx + sgn * 6, 54.2)], n=6, closed=True))
        cv.shade(foot, SKINC, r=0.8, spec=0.2, rim=0.3)
        cv.paint(cv.lines([[(cx + sgn * (5.0 + k * 0.8), 52.4), (cx + sgn * (4.4 + k * 0.8), 53.6)] for k in range(3)], 0.15) * foot, '#7a4a2a', 0.6)
    # torso
    torso = cv.poly(spline([(cx - 8, 19.5), (cx - 13, 23), (cx - 15, 33), (cx - 15.5, 46), (cx, 48), (cx + 15.5, 46), (cx + 15, 33), (cx + 13, 23), (cx + 8, 19.5)], n=10))
    cv.shade(torso, ROBE, r=3.5, spec=0.1, rim=0.35, tex=0.12, tscale=0.6)
    shawl = cv.poly([(cx - 9, 19.8), (cx - 3.5, 19.5), (cx + 15.4, 40), (cx + 15.6, 46.5), (cx + 9, 47.6)])
    cv.shade(shawl * torso, SHAWL, r=1.6, spec=0.1, rim=0.3, tex=0.12, tscale=0.6)
    cv.paint(cv.lines([bez((cx - 4, 22), (cx + 4, 31), (cx + 13, 41), n=16), bez((cx - 7, 23), (cx + 1, 34), (cx + 10, 45), n=16)], 0.3) * shawl * torso, '#6a4010', 0.5)
    # arms in wide sleeves, hands on the knees (mudra)
    for sgn in (-1, 1):
        sl = cv.tube(bez((cx + sgn * 12, 23.5), (cx + sgn * 17, 30), (cx + sgn * 18.5, 38), (cx + sgn * 17.5, 45.5), n=30), 7.6, 8.6)
        cv.shade(sl, SHAWL if sgn > 0 else ROBE, r=2.2, spec=0.1, rim=0.35, tex=0.12, tscale=0.6)
        cv.paint(cv.lines([bez((cx + sgn * 14, 30), (cx + sgn * 16.5, 36), (cx + sgn * 16, 43), n=12)], 0.3) * sl, '#3a1208', 0.4)
        hand = cv.poly(spline([(cx + sgn * 14.6, 45.6), (cx + sgn * 19.4, 45.0), (cx + sgn * 21.6, 47.4), (cx + sgn * 19.4, 49.6), (cx + sgn * 15.0, 49.0)], n=6, closed=True))
        cv.shade(hand, SKINC, r=0.9, spec=0.2, rim=0.3)
        ring = cv.circle(cx + sgn * 20.2, 46.4, 1.0) * (1 - cv.circle(cx + sgn * 20.2, 46.4, 0.45))
        cv.shade(ring, SKINC, r=0.3, spec=0.2)
        cv.paint(cv.lines([[(cx + sgn * 16.5, 46.4), (cx + sgn * 16.0, 48.6)], [(cx + sgn * 17.6, 46.2), (cx + sgn * 17.2, 48.6)]], 0.14) * hand, '#7a4a2a', 0.6)
    # prayer beads hanging from the right hand
    for k in range(9):
        a = math.pi * (0.1 + 0.8 * k / 8)
        x, y = cx + 18.0 + 2.6 * math.cos(a), 49.0 + 3.0 * math.sin(a)
        cv.shade(cv.circle(x, y, 0.55), '#5a2a14', r=0.25, spec=0.5)
    # head
    for sgn in (-1, 1):
        ear = cv.ellipse(cx + sgn * 6.4, 13.2, 1.3, 2.3)
        cv.shade(ear, SKINC, r=0.6, spec=0.15, rim=0.3)
    head = cv.poly(spline([(cx, 3.0), (cx + 5.4, 4.8), (cx + 6.6, 10.5), (cx + 5.8, 16.5), (cx, 20), (cx - 5.8, 16.5), (cx - 6.6, 10.5), (cx - 5.4, 4.8)], n=10, closed=True))
    cv.shade(head, Rad(cx - 2, 6, 10, '#f0c09a', SKINC, '#7a4a2e'), r=2.0, spec=0.35, shin=16, rim=0.3)
    cv.hl(cx - 2.2, 5.4, 1.8, 1.0, 0.45, rot=-0.4)
    cv.paint(cv.lines([bez((cx - 3.5, 7.6 + k * 1.0), (cx, 7.0 + k * 1.0), (cx + 3.5, 7.6 + k * 1.0), n=12) for k in range(3)], 0.14) * head, '#8a5a3a', 0.6)
    # wisps of hair at the temples
    for sgn in (-1, 1):
        w = cv.poly(spline([(cx + sgn * 5.6, 8.4), (cx + sgn * 7.8, 10.6), (cx + sgn * 7.6, 15.6), (cx + sgn * 6.0, 14.6), (cx + sgn * 5.8, 11.0)], n=6, closed=True))
        cv.shade(w, BEARD, r=0.5, spec=0.1, rim=0.3)
    # bushy brows, closed eyes, nose
    for sgn in (-1, 1):
        b = cv.poly(spline([(cx + sgn * 0.8, 10.6), (cx + sgn * 3.6, 9.6), (cx + sgn * 5.8, 11.4), (cx + sgn * 3.6, 11.4)], n=6, closed=True))
        cv.shade(b, BEARD, r=0.4, spec=0.1, rim=0.2)
        cv.paint(cv.line(bez((cx + sgn * 1.4, 12.6), (cx + sgn * 2.8, 13.3), (cx + sgn * 4.2, 12.6), n=10), 0.22), '#4a2a18', 0.85)
    nose = cv.poly([(cx - 0.6, 11.8), (cx + 0.6, 11.8), (cx + 1.5, 15.6), (cx, 16.2), (cx - 1.5, 15.6)])
    cv.shade(nose, SKINC, r=0.6, spec=0.3, rim=0.3)
    # beard and moustache
    beard = cv.poly(spline([(cx - 5.4, 14.2), (cx - 2.0, 16.6), (cx + 2.0, 16.6), (cx + 5.4, 14.2), (cx + 6.4, 20), (cx + 5.6, 28), (cx + 3.4, 36),
                            (cx + 1.6, 42.5), (cx, 45.4), (cx - 1.6, 42.0), (cx - 3.8, 35.6), (cx - 5.8, 27.6), (cx - 6.6, 20)], n=10, closed=True))
    cv.paint(cv.feather(cv.poly([(x + 1.0, y + 1.0) for x, y in spline([(cx - 5.4, 14.2), (cx + 5.4, 14.2), (cx + 6.4, 20), (cx + 3.4, 36), (cx, 45.4), (cx - 3.8, 35.6), (cx - 6.6, 20)], n=8, closed=True)]), 0.8), (0, 0, 0), 0.35)
    cv.shade(beard, BEARD, r=2.2, spec=0.15, rim=0.3)
    rng = np.random.default_rng(52)
    strands = []
    for i in range(26):
        x0 = rng.uniform(cx - 5.4, cx + 5.4)
        strands.append(bez((x0, 16.5 + rng.uniform(0, 3)), (x0 * 0.85 + cx * 0.15 + rng.uniform(-1.5, 1.5), 28), (cx + (x0 - cx) * 0.25 + rng.uniform(-1, 1), 40 + rng.uniform(-3, 4)), n=16))
    cv.paint(cv.lines(strands, 0.14) * beard, '#9a968e', 0.6)
    cv.paint(cv.lines([[(x + 0.25, y) for x, y in s_] for s_ in strands[::2]], 0.12) * beard, '#ffffff', 0.6)
    mous = cv.poly(spline([(cx, 16.0), (cx + 2.6, 16.4), (cx + 4.8, 18.6), (cx + 5.4, 22.4), (cx + 3.6, 19.6), (cx, 18.2), (cx - 3.6, 19.6), (cx - 5.4, 22.4), (cx - 4.8, 18.6), (cx - 2.6, 16.4)], n=6, closed=True))
    cv.shade(mous, BEARD, r=0.6, spec=0.15, rim=0.3)
    cv.paint(cv.ellipse(cx, 19.0, 1.0, 0.35), '#5a2a1a', 0.7)
    return cv


# ---- big set pieces --------------------------------------------------------------------------

DRAGON = Lin(0, 0, 100, 112, '#5aa846', '#3a8a30', '#1e5a1c')
DRAGON_DARK = Lin(0, 0, 100, 112, '#3a7a30', '#24561e', '#123a12')
BELLY = '#e2d27a'
IVORY = '#efe6c8'


def path_normals(path):
    p = np.array(path, np.float64)
    d = np.gradient(p, axis=0)
    ln = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)
    return p, d / ln[:, None], np.stack([-d[:, 1] / ln, d[:, 0] / ln], 1)


def spines(cv, path, widths, side, every, size, col='#d8b444', start=0.0, end=1.0):
    """Triangular spikes along one edge of a tube (side=+1/-1 picks the edge)."""
    p, t, n = path_normals(path)
    N = len(p)
    polys = []
    for i in range(int(start * N), int(end * N), every):
        w = widths[i] / 2
        base = p[i] + n[i] * side * w * 0.85
        s = size * (0.6 + 0.4 * math.sin(math.pi * i / N))
        tip = base + n[i] * side * s - t[i] * s * 0.5
        polys.append([tuple(base - t[i] * s * 0.45), tuple(tip), tuple(base + t[i] * s * 0.45)])
    m = cv.poly(*polys)
    cv.shade(m, col, r=0.4, spec=0.3, rim=0.3)
    return m


def belly_plates(cv, path, widths, side, frac=0.42, col=BELLY, every=3, clip=None):
    """Pale ridged plates along one side of a tube."""
    p, t, n = path_normals(path)
    left = [tuple(p[i] + n[i] * side * widths[i] / 2 * 1.0) for i in range(len(p))]
    inner = [tuple(p[i] + n[i] * side * widths[i] / 2 * (1 - 2 * frac)) for i in range(len(p))]
    m = cv.poly(left + inner[::-1])
    if clip is not None:
        m = m * clip
    cv.shade(m, Lin(0, 0, 0, 112, '#f4e8a8', col, '#a89040'), r=0.9, spec=0.3, rim=0.3)
    segs = [[tuple(p[i] + n[i] * side * widths[i] / 2 * 1.05), tuple(p[i] + n[i] * side * widths[i] / 2 * (1 - 2 * frac))] for i in range(2, len(p) - 1, every)]
    cv.paint(cv.lines(segs, 0.3) * m, '#7a6428', 0.6)
    return m


def wing(cv, shoulder, wrist, tips, body_pt, col, bone, seed=0):
    pts = [shoulder, wrist]
    prev = wrist
    for i, tip in enumerate(tips):
        if i > 0:
            a = tips[i - 1]
            mid = ((a[0] + tip[0]) / 2, (a[1] + tip[1]) / 2)
            ctrl = (mid[0] + (wrist[0] - mid[0]) * 0.32, mid[1] + (wrist[1] - mid[1]) * 0.32)
            pts += bez(a, ctrl, tip, n=16)[1:]
        else:
            pts.append(tip)
    last = tips[-1]
    mid = ((last[0] + body_pt[0]) / 2, (last[1] + body_pt[1]) / 2)
    ctrl = (mid[0] + (wrist[0] - mid[0]) * 0.3, mid[1] + (wrist[1] - mid[1]) * 0.3)
    pts += bez(last, ctrl, body_pt, n=16)[1:]
    mem = cv.poly(pts)
    cv.shade(mem, col, r=2.5, spec=0.15, rim=0.25, amb=0.5, tex=0.12, tscale=1.0, tseed=seed)
    veins = []
    for tip in tips:
        veins.append(bez(wrist, ((wrist[0] + tip[0]) / 2 + 1, (wrist[1] + tip[1]) / 2 + 1), tip, n=20))
    arm = cv.tube([shoulder, ((shoulder[0] + wrist[0]) / 2 + 1.5, (shoulder[1] + wrist[1]) / 2), wrist], 3.0, 2.0)
    fingers = cv.lines(veins, 1.0)
    cv.shade(np.maximum(arm, fingers), bone, r=0.6, spec=0.3, rim=0.3)
    cv.shade(cv.circle(*wrist, 1.9), bone, r=0.6, spec=0.3)
    claw = cv.poly([(wrist[0] - 1, wrist[1] - 1), (wrist[0] - 3.4, wrist[1] - 3.6), (wrist[0] + 0.6, wrist[1] - 1.8)])
    cv.shade(claw, IVORY, r=0.3, spec=0.4)
    return mem


def smoke(cv, puffs, alpha=0.55, seed=0):
    lay = cv.layer()
    m = np.zeros((cv.H, cv.W), np.float32)
    for (x, y, r) in puffs:
        m = np.maximum(m, cv.circle(x, y, r))
    m = lay.feather(m, 0.5)
    lay.shade(m, Lin(0, 0, 0, 30, '#d8d8d4', '#9a9a96', '#5a5a58'), r=1.6, spec=0.0, rim=0.15, amb=0.65, diff=0.45, tex=0.25, tscale=0.8, tseed=seed)
    cv.over(lay, alpha)


@sprite('dragon', 112)
def dragon():
    cv = Canvas(108, 116, ss=2, seed=60)
    cv.ground = 114.0
    G = 114.0
    cv.shadow(66, G, 36, 2.6, 0.5)
    # far wing, just showing above the back
    wing(cv, (60, 50), (66, 14), [(58, 2), (72, 4), (78, 12)], (66, 46), DRAGON_DARK, '#244a1a', seed=1)
    # far hind leg
    fl = cv.tube(spline([(72, 92), (79, 100), (76, 108), (79, 112.4)], n=10), 8, 5)
    cv.shade(fl, DRAGON_DARK, r=2.0, spec=0.2, rim=0.3)
    cv.shade(cv.ellipse(81.5, 112.2, 4.5, 1.6), DRAGON_DARK, r=0.6)
    # tail sweeping along the ground and curling up
    tail = spline([(64, 92), (78, 101), (92, 106), (103, 102), (105, 93), (100, 87.5)], n=14)
    tw = np.linspace(13, 2.0, len(tail))
    tm = cv.tube(tail, 0, widths=tw)
    cv.shade(tm, scales_field(DRAGON, k=1.6, amt=0.14), r=2.4, spec=0.3, shin=14, rim=0.35)
    spines(cv, tail, tw, -1, 6, 2.8, start=0.05, end=0.95)
    spade = cv.poly([(100.5, 88.5), (96.5, 82.0), (101.0, 84.0), (104.5, 81.0), (102.5, 88.0)])
    cv.shade(spade, '#2a6a24', r=0.6, spec=0.3)
    # near wing, half open behind the body
    wing(cv, (58, 50), (80, 16), [(103, 4), (106, 30), (99, 52)], (72, 66), Lin(60, 10, 100, 60, '#4a9a5a', '#2e7040', '#1c4a2a'), '#2a5a22', seed=2)
    # torso, rising from the haunches to the chest
    torso = bez((66, 94), (64, 80), (56, 66), (48, 56), n=40)
    bw = np.linspace(31, 20, len(torso))
    bm = cv.tube(torso, 0, widths=bw)
    cv.shade(bm, scales_field(DRAGON, k=1.6, amt=0.14), r=4.5, spec=0.25, shin=12, rim=0.4)
    spines(cv, torso, bw, 1, 5, 3.6, end=0.72)
    belly_plates(cv, torso, bw, -1, frac=0.3)
    # neck: S-curve up to the head
    neck = spline([(48, 58), (40, 46), (43, 34), (37, 24), (29, 19)], n=12)
    nw = np.linspace(18, 10, len(neck))
    nm = cv.tube(neck, 0, widths=nw)
    cv.shade(nm, scales_field(DRAGON, k=1.8, amt=0.14), r=3.0, spec=0.25, shin=12, rim=0.4)
    spines(cv, neck, nw, 1, 4, 3.0, end=0.9)
    belly_plates(cv, neck, nw, -1, frac=0.32, every=3)
    # near hind leg: big thigh, shin, clawed foot
    thigh = cv.ellipse(63, 93, 11, 9.5, rot=-0.5)
    cv.shade(thigh, scales_field(DRAGON, k=1.6, amt=0.14), r=3.2, spec=0.3, shin=12, rim=0.4)
    shin = cv.tube(spline([(60, 98), (54, 104), (57, 110), (56, 112.5)], n=10), 7, 5)
    cv.shade(shin, DRAGON, r=1.8, spec=0.3, rim=0.35)
    foot = cv.poly(spline([(48, G), (50, 110.5), (56, 109.6), (61, 111), (62, G)], n=6))
    cv.shade(foot, DRAGON, r=1.0, spec=0.3)
    for x in (47.0, 51.0, 55.0):
        cv.shade(cv.poly([(x + 1.6, 111.2), (x + 1.8, G), (x - 1.8, G - 0.1)]), IVORY, r=0.3, spec=0.5)
    # arms raised, clawed hands spread
    def arm(pts, w0, w1, col, hand, claw_col, k):
        m = cv.tube(spline(pts, n=10), w0, w1)
        cv.shade(m, col, r=1.6, spec=0.3, rim=0.35)
        hx_, hy_ = hand
        palm = cv.ellipse(hx_, hy_, w1 * 0.75, w1 * 0.6)
        cv.shade(palm, col, r=0.8, spec=0.3, rim=0.3)
        for j in range(4):
            a_ = -2.1 - 0.5 * k + j * 0.42
            bx_, by_ = hx_ + w1 * 0.55 * math.cos(a_), hy_ + w1 * 0.5 * math.sin(a_)
            c1 = (bx_ + 2.6 * math.cos(a_), by_ + 2.6 * math.sin(a_))
            tip = (c1[0] + 2.2 * math.cos(a_ - 0.9), c1[1] + 2.2 * math.sin(a_ - 0.9))
            cl = cv.tube(bez((bx_, by_), c1, tip, n=12), 1.3, 0.12)
            cv.shade(cl, claw_col, r=0.3, spec=0.6, rim=0.2)
    arm([(53, 60), (47, 70), (39, 70), (34, 63)], 6.0, 4.6, DRAGON_DARK, (33.6, 62.4), '#c8bc98', 1)
    arm([(52, 68), (47, 80), (38, 80), (31, 73)], 7.2, 5.4, DRAGON, (30.6, 72.4), IVORY, 0)
    # ---- head (facing left), jaws open
    hx, hy = 21.0, 18.0
    # mouth interior
    cv.paint(cv.poly([(26, 20.5), (9.0, 19.6), (6.8, 26.8), (24, 24.6)]), Lin(0, 19, 0, 27, '#3a0606', '#8a1618'))
    # lower jaw
    lj = cv.poly(spline([(29, 21.5), (20, 24.4), (10, 26.6), (6.4, 27.6), (7.2, 29.4), (16, 28.8), (26, 27.4), (31, 24.6)], n=8, closed=True))
    cv.shade(lj, DRAGON, r=1.2, spec=0.3, rim=0.35)
    cv.paint(cv.poly([(26.0, 27.0), (16, 28.6), (7.8, 29.2), (7.2, 28.2), (16, 27.2)]), BELLY, 0.6)
    # skull + snout
    sk = cv.poly(spline([(33, 16), (30, 10.4), (24, 9.0), (16, 10.8), (8, 13.0), (3.4, 15.4), (3.6, 18.6), (8, 20.2), (16, 20.6), (25, 21.6), (31, 21.6)], n=8, closed=True))
    cv.shade(sk, scales_field(Rad(18, 11, 18, '#7ac060', '#3f8f34', '#1e5a1c'), k=2.2, amt=0.12), r=2.0, spec=0.35, shin=14, rim=0.35)
    # teeth
    tt = []
    for x in np.arange(6.0, 24.0, 2.0):
        y = 19.6 + (x - 6) * 0.06
        tt.append([(x - 0.6, y), (x + 0.6, y), (x + 0.1, y + 1.9 + (x < 9) * 0.8)])
    for x in np.arange(8.0, 24.0, 2.3):
        y = 26.6 - (x - 8) * 0.05
        tt.append([(x - 0.6, y), (x + 0.6, y), (x - 0.1, y - 1.7)])
    cv.shade(cv.poly(*tt), IVORY, r=0.25, spec=0.5, rim=0.2)
    # horns and brow spikes
    for (base, ctrl, tip, w) in (((29, 11.5), (36, 6), (42, 3.5), 2.4), ((25.5, 10.0), (29, 3), (34, 0.6), 2.0)):
        h = cv.tube(bez(base, ctrl, tip, n=20), w, 0.2)
        cv.shade(h, Lin(base[0], base[1], tip[0], tip[1], '#c8b890', IVORY, '#fffbe8'), r=0.6, spec=0.5, rim=0.3)
    jaw_sp = cv.poly([(30.5, 19.5), (36.5, 21.5), (31, 22.6)], [(28.5, 23.5), (33.8, 27.0), (28.0, 26.0)])
    cv.shade(jaw_sp, '#d8b444', r=0.4, spec=0.3)
    # brow ridge and fierce eye
    cv.paint(cv.feather(cv.poly([(16, 12.2), (24, 11.0), (27, 13.8), (19, 14.4)]), 0.3), (0, 0, 0), 0.45)
    eye = cv.ellipse(21.6, 13.6, 2.1, 1.2, rot=0.2)
    cv.glow(eye, '#ffb020', 0.8, 0.6)
    cv.shade(eye, Rad(21.2, 13.3, 2.4, '#fff07a', '#ffb81e', '#c85a08'), r=0.4, spec=0.2, rim=0.1)
    cv.paint(cv.ellipse(21.8, 13.6, 0.38, 1.05), '#100400')
    cv.hl(21.0, 13.1, 0.4, 0.25, 0.9, soft=0.2)
    brow = cv.poly([(15.6, 11.6), (25.6, 10.0), (28.0, 11.6), (24.6, 12.4), (17.0, 13.0)])
    cv.shade(brow, '#2e7a28', r=0.5, spec=0.3)
    cv.paint(cv.ellipse(6.2, 15.4, 1.0, 0.55, rot=-0.3), '#0a1a06')
    # smoke curling from the nostrils
    smoke(cv, [(4.0, 12.4, 2.0), (2.6, 9.0, 2.8), (4.4, 5.0, 3.4), (8.6, 2.6, 3.0), (2.4, 2.6, 2.4), (12.8, 1.8, 2.2), (6.4, 9.2, 1.8)], alpha=0.8, seed=3)
    return cv


@sprite('dragon_dead', 30)
def dragon_dead():
    cv = Canvas(110, 32, ss=2, seed=61)
    cv.ground = 31.0
    G = 31.0
    cv.shadow(56, G, 48, 2.2, 0.5)
    # dark stain where the head was
    cv.paint(cv.feather(cv.ellipse(11, G - 1.2, 9, 1.6), 0.8), '#1e0806', 0.7)
    # tail
    tail = spline([(76, 26), (90, 28.5), (102, 29.0), (108, 27.6)], n=14)
    tw = np.linspace(10, 1.5, len(tail))
    cv.shade(cv.tube(tail, 0, widths=tw), scales_field(DRAGON, k=1.6, amt=0.14), r=2.0, spec=0.25, rim=0.35)
    spines(cv, tail, tw, -1, 5, 2.2, col='#b09a44')
    # far legs sticking out limply
    cv.shade(cv.tube(spline([(66, 22), (74, 16), (79, 13.5)], n=8), 5, 3.4), DRAGON_DARK, r=1.2, spec=0.2)
    for k in range(3):
        cv.shade(cv.poly([(79 + k * 0.8, 12.6 + k), (82.5 + k * 0.6, 10.8 + k * 1.4), (80.2 + k * 0.8, 14.2 + k)]), '#c8bc98', r=0.3)
    # body lying on its side, belly towards us
    body = cv.poly(spline([(26, 27), (32, 15), (48, 9.5), (66, 10.5), (80, 18.5), (84, 27), (80, G), (30, G)], n=10, closed=True))
    cv.shade(body, scales_field(DRAGON, k=1.6, amt=0.14), r=5.0, spec=0.25, rim=0.4)
    bel = cv.poly(bez((28, 28.6), (40, 21.4), (64, 20.6), (82, 27.4), n=30) + [(82, G), (28, G)])
    cv.shade(bel * body, Lin(0, 20, 0, 31, '#f0e2a0', BELLY, '#9a8440'), r=1.2, spec=0.25, rim=0.2)
    cv.paint(cv.lines([[(x, 21.6 + abs(x - 52) * 0.12), (x + 0.4, G)] for x in np.arange(31, 81, 2.4)], 0.28) * bel * body, '#7a6428', 0.55)
    # crumpled wing on top
    wing_pts = [(40, 12), (46, 2.4), (52, 9.4), (58, 1.0), (63, 9.6), (70, 4.4), (72, 13.6), (60, 16), (46, 16)]
    wm = cv.poly(wing_pts)
    cv.shade(wm, Lin(40, 0, 72, 16, '#4a9a5a', '#2e7040', '#1c4a2a'), r=1.6, spec=0.15, rim=0.3, tex=0.12, tscale=1.0)
    cv.shade(cv.lines([[(48, 15), (46, 2.4)], [(52, 15), (58, 1.0)], [(60, 15), (70, 4.4)]], 0.9), '#2a5a22', r=0.4, spec=0.3)
    # spines along the back
    back = spline([(30, 16), (44, 9.4), (60, 8.8), (76, 14), (84, 24)], n=12)
    spines(cv, back, np.full(len(back), 1.0), -1, 5, 2.8, col='#b09a44')
    # near legs limp with claws
    leg = cv.tube(spline([(70, 25), (77, 28.6), (84, 29.8)], n=8), 6.0, 4.0)
    cv.shade(leg, DRAGON, r=1.4, spec=0.25)
    for k in range(3):
        cv.shade(cv.poly([(84 + k * 0.3, 28.6 + k * 0.6), (88.4, 28.4 + k * 1.2), (84.4, 30.0 + k * 0.4)]), IVORY, r=0.3)
    arm = cv.tube(spline([(34, 25), (30, 28.6), (24, 29.6)], n=8), 4.0, 3.0)
    cv.shade(arm, DRAGON, r=1.0, spec=0.25)
    for k in range(3):
        cv.shade(cv.poly([(24.4, 28.6 + k * 0.6), (20.4, 28.0 + k * 1.1), (24.0, 30.2)]), IVORY, r=0.3)
    # neck stretched out to the left, ending in a dark severed stump
    neck = spline([(34, 20), (24, 21.0), (16, 24.6), (11, 26.4)], n=12)
    nw = np.linspace(12, 8.0, len(neck))
    nm = cv.tube(neck, 0, widths=nw, caps=False)
    cv.shade(nm, scales_field(DRAGON, k=1.8, amt=0.14), r=2.0, spec=0.25, rim=0.35)
    belly_plates(cv, neck, nw, -1, frac=0.3, every=3)
    spines(cv, neck, nw, 1, 4, 2.2, col='#b09a44', end=0.85)
    stump = cv.ellipse(10.6, 26.6, 1.7, 3.9, rot=0.35)
    cv.shade(stump, Rad(7.4, 27.0, 3.4, '#6a1a14', '#3a0a08', '#1a0404'), r=0.6, spec=0.2, rim=0.2)
    cv.paint(cv.ellipse(10.5, 26.2, 0.6, 1.4, rot=0.35), '#d8c8a8', 0.6)
    # closed eye on the far leg? no: a final wisp of smoke from the stump area
    smoke(cv, [(8.4, 21.0, 1.4), (7.0, 18.0, 1.7), (8.6, 15.0, 1.5)], alpha=0.35, seed=4)
    return cv


HELI = Lin(0, 20, 0, 100, '#f2c040', '#d89a1c', '#8a5a0c')


@sprite('helicopter', 96)
def helicopter():
    cv = Canvas(164, 100, ss=2, seed=62)
    cv.ground = 98.0
    G = 98.0
    cv.shadow(76, G, 58, 3.2, 0.45)
    GREY = Lin(0, 20, 0, 80, '#7a7e84', '#4a4e54', '#26282c')
    # far skid + struts
    far = cv.tube([(52, 88.5), (122, 87.2)], 1.5)
    cv.shade(far, '#5a5e64', r=0.5, spec=0.5)
    for x in (62.0, 108.0):
        cv.shade(cv.tube([(x, 88.3), (x + 2, 70.0)], 1.4), '#4a4e54', r=0.4, spec=0.4)
    # tail boom: open lattice truss tapering to the tail rotor
    tops = [(94, 40.0), (150, 33.0)]
    bots = [(94, 58.0), (150, 38.5)]
    fars = [(98, 46.0), (150, 35.2)]
    def L(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    segs = [tops, bots, fars]
    ts = np.linspace(0, 1, 11)
    for i in range(len(ts) - 1):
        segs.append([L(*tops, ts[i]), L(*bots, ts[i + 1])])
        segs.append([L(*bots, ts[i + 1]), L(*tops, ts[i + 1])])
        segs.append([L(*fars, ts[i]), L(*bots, ts[i])])
    truss = cv.lines(segs, 0.9)
    cv.shade(truss, HELI, r=0.4, spec=0.35, rim=0.3)
    # tail rotor gearbox, fin and two-blade rotor
    gb = cv.ellipse(151.5, 35.6, 3.0, 2.6)
    cv.shade(gb, GREY, r=0.8, spec=0.4)
    fin = cv.poly([(146, 38.0), (152, 37.4), (151, 45.6), (148, 44.6)])
    cv.shade(fin, HELI, r=0.6, spec=0.3)
    guard = cv.line(bez((140, 40.8), (146, 50), (153, 47.5), (152.5, 42), n=20), 0.7)
    cv.shade(guard, '#6a6e74', r=0.25, spec=0.5)
    blades = cv.lines([[(153.5, 35.6), (155.6, 22.6)], [(153.5, 35.6), (151.6, 48.6)]], 1.3)
    cv.shade(blades, Lin(0, 22, 0, 49, '#e8e8e8', '#5a5e64', '#e8e8e8'), r=0.4, spec=0.5)
    cv.paint(cv.lines([[(155.4, 23.6), (155.7, 22.4)], [(151.7, 47.6), (151.5, 48.8)]], 1.4), '#d03020', 0.9)
    cv.shade(cv.circle(153.5, 35.6, 1.0), '#3a3e44', r=0.3, spec=0.6)
    # engine / transmission block behind the cabin
    eng = cv.poly([(76, 32), (100, 34), (102, 60), (78, 64)])
    cv.shade(eng, GREY, r=1.2, spec=0.4, rim=0.3, tex=0.2, tscale=0.4)
    cv.paint(cv.lines([[(82, y), (99, y + 0.6)] for y in np.arange(44, 58, 1.6)], 0.4) * eng, '#16181a', 0.6)
    for (x, y) in ((86, 50), (93, 51)):
        cv.shade(cv.circle(x, y, 2.4), '#8a8e94', r=0.6, spec=0.6)
    # saddle fuel tanks
    for (x0, y0, dy) in ((80, 34.5, 0), (84, 31.5, 0)):
        tank = cv.rrect(x0, y0, x0 + 20, y0 + 6.2, 3.0)
        cv.shade(tank, HELI, r=1.6, spec=0.45, shin=16, rim=0.3)
        cv.paint(cv.lines([[(x0 + 5, y0 + 0.4), (x0 + 5, y0 + 5.8)], [(x0 + 15, y0 + 0.4), (x0 + 15, y0 + 5.8)]], 0.35) * tank, '#5a3a08', 0.7)
    # mast + rotor head
    mast = cv.rect(84.6, 13, 87.4, 33)
    cv.shade(mast, GREY, r=0.6, spec=0.5)
    cv.shade(cv.rrect(81.5, 22.5, 90.5, 25.5, 1.0), GREY, r=0.6, spec=0.5)
    cv.shade(cv.lines([[(80, 21.0), (92, 20.4)]], 0.9), '#3a3e44', r=0.3, spec=0.5)
    for x in (80.0, 92.0):
        cv.shade(cv.circle(x, 20.7, 1.2), '#5a5e64', r=0.4, spec=0.5)
    # main rotor blades (long, drooping slightly)
    rotor = cv.poly([(86, 12.2), (6, 18.6), (4.6, 20.4), (86, 14.6)], [(86, 12.2), (160, 6.6), (161, 8.2), (86, 14.6)])
    cv.shade(rotor, Lin(0, 6, 0, 21, '#8a8e94', '#3a3e44', '#1e2024'), r=0.5, spec=0.5, rim=0.2)
    cv.paint(cv.poly([(6, 18.6), (12, 18.1), (11.8, 20.0), (4.6, 20.4)], [(160, 6.6), (155, 7.0), (155.2, 8.5), (161, 8.2)]), '#e8c020', 0.95)
    cv.shade(cv.ellipse(86, 13.4, 3.6, 2.2), '#2e3034', r=0.6, spec=0.6)
    # cabin floor / chin and the frame under the bubble
    chin = cv.poly(spline([(32, 62), (52, 68), (82, 70), (100, 62), (100, 56), (82, 64), (52, 63), (36, 58)], n=8, closed=True))
    cv.shade(chin, HELI, r=1.4, spec=0.4, rim=0.3)
    # near skid + struts
    for (a, b) in (((44, 95.2), (50, 66.0)), ((98, 94.4), (94, 63.0))):
        cv.shade(cv.tube([a, b], 1.8), '#4a4e54', r=0.5, spec=0.5)
    skid = cv.tube([(28, 93.0), (32, 95.6), (118, 94.2)], 2.0)
    cv.shade(skid, '#6a6e74', r=0.6, spec=0.6)
    cv.shade(cv.tube(bez((28, 93.0), (24, 92.6), (22.6, 90.0), n=10), 2.0), '#6a6e74', r=0.6, spec=0.6)
    # the bubble: inside first (seat, stick, console), then glass with reflections
    bub = cv.ellipse(56, 46, 24.5, 22.5)
    cv.paint(bub, Lin(0, 24, 0, 68, '#1a2a36', '#0e161e'), 0.85)
    seat = cv.rrect(58, 48, 82, 60, 2.0)
    cv.shade(seat * bub, '#8a5a3a', r=1.2, spec=0.2)
    cv.shade(cv.rrect(60, 40, 80, 50, 2.0) * bub, '#9a6a44', r=1.0, spec=0.2)
    cv.shade(cv.tube([(52, 64), (48, 52)], 0.8) * bub, '#2a2a2a', r=0.3, spec=0.4)
    cv.shade(cv.rrect(38, 54, 50, 64, 1.5) * bub, '#3a3e44', r=0.8, spec=0.3)
    for (x, y) in ((41.5, 57.5), (46.5, 57.5)):
        cv.paint(cv.circle(x, y, 1.3), '#e8e8d8', 0.8)
        cv.paint(cv.line([(x, y), (x + 0.8, y - 0.8)], 0.2), '#1a1a1a', 0.9)
    glass = cv.layer()
    glass.shade(bub, Rad(46, 34, 30, '#e8f8ff', '#9ad0ec', '#4a88b0'), r=5.0, spec=0.6, shin=10, rim=0.2, amb=0.7, diff=0.4)
    cv.over(glass, 0.42)
    cv.hl(44, 32, 9, 4.6, 0.55, rot=-0.6, soft=0.5)
    cv.hl(38.5, 46, 2.0, 7.0, 0.35, rot=0.2, soft=0.5)
    cv.paint(cv.line(bez((70, 30), (76, 36), (78, 46), n=12), 0.8), '#ffffff', 0.4)
    # bubble frame: rim and centre bow
    cv.shade(cv.line(ell_pts(56, 46, 24.5, 22.5, n=90, a0=math.pi * 0.55, a1=math.pi * 2.25), 1.0, caps=False), '#2e3034', r=0.3, spec=0.5)
    cv.shade(cv.line(bez((40, 29), (34, 46), (46, 66), n=20), 0.8), '#2e3034', r=0.3, spec=0.5)
    cv.shade(cv.line(bez((32, 54), (52, 60), (78, 60), n=20), 1.0), '#2e3034', r=0.3, spec=0.5)
    # small marker lights
    cv.glow(cv.circle(31.5, 57, 0.8), '#ff3020', 0.6, 0.8)
    cv.shade(cv.circle(31.5, 57, 0.8), '#ff3020', r=0.3, spec=0.8)
    return cv


def palm_draw(coconuts):
    cv = Canvas(84, 128, ss=2, seed=63)
    cv.ground = 126.5
    G = 126.5
    bx = 44.0
    cv.anchor = bx
    rng = np.random.default_rng(63)
    crown = (39.0, 25.0)

    def frond(ang, L, droop, w, col0, col1, seed, lift=0.25):
        a = math.radians(ang)
        d = (math.cos(a), math.sin(a))
        p0 = crown
        p1 = (crown[0] + d[0] * L * 0.45, crown[1] + d[1] * L * 0.45 - L * lift)
        p2 = (crown[0] + d[0] * L, crown[1] + d[1] * L + droop)
        path = bez(p0, p1, p2, n=50)
        P, T, N = path_normals(path)
        r_ = np.random.default_rng(seed)
        polys = []
        for i in range(5, len(P) - 1, 1):
            t = i / (len(P) - 1)
            ll = w * (0.35 + 0.65 * math.sin(math.pi * min(1.0, t * 1.1)) ** 0.6)
            for side in (-1, 1):
                dx_, dy_ = T[i] * 0.55 + N[i] * side * 0.85
                dy_ += 0.55
                ln = math.hypot(dx_, dy_)
                dx_, dy_ = dx_ / ln, dy_ / ln
                jitter = r_.uniform(0.85, 1.15)
                tip = (P[i][0] + dx_ * ll * jitter, P[i][1] + dy_ * ll * jitter)
                b0 = P[i] - T[i] * 0.5
                b1 = P[i] + T[i] * 0.5
                px_, py_ = -dy_, dx_
                m0 = (P[i][0] + dx_ * ll * 0.45 * jitter - px_ * 0.5, P[i][1] + dy_ * ll * 0.45 * jitter - py_ * 0.5)
                m1 = (P[i][0] + dx_ * ll * 0.45 * jitter + px_ * 0.5, P[i][1] + dy_ * ll * 0.45 * jitter + py_ * 0.5)
                polys.append([tuple(b0), m0, tip, m1, tuple(b1)])
        m = cv.poly(*polys)
        cv.shade(m, Lin(crown[0], crown[1], p2[0], p2[1], col0, col1), r=0.5, spec=0.25, shin=12, rim=0.3, tex=0.12, tscale=0.8, tseed=seed)
        cv.paint(cv.line(path[2:], 0.55), mix(col1, '#e8e0a0', 0.4), 0.85)
        return m

    back = [(-100, 28, 2, 8.5), (-55, 33, 4, 9.0), (-140, 33, 4, 9.0), (-20, 38, 10, 9.5), (-165, 38, 10, 9.5)]
    for i, (a, L, dr, w) in enumerate(back):
        frond(a, L, dr, w, '#2a5a1c', '#6a9a3a', 10 + i, lift=0.18)
    # trunk
    trunk = bez((bx, G + 0.2), (bx - 4, 96), (bx + 4, 58), (crown[0], crown[1] + 2), n=80)
    tw = np.linspace(6.6, 3.8, len(trunk))
    tw[:6] += np.linspace(2.6, 0, 6)
    tm = cv.tube(trunk, 0, widths=tw)
    cv.shade(tm, Tex(Lin(bx - 4, 0, bx + 4, 0, '#b8a07a', '#8a7454', '#4a3c2c'), 0.25, 0.8, 5, aniso=(0.5, 3)), r=1.4, spec=0.1, rim=0.35)
    P, T, N = path_normals(trunk)
    rings = []
    for i in range(3, len(P) - 2, 2):
        w = tw[i] / 2
        rings.append(bez(tuple(P[i] - N[i] * w), tuple(P[i] + T[i] * 0.5), tuple(P[i] + N[i] * w), n=8))
    cv.paint(cv.lines(rings, 0.28) * tm, '#3a2c1c', 0.6)
    cv.paint(cv.lines([[(x - 0.2, y - 0.3) for x, y in r_] for r_ in rings], 0.15) * tm, '#e8d4a8', 0.35)
    # roots
    for dx_ in (-4.5, -2.0, 2.4, 4.8):
        cv.shade(cv.tube([(bx + dx_ * 0.6, G - 2.2), (bx + dx_ * 1.3, G - 0.1)], 1.2, 0.8), '#6a5a44', r=0.4, spec=0.1)
    # crown boss + a dry hanging frond
    frond(100, 26, 6, 5.0, '#6a5a2a', '#a88a4a', 30, lift=-0.05)
    cv.shade(cv.ellipse(crown[0], crown[1] + 1, 4.0, 3.2), '#5a6a2a', r=1.0, spec=0.2, tex=0.3, tscale=0.3)
    # front fronds drooping towards us
    front = [(10, 37, 15, 9.0), (170, 37, 15, 9.0), (45, 30, 16, 8.5), (135, 30, 16, 8.5), (78, 24, 12, 7.5), (108, 24, 12, 7.5)]
    for i, (a, L, dr, w) in enumerate(front):
        frond(a, L, dr, w, '#3a7a24', '#9ac44a', 20 + i, lift=0.32)
    if coconuts:
        nuts = [(-3.8, 4.6), (0.2, 5.2), (4.0, 4.4), (-2.0, 8.2), (2.2, 8.6), (-5.6, 7.6), (5.4, 7.6), (0.2, 11.2)]
        for i, (dx_, dy_) in enumerate(sorted(nuts, key=lambda p: p[1])):
            x, y = crown[0] + dx_ * 1.1, crown[1] + dy_ + 3.5
            nut = cv.ellipse(x, y, 2.6, 2.8, rot=dx_ * 0.08)
            cv.shade(nut, Rad(x - 0.9, y - 1.0, 3.8, '#c0a050', '#7a6a28', '#3a2e10'), r=1.0, spec=0.4, shin=16, rim=0.3)
            cv.paint(cv.circle(x + dx_ * 0.1, y - 2.0, 0.5), '#4a3a1a', 0.8)
    return cv


@sprite('palm', 124)
def palm():
    return palm_draw(True)


@sprite('palm_bare', 124)
def palm_bare():
    return palm_draw(False)


# ---- app icon masters ----------------------------------------------------------------------------

def _canvas_image(cv, size, opaque):
    chans = [np.asarray(Image.fromarray(np.ascontiguousarray(cv.img[..., i])).resize((size, size), Image.LANCZOS)) for i in range(4)]
    out = np.stack(chans, -1)
    al = np.clip(out[..., 3:], 0, 1)
    rgb = np.where(al > 1e-4, out[..., :3] / np.maximum(al, 1e-4), 0)
    if opaque:
        return Image.fromarray((np.clip(out[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8))
    return Image.fromarray((np.concatenate([np.clip(rgb, 0, 1), al], -1) * 255 + 0.5).astype(np.uint8))


def icon_diamond(cv, cx, cy, s, rays=True):
    """Diamond centred on (cx, cy) (its bounding box), with glow and light rays."""
    top = cy - 1.65 * s / 2
    if rays:
        lay = cv.layer()
        polys = []
        for i in range(12):
            a = i * math.pi / 6 + 0.13
            w = 0.05 if i % 2 else 0.09
            L = s * (1.5 if i % 2 else 1.95)
            polys.append([(cx, cy), (cx + L * math.cos(a - w), cy + L * math.sin(a - w)), (cx + L * math.cos(a + w), cy + L * math.sin(a + w))])
        m = lay.feather(lay.poly(*polys), s * 0.03)
        fade = Rad(cx, cy, s * 1.9, '#ffffff', '#000000')
        lay.paint(m, '#dff4ff', 1.0)
        R = Region(lay, slice(0, lay.H), slice(0, lay.W))
        lay.img *= field_eval(fade, R)[..., :1]
        cv.over(lay, 0.45)
    if rays:
        cv.glow(cv.circle(cx, cy, s * 0.9), '#bfe8ff', s * 0.35, 0.55)
    else:
        cv.glow(cv.circle(cx, cy, s * 0.75), '#bfe8ff', s * 0.12, 0.3)
    draw_diamond(cv, cx, top, s, glow=False, sparkles=False, edge=0.035)
    cv.sparkle(cx - 0.45 * s, top + 0.1 * s, (0.7 if rays else 0.5) * s, 1.0)
    cv.sparkle(cx + 0.55 * s, top + 0.6 * s, 0.42 * s, 0.95, ang=0.3)
    cv.sparkle(cx - 0.05 * s, top + 1.25 * s, 0.28 * s, 0.85)


def make_icons():
    os.makedirs('art', exist_ok=True)
    # ---- full icon: night/dusk island with volcano, the diamond in front
    cv = Canvas(128, 128, ss=2, seed=99)
    full = np.ones((cv.H, cv.W), np.float32)
    cv.paint(full, Lin(0, 0, 0, 100, (0.0, '#060a2c'), (0.4, '#221a5c'), (0.66, '#5a2478'), (0.84, '#c0487a'), (1.0, '#f08a6a')))
    rng = np.random.default_rng(99)
    for i in range(70):
        x, y = rng.uniform(0, 128), rng.uniform(0, 70)
        r_ = rng.uniform(0.18, 0.5)
        cv.glow(cv.circle(x, y, r_), '#ffffff', r_ * 0.6, rng.uniform(0.35, 0.9) * (1 - y / 90))
    # volcano glow in the sky
    cv.glow(cv.ellipse(104, 46, 16, 10), '#ff6a2a', 8, 0.55)
    # smoke plume
    lay = cv.layer()
    pm = np.zeros((cv.H, cv.W), np.float32)
    for i, (x, y, r_) in enumerate(((102, 38, 4), (99, 31, 5.4), (95, 23, 6.6), (89, 15, 7.4), (81, 8, 8.0), (72, 3, 8.4))):
        pm = np.maximum(pm, lay.circle(x, y, r_))
    lay.shade(lay.feather(pm, 1.4), Lin(0, 0, 0, 45, '#3a2a5a', '#5a3a6a', '#a04a5a'), r=3, spec=0, amb=0.8, diff=0.3, tex=0.3, tscale=4, tseed=2)
    cv.over(lay, 0.75)
    # sea
    sea = cv.rect(0, 96, 128, 128)
    cv.paint(sea, Lin(0, 96, 0, 128, '#2a1e5a', '#0a0a2a'))
    cv.paint(cv.feather(cv.ellipse(64, 104, 30, 3.5), 2.5) * sea, '#ffd0d8', 0.35)
    cv.paint(cv.lines([[(x, y), (x + rng.uniform(3, 9), y)] for x, y in zip(rng.uniform(10, 120, 26), rng.uniform(98, 126, 26))], 0.35) * sea, '#c8a0e0', 0.35)
    # island silhouette: hills, volcano on the right, palms on the left
    isl = cv.poly(spline([(-2, 99), (6, 93), (16, 90), (30, 91), (44, 88), (58, 86), (74, 80), (86, 64), (96, 45), (99.5, 41.5), (108, 41.2),
                          (112, 45), (118, 58), (124, 70), (130, 76), (130, 99)], n=10) + [(130, 101), (-2, 101)])
    cv.paint(isl, Lin(0, 40, 0, 100, '#2a1430', '#120a1e', '#08040e'))
    cv.paint(cv.feather(cv.poly([(98, 42), (110, 42), (114, 50), (102, 56), (96, 50)]), 1.2) * isl, '#ff5a1e', 0.85)
    cv.paint(cv.lines([bez((101, 43), (100, 52), (97, 62), n=12), bez((107, 43), (110, 54), (114, 62), n=12)], 0.9) * isl, '#ff7a2a', 0.8)
    cv.glow(cv.ellipse(104.5, 41.6, 5.5, 1.4), '#ffb040', 1.0, 0.9)
    for (bx, by, h, lean) in ((12, 92, 22, -3), (21, 91, 16, 4)):
        top = (bx + lean, by - h)
        cv.paint(cv.tube(bez((bx, by), (bx + lean * 0.2, by - h * 0.5), top, n=20), 1.6, 1.0), '#0a0612')
        polys = []
        for a in (-160, -125, -90, -55, -20, 10, 170):
            ar = math.radians(a)
            L = 9.5
            tip = (top[0] + L * math.cos(ar), top[1] + L * math.sin(ar) + 4.0)
            mid = (top[0] + L * 0.5 * math.cos(ar), top[1] + L * 0.5 * math.sin(ar) - 1.2)
            polys.append(bez(top, mid, tip, n=12) + [(tip[0] + 0.5, tip[1] - 1.4)] + bez(tip, (mid[0], mid[1] + 1.8), top, n=12))
        cv.paint(cv.poly(*polys), '#0a0612')
    # the diamond, huge, in front
    icon_diamond(cv, 64, 63, 36)
    _canvas_image(cv, 1024, True).save(os.path.join('art', 'icon-1024.png'), optimize=True)
    print('art/icon-1024.png')
    # ---- adaptive foreground: just the diamond (~55% of the frame), transparent
    fg = Canvas(128, 128, ss=2, seed=98)
    icon_diamond(fg, 64, 64, 35, rays=False)
    _canvas_image(fg, 1024, False).save(os.path.join('art', 'icon-foreground-1024.png'), optimize=True)
    print('art/icon-foreground-1024.png')


# @@SPRITES@@


# ==============================================================================================

def main(argv):
    names = ' '.join(argv[1:]).split() or list(SPRITES) + ['icon']
    for n in names:
        if n == 'icon':
            make_icons()
            continue
        fn, vh = SPRITES[n]
        cv = fn()
        cv.save(n, vh)


if __name__ == '__main__':
    main(sys.argv)
