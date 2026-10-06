#!/usr/bin/env python3
"""Generates the first-person background pictures (bg_*.jpg) and the full-screen pictures.

    python3 tools/make_backgrounds.py            (all pictures)
    python3 tools/make_backgrounds.py beach_sea crater ...   (only those)

Contract: art/ART_SPEC.md. Scenes are 240 x 136 virtual pixels drawn at 6x (1440 x 816);
full-screen pictures are 240 x 224 virtual (1440 x 1344). Everything is rendered at twice that
size (supersampling) and Lanczos-reduced, then saved as JPEG quality 90 in Diamond.Core/Art/.

The pictures are built from a small set of shared painters (sky, clouds, sea, sand, foliage,
palms, rocks, a torch-lit ray-cast room/cave renderer, stone blocks, corrugated iron, ...) so the
whole set looks consistent. Everything is deterministic: every random choice comes from a fixed
seed.
"""
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'Diamond.Core', 'Art')

SS = 2            # supersampling factor
U = 6 * SS        # working pixels per virtual pixel
F = np.float32
LIGHT = (-0.62, -0.78)   # outdoor light direction (from the upper left), screen space


# --------------------------------------------------------------------------------------------
# Basic maths and colour helpers
# --------------------------------------------------------------------------------------------

def col(h, scale=1.0):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 * scale for i in (0, 2, 4)], F)


def rgb255(c):
    return tuple(int(max(0, min(255, round(float(v) * 255)))) for v in c)


def mix(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smooth(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def box1(a, r, axis):
    """Box filter of radius r along an axis (cumulative sums, edge padded)."""
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode='edge')
    cs = np.cumsum(p, axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(cs, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(cs, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(F)


def gblur(a, sigma):
    """Approximate gaussian blur of a float array (H x W or H x W x C)."""
    if sigma < 0.5:
        return a
    if sigma > 24:   # blur big radii at a reduced size
        k = int(sigma // 12)
        h, w = a.shape[:2]
        small = a[::k, ::k]
        small = gblur(small, sigma / k)
        return resize_arr(small, w, h)
    r = max(1, int(round(sigma * 0.95)))
    for axis in (0, 1):
        for _ in range(3):
            a = box1(a, r, axis)
    return a


def resize_arr(a, w, h):
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(F)).resize((w, h), Image.BICUBIC), F)
    return np.stack([resize_arr(a[..., i], w, h) for i in range(a.shape[2])], axis=-1)


_noise_cache = {}


class VNoise:
    """Smooth value noise on a 256-periodic lattice, evaluated at arbitrary coordinates."""

    def __init__(self, seed):
        self.t = np.random.default_rng(seed).random((256, 256)).astype(F)

    def __call__(self, u, v):
        u = np.asarray(u, F)
        v = np.asarray(v, F)
        iu = np.floor(u)
        iv = np.floor(v)
        fu = u - iu
        fv = v - iv
        iu = iu.astype(np.int64) & 255
        iv = iv.astype(np.int64) & 255
        fu = fu * fu * (3 - 2 * fu)
        fv = fv * fv * (3 - 2 * fv)
        i1 = (iu + 1) & 255
        j1 = (iv + 1) & 255
        t = self.t
        a = t[iv, iu]
        b = t[iv, i1]
        c = t[j1, iu]
        d = t[j1, i1]
        return a + (b - a) * fu + (c - a) * fv + (a - b - c + d) * fu * fv


def vnoise(seed):
    if seed not in _noise_cache:
        _noise_cache[seed] = VNoise(seed)
    return _noise_cache[seed]


def fbm(u, v, seed, octaves=5, gain=0.5, lac=2.03, ridged=False):
    """Fractal noise in about [0, 1] (ridged: sharp creases at 1)."""
    total = 0.0
    amp = 1.0
    norm = 0.0
    u = np.asarray(u, F)
    v = np.asarray(v, F)
    for o in range(octaves):
        n = vnoise(seed * 31 + o)(u + o * 17.13, v - o * 9.71)
        if ridged:
            n = 1.0 - np.abs(2 * n - 1)
            n = n * n
        total = total + n * amp
        norm += amp
        amp *= gain
        u, v = u * lac + v * 0.12, v * lac - u * 0.12
    return total / norm


def snoise(h, w, scale, seed, octaves=4, gain=0.55):
    """Fast screen-space fractal noise (upsampled random grids), normalised to mean 0.5, sd 0.17."""
    rng = np.random.default_rng(seed + 7919)
    total = np.zeros((h, w), F)
    amp = 1.0
    s = float(scale)
    for _ in range(octaves):
        gw = max(2, int(w / s) + 3)
        gh = max(2, int(h / s) + 3)
        g = rng.random((gh, gw)).astype(F)
        im = Image.fromarray(g).resize((int(gw * s), int(gh * s)), Image.BICUBIC)
        ox = int(rng.integers(0, max(1, int(s))))
        oy = int(rng.integers(0, max(1, int(s))))
        arr = np.asarray(im, F)[oy:oy + h, ox:ox + w]
        total += arr * amp
        amp *= gain
        s /= 2.0
        if s < 1.5:
            break
    total -= total.mean()
    sd = total.std() + 1e-6
    return total / sd * 0.17 + 0.5


# --------------------------------------------------------------------------------------------
# Canvas, masks and compositing
# --------------------------------------------------------------------------------------------

class Lay:
    """Drawing layer: colour drawn with alpha blending + a separate coverage mask, so leaves can
    cast soft drop shadows onto the leaves beneath them."""

    def __init__(self, w, h, shadows=True):
        self.rgb = Image.new('RGB', (w, h), (0, 0, 0))
        self.a = Image.new('L', (w, h), 0)
        self.d = ImageDraw.Draw(self.rgb, 'RGBA')
        self.da = ImageDraw.Draw(self.a)
        self.shadow = shadows

    def _cover(self, kind, geom, fill, **kw):
        al = 255 if len(fill) < 4 else fill[3]
        if al >= 250:
            getattr(self.da, kind)(geom, fill=255, **kw)
            return
        # translucent: max() into the coverage mask
        tmp = Image.new('L', self.a.size, 0)
        getattr(ImageDraw.Draw(tmp), kind)(geom, fill=int(al), **kw)
        bb = tmp.getbbox()
        if bb:
            self.a.paste(ImageChops.lighter(self.a.crop(bb), tmp.crop(bb)), bb[:2])

    def polygon(self, pts, fill):
        self.d.polygon(pts, fill=fill)
        self._cover('polygon', pts, fill)

    def line(self, pts, fill, width=1, joint=None):
        self.d.line(pts, fill=fill, width=width, joint=joint)
        self._cover('line', pts, fill, width=width, joint=joint)

    def ellipse(self, box, fill):
        self.d.ellipse(box, fill=fill)
        self._cover('ellipse', box, fill)

    def rectangle(self, box, fill):
        self.d.rectangle(box, fill=fill)
        self._cover('rectangle', box, fill)

    def pieslice(self, box, start, end, fill):
        self.d.pieslice(box, start, end, fill=fill)
        self._cover('pieslice', box, fill, start=start, end=end)

    def chord(self, box, start, end, fill):
        self.d.chord(box, start, end, fill=fill)
        self._cover('chord', box, fill, start=start, end=end)

    def arc(self, box, start, end, fill, width=1):
        self.d.arc(box, start, end, fill=fill, width=width)

    def shade(self, pts, alpha=70, color=(0, 0, 0)):
        """Darkens what is already drawn (no coverage change)."""
        self.d.polygon(pts, fill=tuple(color) + (int(alpha),))

    def image(self):
        im = self.rgb.copy()
        im.putalpha(self.a)
        return im

    def filter(self, f):
        return self.image().filter(f)


class Canvas:
    def __init__(self, vw=240, vh=136):
        self.vw, self.vh = vw, vh
        self.W, self.H = vw * U, vh * U
        self.img = np.zeros((self.H, self.W, 3), F)
        self.xs = np.arange(self.W, dtype=F)[None, :]
        self.ys = np.arange(self.H, dtype=F)[:, None]

    def save(self, name):
        a = (np.clip(self.img, 0, 1) * 255 + 0.5).astype(np.uint8)
        im = Image.fromarray(a).resize((self.W // SS, self.H // SS), Image.LANCZOS)
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, name + '.jpg')
        im.save(path, 'JPEG', quality=90, optimize=True)
        return path

    def layer(self, shadows=True):
        """A transparent drawing layer the size of the canvas (see Lay)."""
        lay = Lay(self.W, self.H, shadows)
        return lay, lay

    def mask(self):
        im = Image.new('L', (self.W, self.H), 0)
        return im, ImageDraw.Draw(im)

    def comp(self, layer, blur=0, tint=None, tint_amt=0.0, opacity=1.0, box=None, dapple=None):
        """Composite a layer over the canvas (optionally hazed towards a tint / dappled)."""
        if isinstance(layer, Lay):
            layer = layer.image()
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        a = np.asarray(layer, F) / 255.0
        rgb = a[..., :3]
        al = a[..., 3] * opacity
        if dapple is not None:
            scale, amount, seed = dapple
            n = snoise(rgb.shape[0] // 4, rgb.shape[1] // 4, scale / 4, seed, 3)
            n = resize_arr(n, rgb.shape[1], rgb.shape[0])
            rgb = rgb * (1 + (n[..., None] - 0.5) * 2 * amount)
        if tint is not None and tint_amt:
            rgb = mix(rgb, tint, tint_amt)
        over(self.img, al, rgb, box)

    def add(self, arr, box=None):
        if box is None:
            self.img += arr
        else:
            x0, y0, x1, y1 = box
            self.img[y0:y1, x0:x1] += arr


def over(img, a, c, box=None):
    """img = img * (1 - a) + c * a, in place (a: H x W; c: colour or H x W x 3)."""
    if box is not None:
        x0, y0, x1, y1 = box
        img = img[y0:y1, x0:x1]
    if a.ndim == 2:
        a = a[..., None]
    img += (np.asarray(c, F) - img) * a


def m2a(m, blur=0):
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(m, F) / 255.0


def P(*v):
    """Virtual -> working pixel coordinates (flat list of numbers or (x, y) points)."""
    if len(v) == 1 and isinstance(v[0], (list, tuple)):
        return [(x * U, y * U) for (x, y) in v[0]]
    return [x * U for x in v]


def mask_crop(c, polys=(), ellipses=(), pad=4, blur=0, lines=()):
    """Draws shapes (working px) into a cropped L mask. Returns (alpha, box)."""
    xs, ys = [], []
    for p in polys:
        xs += [q[0] for q in p]
        ys += [q[1] for q in p]
    for e in ellipses:
        xs += [e[0], e[2]]
        ys += [e[1], e[3]]
    for ln in lines:
        xs += [q[0] for q in ln[0]]
        ys += [q[1] for q in ln[0]]
    pad = int(pad + blur * 3)
    x0 = max(0, int(min(xs)) - pad)
    y0 = max(0, int(min(ys)) - pad)
    x1 = min(c.W, int(max(xs)) + pad + 1)
    y1 = min(c.H, int(max(ys)) + pad + 1)
    if x1 <= x0 or y1 <= y0:
        return None, None
    m = Image.new('L', (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon([(q[0] - x0, q[1] - y0) for q in p], fill=255)
    for e in ellipses:
        d.ellipse((e[0] - x0, e[1] - y0, e[2] - x0, e[3] - y0), fill=255)
    for pts, wdt in lines:
        d.line([(q[0] - x0, q[1] - y0) for q in pts], fill=255, width=int(wdt), joint='curve')
    return m2a(m, blur), (x0, y0, x1, y1)


def shape_lam(a, R, light=LIGHT):
    """Lighting term in [-1, 1] for a silhouette, as if it were a rounded volume."""
    h = gblur(a, R)
    gy, gx = np.gradient(h)
    lam = -(gx * light[0] + gy * light[1]) * R * 2.6
    return np.clip(lam, -1, 1), h


def bump_lam(height, strength, light=LIGHT):
    gy, gx = np.gradient(height)
    return -(gx * light[0] + gy * light[1]) * strength


def glow(c, x, y, r, color, strength=1.0, power=2.0):
    """Additive radial glow at (x, y) working px."""
    x0 = max(0, int(x - r * 2.5))
    x1 = min(c.W, int(x + r * 2.5))
    y0 = max(0, int(y - r * 2.5))
    y1 = min(c.H, int(y + r * 2.5))
    if x1 <= x0 or y1 <= y0:
        return
    xx = np.arange(x0, x1, dtype=F)[None, :] - x
    yy = np.arange(y0, y1, dtype=F)[:, None] - y
    d = np.sqrt(xx * xx + yy * yy) / r
    g = 1.0 / (1.0 + d ** power) - 1.0 / (1.0 + 2.5 ** power)
    g = np.clip(g, 0, None) * strength
    c.img[y0:y1, x0:x1] += g[..., None] * np.asarray(color, F)


def vignette(c, amount=0.35, power=2.2, cx=0.5, cy=0.5, color=(0, 0, 0)):
    nx = (c.xs / c.W - cx) * 2
    ny = (c.ys / c.H - cy) * 2 * (c.H / c.W) * 1.25
    d = np.sqrt(nx * nx + ny * ny)
    v = clamp01(d ** power * amount)
    over(c.img, np.broadcast_to(v, (c.H, c.W)), np.asarray(color, F))


def grade(c, gamma=1.0, sat=1.0, contrast=1.0, lift=0.0):
    img = np.clip(c.img, 0, None)
    if gamma != 1.0:
        img = img ** (1.0 / gamma)
    if sat != 1.0:
        lum = img.mean(axis=2, keepdims=True)
        img = lum + (img - lum) * sat
    if contrast != 1.0:
        img = 0.5 + (img - 0.5) * contrast
    if lift:
        img = img + lift * (1 - img)
    c.img = img.astype(F)


def grain(c, amount=0.018, seed=0):
    rng = np.random.default_rng(seed + 99)
    n = rng.standard_normal((c.H, c.W)).astype(F) * amount
    c.img += n[..., None]


def vgrad(c, stops, y0=0, y1=None):
    """Fills rows [y0, y1) (working px) with a vertical gradient. stops: [(t, colour)]."""
    if y1 is None:
        y1 = c.H
    t = (np.arange(y0, y1, dtype=F) - y0) / max(1, (y1 - y0 - 1))
    ts = [s[0] for s in stops]
    out = np.zeros((y1 - y0, 3), F)
    for ch in range(3):
        out[:, ch] = np.interp(t, ts, [s[1][ch] for s in stops])
    c.img[y0:y1] = out[:, None, :]


def ramp(t, stops):
    """Colour ramp: t array -> colours (... x 3)."""
    ts = [s[0] for s in stops]
    t = np.asarray(t, F)
    return np.stack([np.interp(t, ts, [s[1][ch] for s in stops]).astype(F) for ch in range(3)],
                    axis=-1)


# --------------------------------------------------------------------------------------------
# Camera / ground plane
# --------------------------------------------------------------------------------------------

class Cam:
    """Pinhole camera looking along +Z. Y is the height above the ground."""

    def __init__(self, c, hy_v, h=1.7, fov=75.0, cx_v=None):
        self.c = c
        self.f = (c.W / 2) / math.tan(math.radians(fov / 2))
        self.hy = hy_v * U
        self.h = h
        self.cx = c.W / 2 if cx_v is None else cx_v * U

    def proj(self, X, Y, Z):
        return self.cx + X * self.f / Z, self.hy - (Y - self.h) * self.f / Z

    def zat(self, y_px):
        return self.h * self.f / max(0.5, y_px - self.hy)

    def ground(self, y0=None):
        """Ground plane coordinates for rows y0.. : (X, Z) arrays (rows x W) and row offset."""
        if y0 is None:
            y0 = int(self.hy) + 1
        ys = np.arange(y0, self.c.H, dtype=F)[:, None]
        Z = self.h * self.f / np.maximum(ys - self.hy, 0.5)
        X = (self.c.xs - self.cx) * Z / self.f
        return X, np.broadcast_to(Z, X.shape).astype(F), y0


# --------------------------------------------------------------------------------------------
# Sky and clouds
# --------------------------------------------------------------------------------------------

DAY_SKY = [(0.0, col('#2f6fc0')), (0.55, col('#5a9fe0')), (0.9, col('#a9d4f2')),
           (1.0, col('#d8eef8'))]


def sky(c, y1_v, stops=DAY_SKY, sun=None, sun_col=col('#fff3d0'), sun_r=40, sun_str=0.35):
    vgrad(c, stops, 0, int(y1_v * U))
    if sun is not None:
        glow(c, sun[0] * U, sun[1] * U, sun_r * U, sun_col, sun_str, power=1.6)


def puff(c, circles, seed, lit, shade, alpha=0.95, light=LIGHT, base_y=None, soft=1.0):
    """One cauliflower bulge of a cumulus: a union of circles (virtual x, y, r), shaded."""
    ells = [P(x - r, y - r, x + r, y + r) for x, y, r in circles]
    rmax = max(r for _, _, r in circles)
    a, box = mask_crop(c, ellipses=ells, pad=int(rmax * U * 0.8), blur=1.5 * soft)
    if a is None:
        return
    yy = np.arange(box[1], box[3], dtype=F)[:, None]
    if base_y is not None:
        a = a * (1 - smooth(base_y * U - rmax * U * 0.15, base_y * U + rmax * U * 0.05, yy))
    R = rmax * U * 0.45
    lam, hh = shape_lam(a, R, light)
    tex = snoise(a.shape[0], a.shape[1], max(4, rmax * U * 0.18), seed, 4)
    cy = sum(y for _, y, _ in circles) / len(circles)
    vert = clamp01((yy - (cy - rmax) * U) / (rmax * U * 2.2))
    t = clamp01(0.62 + 0.5 * lam - 0.45 * vert + (tex - 0.5) * 0.45)
    colr = mix(shade, lit, t[..., None])
    # fluffy edge
    edge = gblur(a, max(1.0, rmax * U * 0.05) * soft)
    al = clamp01(edge * 1.25 - 0.1 + (tex - 0.5) * 0.6 * (1 - edge)) * alpha
    over(c.img, al, colr, box)


def cloud(c, cx, cy, w, h, seed, lit=col('#ffffff'), shade=col('#a9b9d0'), alpha=0.97,
          light=LIGHT, flat=0.35):
    """A cumulus cloud (virtual coordinates: centre, width, height): several lobes of puffs."""
    rng = np.random.default_rng(seed)
    base = cy + h * 0.5
    lobes = max(2, int(round(w / h * 1.1)))
    puffs = []
    for L in range(lobes):
        u = (L + 0.5) / lobes
        lx = cx - w / 2 + w * u + rng.uniform(-0.25, 0.25) * w / lobes
        prof = math.sin(math.pi * u) ** 0.7
        lh = h * (0.4 + 0.6 * prof) * rng.uniform(0.75, 1.15)
        r = min(lh * 0.55, w / lobes * rng.uniform(0.55, 0.8))
        circ = [(lx, base - lh + r, r)]
        for k in range(5):
            ang = math.pi + rng.uniform(0.15, 0.85) * math.pi
            rr = r * rng.uniform(0.35, 0.55)
            circ.append((lx + math.cos(ang) * r * 0.8, base - lh + r + math.sin(ang) * r * 0.75, rr))
        circ.append((lx, base - r * 0.7, r * 1.05))
        puffs.append((base - lh, circ))
    # low puffs along the base in front
    for k in range(lobes + 1):
        lx = cx - w / 2 + w * rng.uniform(0.1, 0.9)
        r = h * rng.uniform(0.18, 0.3)
        puffs.append((base - r * 0.5, [(lx, base - r * 0.8, r), (lx + r * 0.9, base - r * 0.6, r * 0.7)]))
    puffs.sort(key=lambda p: p[0])
    for i, (_, circ) in enumerate(puffs):
        puff(c, circ, seed * 13 + i, lit, shade, alpha, light, base_y=base)


def cloud_bank(c, y_v, seed, n=6, x_range=(0, 240), size=(18, 40), lit=col('#ffffff'),
               shade=col('#9fb3cc'), alpha=0.95):
    rng = np.random.default_rng(seed)
    for i in range(n):
        w = rng.uniform(*size)
        x = rng.uniform(*x_range)
        y = y_v + rng.uniform(-3, 3)
        cloud(c, x, y - w * 0.14, w, w * rng.uniform(0.28, 0.42), seed * 100 + i, lit, shade, alpha)


def wisps(c, y0_v, y1_v, seed, color=col('#ffffff'), amount=0.35, stretch=8.0):
    """Thin streaky high clouds."""
    y0, y1 = int(y0_v * U), int(y1_v * U)
    h = y1 - y0
    n = snoise(h, c.W // 4, 30, seed, 5)
    n = resize_arr(n, c.W, h)
    band = np.sin(np.linspace(0, math.pi, h, dtype=F))[:, None]
    a = clamp01((n - 0.55) * 3.0) * band * amount
    over(c.img[y0:y1], a, color)


# --------------------------------------------------------------------------------------------
# Leaves, fronds, palms, grass
# --------------------------------------------------------------------------------------------

def leaf_pts(x, y, ang, L, Wd, bend=0.0, n=9, shape=0.8, base_w=0.25):
    """Pointed leaf from base (x, y) along ang. Returns (left_edge, right_edge, spine)."""
    ca, sa = math.cos(ang), math.sin(ang)
    left, right, spine = [], [], []
    for i in range(n + 1):
        t = i / n
        sx = x + ca * L * t
        sy = y + sa * L * t + bend * L * t * t
        tx = ca
        ty = sa + 2 * bend * t
        nl = math.hypot(tx, ty) or 1
        nx, ny = -ty / nl, tx / nl
        w = Wd * 0.5 * (math.sin(math.pi * min(1, t * (1 + base_w) / (1 + base_w * t))) ** shape)
        left.append((sx + nx * w, sy + ny * w))
        right.append((sx - nx * w, sy - ny * w))
        spine.append((sx, sy))
    return left, right, spine


def draw_leaf(d, x, y, ang, L, Wd, color, bend=0.0, light=LIGHT, rib=True, shape=0.8,
              alpha=255):
    left, right, spine = leaf_pts(x, y, ang, L, Wd, bend, shape=shape)
    ca, sa = math.cos(ang), math.sin(ang)
    nx, ny = -sa, ca
    # the half whose normal faces the light is brighter
    facing = -(nx * light[0] + ny * light[1])
    c1 = np.clip(color * (1.0 + 0.22 * facing), 0, 1)
    c2 = np.clip(color * (1.0 - 0.22 * facing), 0, 1)
    if getattr(d, 'shadow', False):
        ox, oy = L * 0.07 + 2, L * 0.11 + 2
        d.shade([(q[0] + ox, q[1] + oy) for q in left + right[::-1]], 85)
    d.polygon(spine + right[::-1], fill=rgb255(c2) + (alpha,))
    d.polygon(spine + left[::-1], fill=rgb255(c1) + (alpha,))
    if rib and L > 14:
        d.line(spine[:-1], fill=rgb255(np.clip(color * 1.25 + 0.04, 0, 1)) + (alpha,),
               width=max(1, int(L / 60)))


def draw_frond(d, x, y, ang, L, color, droop=0.6, leaflet=0.32, density=1.0, light=LIGHT,
               rng=None, alpha=255, width=None, split=0.0):
    """Palm frond: curved rachis with leaflets on both sides (working px)."""
    rng = rng or np.random.default_rng(0)
    n = int(26 * density)
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((x + ca * L * t, y + sa * L * t + droop * L * t * t))
    for i in range(2, n):
        t = i / n
        px, py = pts[i]
        qx, qy = pts[i + 1]
        tang = math.atan2(qy - py, qx - px)
        ll = L * leaflet * math.sin(math.pi * (0.15 + 0.85 * t)) ** 0.7 * (1.1 - 0.4 * t)
        lw = (width or L * 0.035) * (1.1 - 0.5 * t)
        for side in (-1, 1):
            if split and rng.random() < split:
                continue
            a2 = tang + side * (0.75 + 0.25 * rng.random())
            # leaflets droop under gravity
            b = 0.35 + 0.3 * rng.random()
            shade = 0.85 + 0.3 * rng.random()
            facing = -(math.cos(a2 - math.pi / 2) * light[0] + math.sin(a2 - math.pi / 2) * light[1])
            cc = np.clip(color * shade * (1 + 0.15 * facing * side), 0, 1)
            lft, rgt, sp = leaf_pts(px, py, a2, ll, lw, bend=b, n=5, shape=0.6)
            if getattr(d, 'shadow', False) and alpha >= 250:
                d.shade([(q[0] + ll * 0.08 + 2, q[1] + ll * 0.12 + 2) for q in lft + rgt[::-1]], 45)
            d.polygon(lft + rgt[::-1], fill=rgb255(cc) + (alpha,))
    d.line(pts, fill=rgb255(np.clip(color * 0.8 + 0.08, 0, 1)) + (alpha,),
           width=max(1, int(L * 0.018)), joint='curve')


def draw_palm(d, x, y, height, lean, seed, frond_col=col('#2f7d32'), trunk_col=col('#8a7356'),
              alpha=255, fronds=11, crown=1.0):
    """A coconut palm from base (x, y) in working px; height in px; lean in px at the top."""
    rng = np.random.default_rng(seed)
    n = 24
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((x + lean * t * t + math.sin(t * 3 + seed) * height * 0.015,
                    y - height * t))
    w0 = height * 0.045
    left, right, mid_l, mid_r = [], [], [], []
    for i in range(n + 1):
        t = i / n
        x_, y_ = pts[i]
        w = w0 * (1.0 - 0.35 * t) * (1.25 if i == 0 else 1.0)
        left.append((x_ - w, y_))
        right.append((x_ + w, y_))
        mid_l.append((x_ - w * 0.55, y_))
        mid_r.append((x_ + w * 0.25, y_))
    d.polygon(left + right[::-1], fill=rgb255(trunk_col * 0.62) + (alpha,))
    d.polygon(left + mid_r[::-1], fill=rgb255(trunk_col * 0.9) + (alpha,))
    d.polygon(left + mid_l[::-1], fill=rgb255(np.clip(trunk_col * 1.12, 0, 1)) + (alpha,))
    # leaf-scar rings
    k = 0
    tpos = 0.0
    while tpos < 1.0:
        i = min(n, int(tpos * n))
        x_, y_ = pts[i]
        w = w0 * (1.0 - 0.35 * tpos)
        d.arc((x_ - w, y_ - w * 0.35, x_ + w, y_ + w * 0.35), 10, 170,
              fill=rgb255(trunk_col * 0.5) + (int(alpha * 0.7),), width=max(1, int(w * 0.18)))
        tpos += (w * 0.9 + rng.uniform(0, w * 0.5)) / height
        k += 1
    tx, ty = pts[-1]
    L = height * 0.42 * crown
    angs = []
    for i in range(fronds):
        angs.append(-math.pi / 2 + (i / (fronds - 1) - 0.5) * math.pi * 1.9 + rng.uniform(-0.15, 0.15))
    order = sorted(range(fronds), key=lambda i: -abs(math.sin(angs[i])))
    for i in order:
        a = angs[i]
        up = -math.sin(a)
        droop = 0.55 + 0.45 * (1 - abs(math.cos(a))) * 0.3 + 0.25 * up
        shade = 0.75 + 0.35 * rng.random() + 0.15 * up
        draw_frond(d, tx, ty, a, L * rng.uniform(0.85, 1.1), np.clip(frond_col * shade, 0, 1),
                   droop=droop, rng=rng, alpha=alpha, split=0.08)
    # coconuts / crown shadow
    for k in range(4):
        ccx = tx + (k - 1.5) * w0 * 0.6
        ccy = ty + w0 * (0.5 + 0.3 * (k % 2))
        d.ellipse((ccx - w0 * 0.45, ccy - w0 * 0.42, ccx + w0 * 0.45, ccy + w0 * 0.42),
                  fill=rgb255(np.minimum(col('#5a4a22'), trunk_col * 0.8) * (0.8 + 0.1 * k)) + (alpha,))


def draw_fern(d, x, y, size, color, seed, n=9, spread=1.0, light=LIGHT, alpha=255):
    rng = np.random.default_rng(seed)
    for i in range(n):
        a = -math.pi / 2 + (i / max(1, n - 1) - 0.5) * math.pi * 1.25 * spread + rng.uniform(-0.15, 0.15)
        L = size * rng.uniform(0.7, 1.05)
        shade = rng.uniform(0.8, 1.15)
        draw_frond(d, x, y, a, L, np.clip(color * shade, 0, 1), droop=0.55 + 0.2 * rng.random(),
                   leaflet=0.18, density=1.3, rng=rng, alpha=alpha, width=L * 0.05)


def draw_blade(d, x, y, h, lean, w, color, alpha=255):
    """A tapering curved grass blade / reed."""
    pts_l, pts_r = [], []
    n = 6
    for i in range(n + 1):
        t = i / n
        px = x + lean * t * t
        py = y - h * t
        ww = w * (1 - t) * 0.5 + 0.3
        pts_l.append((px - ww, py))
        pts_r.append((px + ww, py))
    d.polygon(pts_l + pts_r[::-1], fill=rgb255(color) + (alpha,))


def draw_broadleaf_bush(d, x, y, size, color, seed, n=14, light=LIGHT, alpha=255, up=1.0):
    """Clump of broad leaves (banana / elephant ear style) from a base point."""
    rng = np.random.default_rng(seed)
    leaves = []
    for i in range(n):
        a = -math.pi / 2 + rng.uniform(-1.3, 1.3) * up
        L = size * rng.uniform(0.55, 1.0)
        leaves.append((a, L))
    leaves.sort(key=lambda q: -q[1])
    for a, L in leaves:
        sh = rng.uniform(0.75, 1.15)
        bx = x + math.cos(a) * L * 0.25
        by = y + math.sin(a) * L * 0.25
        draw_leaf(d, bx, by, a, L, L * rng.uniform(0.35, 0.5), np.clip(color * sh, 0, 1),
                  bend=rng.uniform(0.1, 0.45), alpha=alpha)


def foliage_mass(c, d, top_fn, x0, x1, y_bottom, seed, palette, leaf=40.0, density=1.0,
                 base=None, gap=None, light=1.0, depth=None, kinds=('lance', 'broad', 'frond')):
    """A band of dense foliage whose upper edge follows top_fn(x) (working px).

    Leaves near the top are lit, those lower down fall into shadow."""
    rng = np.random.default_rng(seed)
    if base is None:
        base = palette[0] * 0.28
    step = 6
    xs = list(range(int(x0), int(x1) + step, step))
    poly = [(x, top_fn(x) + leaf * 0.35) for x in xs] + [(x1, y_bottom), (x0, y_bottom)]
    d.polygon(poly, fill=rgb255(base) + (255,))
    band = depth or (y_bottom - min(top_fn(x) for x in xs))
    area = (x1 - x0) * band
    n = int(area / (leaf * leaf) * 3.2 * density)
    items = []
    for i in range(n):
        x = rng.uniform(x0 - leaf * 0.3, x1 + leaf * 0.3)
        t = rng.random() ** 1.6
        y = top_fn(min(max(x, x0), x1)) + t * (y_bottom - top_fn(min(max(x, x0), x1))) + leaf * 0.2
        if gap is not None and gap(x, y):
            continue
        items.append((y, x, t))
    items.sort()
    for y, x, t in items:
        kind = kinds[int(rng.integers(0, len(kinds)))]
        pc = palette[int(rng.integers(0, len(palette)))]
        bright = light * (1.15 - 0.75 * t) * rng.uniform(0.8, 1.15)
        cc = np.clip(pc * bright, 0, 1)
        L = leaf * rng.uniform(0.6, 1.3)
        if kind == 'lance':
            a = -math.pi / 2 + rng.uniform(-1.6, 1.6)
            draw_leaf(d, x, y, a, L, L * 0.28, cc, bend=rng.uniform(0.1, 0.5))
        elif kind == 'broad':
            a = -math.pi / 2 + rng.uniform(-1.4, 1.4)
            draw_leaf(d, x, y, a, L * 1.1, L * 0.55, cc, bend=rng.uniform(0.1, 0.4))
        elif kind == 'frond':
            a = -math.pi / 2 + rng.uniform(-1.2, 1.2)
            draw_frond(d, x, y, a, L * 1.6, cc, droop=0.6, leaflet=0.25, density=0.7, rng=rng)
        elif kind == 'small':
            for k in range(4):
                a = rng.uniform(0, 2 * math.pi)
                draw_leaf(d, x, y, a, L * 0.5, L * 0.22, np.clip(cc * rng.uniform(0.85, 1.1), 0, 1),
                          bend=0.2, rib=False)


def tree_canopy(d, cx, cy, r, palette, seed, leaf=None, light=LIGHT, n=None):
    """Round tree crown made of many leaves, lit from the upper left (working px)."""
    rng = np.random.default_rng(seed)
    leaf = leaf or r * 0.28
    n = n or int((r / leaf) ** 2 * 9)
    items = []
    for i in range(n):
        ang = rng.uniform(0, 2 * math.pi)
        rr = r * math.sqrt(rng.random())
        x = cx + math.cos(ang) * rr * 1.25
        y = cy + math.sin(ang) * rr * 0.8
        items.append((y, x))
    items.sort()
    for y, x in items:
        dx, dy = (x - cx) / r, (y - cy) / r
        lit = 0.85 - 0.5 * (dx * light[0] + dy * light[1]) * -1
        lit = 0.6 + 0.45 * (-(dx * light[0] + dy * light[1]))
        pc = palette[int(rng.integers(0, len(palette)))]
        cc = np.clip(pc * lit * rng.uniform(0.8, 1.15), 0, 1)
        a = math.atan2(dy, dx) + rng.uniform(-0.8, 0.8)
        L = leaf * rng.uniform(0.7, 1.2)
        draw_leaf(d, x, y, a, L, L * 0.45, cc, bend=0.2, rib=L > 30)


JUNGLE = [col('#2e7d32'), col('#3f8f2c'), col('#1f6b3a'), col('#5a9e2f'), col('#2a6e4a'),
          col('#6bab3a')]


# --------------------------------------------------------------------------------------------
# Rocks
# --------------------------------------------------------------------------------------------

def rock_poly(cx, cy, rx, ry, seed, n=28, rough=0.22, flat_base=True):
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 6.28, 4)
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi
        r = 1 + rough * (0.5 * math.sin(2 * a + phase[0]) + 0.3 * math.sin(3 * a + phase[1])
                         + 0.2 * math.sin(5 * a + phase[2])) + rng.uniform(-rough, rough) * 0.35
        x = cx + math.cos(a) * rx * r
        y = cy + math.sin(a) * ry * r
        if flat_base and y > cy:
            y = cy + (y - cy) * 0.35
        pts.append((x, y))
    return pts


def paint_rock(c, pts, base, seed, R=None, tex_scale=None, light=LIGHT, amb=0.35, spec=0.15,
               rim_col=None, rim=0.0, crack=0.5, lit_col=None, alpha=1.0, blur=1.0):
    """Paints a shaded, textured rock from a polygon in working px."""
    a, box = mask_crop(c, polys=[pts], pad=8, blur=blur)
    if a is None:
        return
    h, w = a.shape
    size = min(h, w)
    R = R or size * 0.22
    lam, hh = shape_lam(a, R, light)
    ts = tex_scale or max(6, size * 0.18)
    n1 = snoise(h, w, ts, seed, 5)
    n2 = snoise(h, w, ts * 0.25, seed + 1, 3)
    facets = bump_lam(n1 * ts * 0.9, 1.0, light)
    cr = snoise(h, w, ts * 0.7, seed + 2, 3)
    cracks = 1 - smooth(0.0, 0.04, np.abs(cr - 0.5)) if crack else 0
    shade = clamp01(amb + (1 - amb) * (0.5 + 0.5 * lam) + facets * 0.6)
    shade = shade * (0.85 + 0.35 * (n2 - 0.5) * 2 * 0.5) * (1 - 0.45 * crack * cracks)
    # ambient occlusion at the base
    yy = np.linspace(0, 1, h, dtype=F)[:, None]
    shade *= 1 - 0.35 * smooth(0.65, 1.0, yy)
    colr = base * shade[..., None]
    if lit_col is not None:
        colr = colr + lit_col * (clamp01(lam) ** 2 * spec)[..., None]
    else:
        colr = colr + (clamp01(lam + facets) ** 3 * spec)[..., None]
    if rim_col is not None and rim:
        rimm = clamp01(-lam) ** 2 * rim
        colr = colr + rim_col * rimm[..., None]
    over(c.img, a * alpha, colr, box)


def boulder(c, cx, cy, rx, ry, base, seed, **kw):
    """Boulder centred at (cx, cy) virtual with radii; its base rests at cy + ry*0.35."""
    pts = [(x * U, y * U) for x, y in rock_poly(cx, cy, rx, ry, seed)]
    paint_rock(c, pts, base, seed, **kw)


def contact_shadow(c, cx, cy, rx, ry, strength=0.45, blur=None):
    pts = P(cx - rx, cy - ry, cx + rx, cy + ry)
    a, box = mask_crop(c, ellipses=[pts], blur=blur or ry * U * 0.6)
    if a is not None:
        over(c.img, a * strength, col('#000000'), box)


# --------------------------------------------------------------------------------------------
# Sand and sea (ground plane materials)
# --------------------------------------------------------------------------------------------

SAND_LIGHT = col('#f2d595')
SAND_DARK = col('#cfa560')
WET_SAND = col('#a98652')


def sand_height(X, Z, seed):
    warp = fbm(X * 0.12, Z * 0.12, seed + 2, 3) * 7
    dunes = fbm(X * 0.18, Z * 0.18, seed, 4)
    rip = np.sin(Z * 3.1 + X * 0.55 + warp) * 0.025 * (0.5 + fbm(X * 0.3, Z * 0.3, seed + 5, 2))
    return dunes * 0.5 + rip


def sand_rgb(X, Z, seed, light=SAND_LIGHT, dark=SAND_DARK, haze=col('#e9dcc0'), relief=1.0):
    e = 0.04
    h = sand_height(X, Z, seed)
    hx = sand_height(X + e, Z, seed)
    hz = sand_height(X, Z + e, seed)
    # light from the upper left / behind: slopes facing -X and -Z are lit
    att = np.exp(-Z / 25.0)
    lam = (-(hx - h) / e * 0.8 - (hz - h) / e * 0.5) * relief * att
    n2 = fbm(X * 1.7, Z * 1.7, seed + 1, 3)
    t = clamp01(0.6 + (h - 0.25) * 0.9 + (n2 - 0.5) * 0.3 * np.exp(-Z / 6) + lam * 0.55)
    rgb = mix(dark, light, t[..., None])
    rgb = rgb * (1 + np.clip(lam, -1, 1)[..., None] * 0.1)
    rgb = mix(rgb, haze, (smooth(25, 400, Z) * 0.45)[..., None])
    return rgb


def sand_grain(c, y0, amount=0.05, seed=0):
    """Fine screen-space grain on the near ground (rows y0.. working px)."""
    h = c.H - y0
    rng = np.random.default_rng(seed + 5)
    n = rng.standard_normal((h, c.W)).astype(F)
    n = gblur(n, 0.8)
    ramp_ = np.linspace(0.2, 1.0, h, dtype=F)[:, None]
    c.img[y0:] *= (1 + n * amount * ramp_)[..., None]


SEA_RAMP = [(0.0, col('#a7efe0')), (1.5, col('#62dccd')), (5.0, col('#2fc0c4')),
            (14.0, col('#1d9ec0')), (40.0, col('#1a73b0')), (140.0, col('#17589c')),
            (600.0, col('#1a4c8e'))]


def sea_rgb(X, Z, dist, seed, ramp_stops=SEA_RAMP, sun_x=None, sky_col=col('#9fcff0'),
            horizon_haze=col('#8fbbe0'), glitter=0.5, W=None):
    """Sea colour; dist = distance from the shoreline into the sea (m)."""
    base = ramp(np.clip(dist, 0, 600), ramp_stops)
    # wave texture: horizontal streaks that compress with distance
    att = np.exp(-Z / 60.0)
    warp = fbm(X * 0.02, Z * 0.02, seed + 3, 3) * 6
    n = fbm(X * 0.09, Z * 0.45 + warp, seed, 5)
    n_d = fbm(X * 0.5, Z * 1.6, seed + 1, 3)
    waves = (n - 0.5) * 1.4 + (n_d - 0.5) * 0.7 * att
    # crests: lighter tops facing the sky, darker troughs
    rgb = base * (1 + waves[..., None] * 0.28)
    refl = clamp01(waves * 1.6) * (0.25 + 0.5 * smooth(5, 200, Z))
    rgb = mix(rgb, sky_col, refl[..., None] * 0.35)
    # sun glitter
    if sun_x is not None and glitter:
        xs = (np.arange(X.shape[1], dtype=F)[None, :] - sun_x) / (W or X.shape[1])
        col_band = np.exp(-(xs / (0.06 + 0.002 * np.minimum(Z, 200))) ** 2)
        sp = clamp01((n_d * 0.6 + n * 0.4 - 0.63) * 9) * col_band * glitter
        rgb = rgb + sp[..., None] * col('#fff8e0')
    rgb = mix(rgb, horizon_haze, (smooth(60, 3000, Z) * 0.55)[..., None])
    return rgb


def foam(dist, X, Z, seed, centre, width, lace=1.0, along=None):
    """Whitewater of a breaking wave whose crest is at about `centre` m from the shore."""
    if along is None:
        along = X
    cen = centre + (fbm(along * 0.035, 0.5, seed + 1, 3) - 0.5) * 3.5
    brk = smooth(0.32, 0.62, fbm(along * 0.025, 3.5, seed + 2, 3))
    lace_n = fbm(along * 0.55, dist * 0.8, seed, 4, ridged=True)
    blob = fbm(along * 0.25, dist * 0.5, seed + 3, 3)
    crest = smooth(cen - 0.7, cen - 0.15, dist) * (1 - smooth(cen, cen + 0.3, dist))
    crest = crest * (0.35 + 0.65 * brk)
    behind = smooth(cen - width, cen - 0.3, dist) * (1 - smooth(cen - 0.4, cen, dist))
    dens = smooth(cen - width, cen, dist)
    white = behind * clamp01((lace_n - 0.62 + 0.35 * dens) * 5 + (blob - 0.5) * 2.5 * dens) * (0.3 + 0.7 * brk)
    return clamp01(crest + white * lace)


def beach_scene(c, cam, seed, shore_fn, sea_dist_fn, sun_x=None, wet=3.0, waves=((1.0, 4.0), (7.0, 4.5), (16.0, 5.0)),
                sky_col=col('#9fcff0'), along_z=False):
    """Ground: sand + sea. shore_fn returns the signed distance into the sea (m, <0 on sand)."""
    X, Z, y0 = cam.ground()
    dist = sea_dist_fn(X, Z)
    sand = sand_rgb(X, Z, seed)
    # wet sand band near the water, reflecting the sky
    wetm = smooth(-wet, -0.2, dist)
    sand = mix(sand, mix(WET_SAND, sky_col, 0.25), (wetm * 0.75)[..., None])
    sea = sea_rgb(X, Z, dist, seed + 10, sun_x=sun_x, sky_col=sky_col, W=c.W)
    # shallow water over sand is transparent at the very edge
    edge = smooth(-0.05, 1.2, dist)
    rgb = mix(sand, sea, edge[..., None])
    for i, (cen, wid) in enumerate(waves):
        fm = foam(dist, X, Z, seed + 20 + i, cen, wid, along=Z if along_z else X)
        fm = fm * (1 - smooth(60, 160, Z))
        # wave face shadow just in front of the crest
        face = smooth(cen - 1.6, cen - 0.6, dist) * (1 - smooth(cen - 0.6, cen, dist)) * (1 - smooth(60, 160, Z))
        rgb = rgb * (1 - 0.18 * face[..., None]) + col('#2fd0c0') * (0.1 * face[..., None])
        rgb = mix(rgb, col('#f4fbfb'), fm[..., None] * 0.92)
    # swash: thin lacy foam line at the water's edge
    sw = smooth(-0.35, 0.0, dist) * (1 - smooth(0.0, 0.6, dist))
    lace = fbm((Z if along_z else X) * 1.2, dist * 1.2, seed + 40, 3)
    rgb = mix(rgb, col('#f0fafa'), (sw * clamp01((lace - 0.35) * 3))[..., None] * 0.85)
    c.img[y0:] = rgb
    sand_grain(c, y0, 0.04, seed)
    return X, Z, y0, dist


def grains(c, y0_v, seed, density=0.004, light=col('#fff2d0'), dark=col('#7a5a30'), y1_v=None,
           size=(1.5, 4.0), x_range=None):
    """Pebbles / shell specks scattered on the near ground (screen space, bigger near)."""
    rng = np.random.default_rng(seed)
    lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y0 = y0_v * U
    y1 = (y1_v or c.vh) * U
    n = int(c.W * (y1 - y0) * density / 100)
    for i in range(n):
        y = y0 + (y1 - y0) * math.sqrt(rng.random())
        x = rng.uniform(0, c.W) if x_range is None else rng.uniform(x_range[0] * U, x_range[1] * U)
        s = rng.uniform(*size) * (0.3 + 0.9 * (y - y0) / (y1 - y0))
        dk = rng.random() < 0.6
        cc = dark if dk else light
        cc = np.clip(cc * rng.uniform(0.8, 1.2), 0, 1)
        d.ellipse((x - s, y - s * 0.55, x + s, y + s * 0.55), fill=rgb255(cc) + (int(rng.uniform(90, 200)),))
    c.comp(lay)


def project_wall_band(cam, X_edge_fn, Zs, height_fn):
    """Screen polyline (top, base) of a vertical band along the depth axis."""
    top, basel = [], []
    for Z in Zs:
        x, yb = cam.proj(X_edge_fn(Z), 0, Z)
        _, yt = cam.proj(X_edge_fn(Z), height_fn(Z), Z)
        top.append((x, yt))
        basel.append((x, yb))
    return top, basel


def jungle_edge_along(c, cam, seed, side=-1, x_edge=-10.0, z_far=500, palms=True, height=5.0,
                      haze=col('#b8d2e0')):
    """Jungle wall running along the left side (side=-1) of the view, receding to the horizon."""
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    # continuous undergrowth wedge
    def xedge(Z):
        return side * (abs(x_edge) + 0.02 * Z) + 1.2 * math.sin(Z * 0.07 + seed)

    Zs = np.geomspace(z_far, 1.2, 140)
    top, basel = project_wall_band(cam, xedge, Zs, lambda Z: height + 1.5 * math.sin(Z * 0.21 + seed) + 1.0 * math.sin(Z * 0.53))
    outer = 0 if side < 0 else c.W
    poly = top + [(outer, top[-1][1]), (outer, basel[-1][1] + 50)] + basel[::-1]
    d.polygon(poly, fill=rgb255(col('#123a1f')) + (255,))
    # leaves along the wedge, far to near
    for i, Z in enumerate(Zs):
        x, yb = cam.proj(xedge(Z), 0, Z)
        _, yt = cam.proj(xedge(Z), height, Z)
        sc = cam.f / Z
        k = int(np.clip(3 + 60 / Z, 3, 14))
        for j in range(k):
            lx = x + side * rng.uniform(0, sc * 4) - side * rng.uniform(0, sc * 1.2)
            ly = yt + (yb - yt) * rng.random() ** 1.5
            t = (ly - yt) / max(1, yb - yt)
            pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
            cc = np.clip(pc * (1.15 - 0.7 * t) * rng.uniform(0.8, 1.15), 0, 1)
            cc = mix(cc, haze, float(smooth(20, 400, Z)) * 0.6)
            L = sc * rng.uniform(0.9, 2.0)
            a = -math.pi / 2 + rng.uniform(-1.5, 1.5)
            if rng.random() < 0.3:
                draw_frond(d, lx, ly, a, L * 1.4, cc, droop=0.6, leaflet=0.25, density=0.6, rng=rng)
            else:
                draw_leaf(d, lx, ly, a, L, L * rng.uniform(0.3, 0.55), cc, bend=rng.uniform(0.1, 0.5),
                          rib=L > 20)
        if palms and rng.random() < (0.22 if Z > 30 else 0.35) and Z < 260:
            ph = rng.uniform(9, 15) * sc
            px = x + side * rng.uniform(0.5, 3) * sc
            pcol = mix(col('#2f7d32') * rng.uniform(0.8, 1.15), haze, float(smooth(20, 300, Z)) * 0.6)
            tcol = mix(col('#8a7356'), haze, float(smooth(20, 300, Z)) * 0.6)
            draw_palm(d, px, yb, ph, -side * rng.uniform(0.05, 0.3) * ph, int(seed * 7 + i), frond_col=pcol,
                      trunk_col=tcol)
    c.comp(lay)


def tunnel_opening(c, cx, yb, w, h, seed, inner=col('#2e5a26'), floor=col('#6a5236'), light=col('#b8e080')):
    """Dark leafy tunnel mouth (working px): base centre (cx, yb), width w, height h."""
    x0, x1 = int(cx - w / 2), int(cx + w / 2)
    y0, y1 = int(yb - h), int(yb + 2)
    hh, ww = y1 - y0, x1 - x0
    xx = (np.arange(x0, x1, dtype=F)[None, :] - cx) / (w / 2)
    yy = (np.arange(y0, y1, dtype=F)[:, None] - y0) / h
    # arch: rounded top
    arch = (xx ** 2) * 0.75 + ((1 - yy) * 1.15) ** 2
    m = 1 - smooth(0.85, 1.0, arch)
    m = m * (1 - smooth(0.97, 1.0, np.abs(xx)))
    # receding light: brightest at a far point
    fx, fy = 0.0, 0.62
    dd = np.sqrt((xx - fx) ** 2 * 1.4 + ((yy - fy) * 1.6) ** 2)
    t = clamp01(1 - dd)
    rgb = mix(col('#04120a'), inner, (t ** 1.6)[..., None])
    rgb = rgb + light * (np.exp(-(dd / 0.08) ** 2) * 0.55)[..., None]
    # floor of the path
    floor_m = smooth(fy, fy + 0.1, yy) * (1 - smooth(-0.05, 0.1, np.abs(xx) - 0.08 - (yy - fy) * 1.9))
    ft = clamp01((yy - fy) / (1 - fy))
    rgb = mix(rgb, mix(col('#0a1a0c'), floor, (ft ** 1.3)[..., None]), floor_m[..., None] * 0.95)
    tex = snoise(hh, ww, 6, seed, 3)
    rgb = rgb * (0.85 + 0.3 * tex)[..., None]
    over(c.img[y0:y1, x0:x1], m, rgb)
    # silhouettes of trunks and hanging leaves inside
    lay, d = c.layer()
    rng = np.random.default_rng(seed)
    for k in range(5):
        tx = cx + rng.uniform(-0.38, 0.38) * w
        tw = w * rng.uniform(0.015, 0.035)
        d.polygon([(tx - tw, y0), (tx + tw, y0), (tx + tw * 1.2, yb - h * 0.32), (tx - tw * 1.2, yb - h * 0.32)],
                  fill=rgb255(col('#0c2412') * rng.uniform(0.8, 1.6)) + (255,))
    for k in range(26):
        lx = cx + rng.uniform(-0.45, 0.45) * w
        ly = y0 + rng.uniform(0.0, 0.35) * h
        L = w * rng.uniform(0.06, 0.14)
        draw_leaf(d, lx, ly, math.pi / 2 + rng.uniform(-0.6, 0.6), L, L * 0.4,
                  col('#14361a') * rng.uniform(0.7, 1.4), bend=0.2, rib=False)
    c.comp(lay, opacity=0.9)
    return m


def jungle_wall_across(c, cam, seed, Z=16.0, height=5.5, gap=None, palms=12, haze=col('#b8d2e0'),
                       far=True):
    """A wall of jungle across the view at depth Z (optionally with a path gap (x0, x1) virtual)."""
    rng = np.random.default_rng(seed)
    _, yb = cam.proj(0, 0, Z)
    sc = cam.f / Z
    if far:
        lay, d = c.layer()
        Zf = Z * 3
        scf = cam.f / Zf
        _, ybf = cam.proj(0, 0, Zf)

        def topf(x):
            return ybf - scf * (11 + 3 * math.sin(x / c.W * 9 + seed) + 2 * math.sin(x / c.W * 23))

        for i in range(palms // 2):
            px = rng.uniform(0, c.W)
            draw_palm(d, px, ybf + scf, scf * rng.uniform(15, 20), rng.uniform(-0.2, 0.2) * scf * 10,
                      seed + 300 + i)
        foliage_mass(c, d, topf, 0, c.W, yb + 5, seed + 5, JUNGLE, leaf=scf * 1.5, density=0.8,
                     base=col('#1d4f2f'))
        c.comp(lay, tint=haze, tint_amt=0.32)

    def top(x):
        return yb - sc * (height + 1.3 * math.sin(x / c.W * 11 + seed) + 0.8 * math.sin(x / c.W * 29 + 2 * seed))

    lay, d = c.layer()
    for i in range(palms):
        px = rng.uniform(-0.05, 1.05) * c.W
        if gap is not None and gap[0] * U - 60 < px < gap[1] * U + 60:
            continue
        draw_palm(d, px, yb - sc * 0.5, sc * rng.uniform(10, 15), rng.uniform(-0.25, 0.25) * sc * 9,
                  seed + 100 + i, frond_col=col('#2f7d32') * rng.uniform(0.85, 1.1))
    c.comp(lay)
    lay, d = c.layer()
    gapf = None
    if gap is not None:
        gx0, gx1 = gap[0] * U, gap[1] * U
        gcx, gw = (gx0 + gx1) / 2, gx1 - gx0
        gh = (yb - top(gcx)) * 0.75

        def gapf(x, y):
            u = (x - gcx) / (gw / 2)
            v = (yb - y) / gh
            return u * u * 0.75 + v * v * 1.15 < 1.5 and v > -0.3

    foliage_mass(c, d, top, -20, c.W + 20, yb + sc * 0.2, seed + 1, JUNGLE, leaf=sc * 1.0,
                 density=1.1, base=col('#0e3018'), gap=gapf)
    c.comp(lay, dapple=(sc * 6, 0.25, seed))
    if gap is not None:
        tunnel_opening(c, gcx, yb, gw, gh, seed + 7, floor=col('#a07a4a'))
        lay, d = c.layer()
        # leaves framing the opening
        for k in range(55):
            ang = rng.uniform(-0.1, 1.1) * math.pi
            r = 1.02 + rng.uniform(0.0, 0.12)
            x = gcx - math.cos(ang) * gw / 2 * r
            y = yb - math.sin(ang) * gh * r * 0.95
            if y > yb:
                continue
            pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
            inward = math.atan2((yb - gh * 0.4) - y, gcx - x) + rng.uniform(-0.6, 0.6)
            L = sc * rng.uniform(0.35, 0.7)
            bright = 0.45 + 0.45 * math.sin(ang) * rng.uniform(0.8, 1.2)
            draw_leaf(d, x, y, inward, L, L * 0.42, np.clip(pc * bright, 0, 1), bend=0.25)
        c.comp(lay)
    # tufts and fallen leaves where the jungle meets the sand, and its shadow on the sand
    a, box = mask_crop(c, polys=[[(0, yb - 4), (c.W, yb - 4), (c.W, yb + sc * 0.7), (0, yb + sc * 0.7)]],
                       blur=sc * 0.25)
    over(c.img, a * 0.35, col('#3a2a10'), box)
    lay, d = c.layer()
    for k in range(int(c.W / 40)):
        x = rng.uniform(0, c.W)
        if gap is not None and gx0 - 10 < x < gx1 + 10:
            continue
        y = yb + rng.uniform(-0.1, 0.25) * sc
        hgt = rng.uniform(0.3, 1.0)
        for j in range(int(rng.integers(4, 12))):
            draw_blade(d, x + rng.uniform(-14, 14), y, sc * hgt * rng.uniform(0.5, 1.1), rng.uniform(-0.5, 0.5) * sc,
                       sc * 0.07, np.clip(col('#3f7f2a') * rng.uniform(0.5, 1.1), 0, 1))
        if rng.random() < 0.5:
            draw_broadleaf_bush(d, x + 30, y, sc * rng.uniform(0.5, 0.9), col('#2f6f2a') * rng.uniform(0.7, 1.0),
                                seed + k, n=5)
    c.comp(lay)
    return yb, top


# --------------------------------------------------------------------------------------------
# Scenes: beach
# --------------------------------------------------------------------------------------------

SCENES = {}


def scene(name, full=False):
    def deco(fn):
        SCENES[name] = (fn, full)
        return fn
    return deco


HY = 63   # outdoor horizon (virtual)


def day_sky(c, seed, clouds=True, sun=(40, -10), horizon=HY, n=5):
    sky(c, horizon + 1, sun=sun, sun_r=60, sun_str=0.25)
    wisps(c, 4, 30, seed + 5, amount=0.22)
    if clouds:
        cloud_bank(c, horizon - 4, seed, n=n, size=(14, 34), shade=col('#a3b8d4'))
        rng = np.random.default_rng(seed + 3)
        for i in range(2):
            w = rng.uniform(30, 48)
            cloud(c, rng.uniform(20, 220), rng.uniform(16, 32), w, w * 0.36, seed * 50 + i)


def open_sea_view(c, seed, shore_z=9.0, wreck=False):
    cam = Cam(c, HY)
    day_sky(c, seed)

    def dist(X, Z):
        return Z - (shore_z + 1.0 * np.sin(X * 0.12 + 1) + 0.6 * np.sin(X * 0.31) + 0.8 * (fbm(X * 0.08, 0, seed + 9, 3) - 0.5))

    beach_scene(c, cam, seed, None, dist, sun_x=c.W * 0.2,
                waves=((1.2, 3.0), (6.5, 4.0), (15.0, 5.0)))
    return cam


@scene('beach_sea')
def bg_beach_sea(c):
    open_sea_view(c, 11)
    grains(c, 100, 12, density=0.02)


def wreck_boat(c, cam, X, Z, seed):
    """A small sailing boat lying on its side on black rocks: the deck faces us, the keel is
    up at the back, the broken mast and torn sail lie across the rocks in front."""
    sc = cam.f / Z
    x, y = cam.proj(X, 0, Z)
    rng = np.random.default_rng(seed)
    contact_shadow(c, x / U + 0.6 * sc / U, y / U + 0.1 * sc / U, 4.2 * sc / U, 0.5 * sc / U, 0.45)
    for i in range(5):
        rx = x + rng.uniform(-2.8, 3.2) * sc
        ry = y - rng.uniform(0.1, 0.3) * sc
        r = rng.uniform(0.6, 1.1) * sc
        paint_rock(c, rock_poly(rx, ry, r, r * 0.7, seed + i), col('#2e2c30'), seed + i, spec=0.3)
    L = 6.2 * sc
    hd = 1.0 * sc
    tilt = -0.1
    ct, st = math.cos(tilt), math.sin(tilt)
    cx, cy = x, y - 0.85 * sc

    def R(px, py):
        return (cx + px * ct - py * st, cy + px * st + py * ct)

    def prof(t):
        return max(0.0, math.sin(math.pi * (0.22 + 0.78 * t))) ** 0.55

    N = 30
    top, bot, keel = [], [], []
    for k in range(N + 1):
        t = k / N
        px = (t - 0.5) * L
        lift = (t ** 3) * 0.5 * sc
        p_ = prof(t)
        top.append(R(px, -hd * p_ - lift))
        bot.append(R(px, hd * p_ * 0.8 - lift * 0.6))
        keel.append(R(px + (0.15 * sc if k == N else 0), -hd * p_ - lift - 0.75 * sc * p_ ** 0.7))
    lay, d = c.layer()
    # bottom of the hull seen beyond the deck, up to the keel
    d.polygon(keel + top[::-1], fill=rgb255(col('#5a3d26')) + (255,))
    for j in range(1, 4):
        f = j / 4
        line = [(a_[0] + (b_[0] - a_[0]) * f, a_[1] + (b_[1] - a_[1]) * f) for a_, b_ in zip(top, keel)]
        d.line(line, fill=rgb255(col('#3e2a18')) + (255,), width=max(1, int(sc * 0.035)))
    d.line(keel, fill=rgb255(col('#2a1c10')) + (255,), width=max(2, int(sc * 0.14)))
    # the deck, facing us
    d.polygon(top + bot[::-1], fill=rgb255(col('#a88458')) + (255,))
    for j in range(1, 7):
        f = j / 7
        line = [(a_[0] + (b_[0] - a_[0]) * f, a_[1] + (b_[1] - a_[1]) * f) for a_, b_ in zip(top, bot)]
        d.line(line, fill=rgb255(col('#7a5a38')) + (255,), width=max(1, int(sc * 0.03)))
    # gunwales
    d.line(top, fill=rgb255(col('#6a4a2c')) + (255,), width=max(2, int(sc * 0.1)))
    d.line(bot, fill=rgb255(col('#d0ae7c')) + (255,), width=max(2, int(sc * 0.12)))
    # hatch and cabin
    hx, hy_ = R(-0.22 * L, -0.05 * sc)
    d.polygon([R(-0.34 * L, -0.45 * sc), R(-0.1 * L, -0.5 * sc), R(-0.1 * L, 0.35 * sc), R(-0.34 * L, 0.38 * sc)],
              fill=rgb255(col('#6e4c2e')) + (255,))
    d.polygon([R(-0.31 * L, -0.3 * sc), R(-0.14 * L, -0.33 * sc), R(-0.14 * L, 0.2 * sc), R(-0.31 * L, 0.22 * sc)],
              fill=(22, 15, 10, 255))
    # mast stump with splinters
    mx, my = R(0.08 * L, -0.05 * sc)
    r_ = 0.2 * sc
    d.ellipse((mx - r_, my - r_ * 0.8, mx + r_, my + r_ * 0.8), fill=rgb255(col('#4a3420')) + (255,))
    for k in range(5):
        a_ = rng.uniform(0, 2 * math.pi)
        d.polygon([(mx + math.cos(a_) * r_ * 0.6, my + math.sin(a_) * r_ * 0.5),
                   (mx + math.cos(a_ + 0.3) * r_ * 0.6, my + math.sin(a_ + 0.3) * r_ * 0.5),
                   (mx + math.cos(a_ + 0.15) * r_ * 1.5, my + math.sin(a_ + 0.15) * r_ * 1.2 - r_ * 0.4)],
                  fill=rgb255(col('#b08858')) + (255,))
    c.comp(lay)
    hull = keel + bot[::-1]
    a, box = mask_crop(c, polys=[hull], pad=6)
    lam, _ = shape_lam(a, sc * 0.8)
    tex = snoise(a.shape[0], a.shape[1], sc * 0.12, seed, 3)
    shade = 0.9 + 0.3 * lam + (tex - 0.5) * 0.35
    region = c.img[box[1]:box[3], box[0]:box[2]]
    region *= (1 + (shade[..., None] - 1) * a[..., None])
    # broken mast lying across the rocks in front, torn sail draped down to the sand
    lay, d = c.layer()
    m0 = R(0.02 * L, 0.55 * sc)
    m1 = (m0[0] + 4.6 * sc, m0[1] + 0.55 * sc)
    sail = [(m0[0] + 0.5 * sc, m0[1] + 0.05 * sc), (m1[0] - 0.4 * sc, m1[1] - 0.02 * sc),
            (m1[0] - 0.7 * sc, m1[1] + 0.55 * sc), (m1[0] - 1.1 * sc, m1[1] + 0.35 * sc),
            (m1[0] - 1.6 * sc, m1[1] + 0.85 * sc), (m0[0] + 2.2 * sc, m0[1] + 0.95 * sc),
            (m0[0] + 1.6 * sc, m0[1] + 0.7 * sc), (m0[0] + 0.9 * sc, m0[1] + 1.0 * sc)]
    d.polygon(sail, fill=rgb255(col('#e6dabd')) + (255,))
    # folds in the cloth
    for k in range(7):
        f0 = 0.1 + 0.11 * k
        f1 = f0 + 0.05
        p0 = (m0[0] + (m1[0] - m0[0]) * f0, m0[1] + (m1[1] - m0[1]) * f0)
        p1 = (m0[0] + (m1[0] - m0[0]) * f1, m0[1] + (m1[1] - m0[1]) * f1)
        dn = rng.uniform(0.55, 0.9) * sc
        d.polygon([p0, p1, (p1[0] - 0.1 * sc, p1[1] + dn), (p0[0] - 0.15 * sc, p0[1] + dn * 0.9)],
                  fill=rgb255(col('#bcae8e')) + (200,))
    d.line([m0, m1], fill=rgb255(col('#5e4228')) + (255,), width=max(3, int(sc * 0.2)))
    d.line([(m0[0], m0[1] - sc * 0.05), (m1[0], m1[1] - sc * 0.05)], fill=rgb255(col('#8a6640')) + (255,),
           width=max(1, int(sc * 0.06)))
    d.line([m1, (m1[0] + 0.3 * sc, m1[1] - 0.3 * sc)], fill=rgb255(col('#7a5a38')) + (255,),
           width=max(2, int(sc * 0.1)))
    d.line([R(0.48 * L, -0.4 * sc), (m1[0] - 0.2 * sc, m1[1])], fill=(50, 38, 26, 220), width=max(1, int(sc * 0.03)))
    c.comp(lay)
    for i in range(7):
        rx = x + rng.uniform(-3.3, 3.4) * sc
        ry = y + rng.uniform(0.15, 0.45) * sc
        r = rng.uniform(0.4, 0.85) * sc
        paint_rock(c, rock_poly(rx, ry, r, r * 0.6, seed + 20 + i), col('#2a282c'), seed + 20 + i, spec=0.3)


@scene('beach_wreck')
def bg_beach_wreck(c):
    cam = open_sea_view(c, 21, shore_z=10.5)
    wreck_boat(c, cam, -2.6, 16.0, 5)
    grains(c, 100, 22, density=0.02)


@scene('beach_along')
def bg_beach_along(c, end=False):
    seed = 31 if not end else 41
    cam = Cam(c, HY)
    day_sky(c, seed, sun=(30, -10))

    def dist(X, Z):
        xs = 3.0 + 0.06 * Z + 1.2 * np.sin(Z * 0.045 + seed) + 0.7 * np.sin(Z * 0.13)
        return X - xs

    beach_scene(c, cam, seed, None, dist, sun_x=c.W * 0.15,
                waves=((1.2, 3.0), (6.0, 4.0), (14.0, 5.0)), along_z=True)
    if end:
        headland(c, cam, seed, 75.0)
    jungle_edge_along(c, cam, seed + 1, z_far=75 if end else 500)
    grains(c, 96, seed + 2, density=0.015, x_range=(30, 200))


def cliff_face(c, pts, base, seed, R, light=LIGHT, streak=4, tex=1.0, amb=0.3, spec=0.1,
               lit_col=None, haze=None, haze_amt=0.0):
    """A big rock face from a polygon (working px): rounded shading + vertical strata."""
    a, box = mask_crop(c, polys=[pts], pad=8, blur=1.0)
    if a is None:
        return
    h, w = a.shape
    lam, hh = shape_lam(a, R, light)
    ns = snoise(max(4, h // streak), w, max(4, R * 0.5), seed, 5)
    ns = resize_arr(ns, w, h)
    nf = snoise(h, w, max(3, R * 0.12), seed + 1, 3)
    facets = bump_lam(ns * R * 0.8 * tex, 1.0, light)
    shade = clamp01(amb + (1 - amb) * (0.5 + 0.5 * lam) + facets * 0.7)
    shade = shade * (0.88 + (nf - 0.5) * 0.35)
    colr = base * shade[..., None] + (clamp01(lam + facets) ** 3 * spec)[..., None] * (
        lit_col if lit_col is not None else 1.0)
    if haze is not None:
        colr = mix(colr, haze, haze_amt)
    over(c.img, a, colr, box)
    return a, box


def headland(c, cam, seed, Z):
    """Rocky headland crossing the view at depth Z, jungle on top, surf at its foot."""
    rng = np.random.default_rng(seed)
    _, yb = cam.proj(0, 0, Z)
    sc = cam.f / Z
    n = 60
    top = []
    for i in range(n + 1):
        t = i / n
        x = -30 + (c.W * 0.86 + 30) * t
        hgt = 15 + 2.5 * math.sin(t * 5 + seed) + 1.2 * math.sin(t * 17) + rng.uniform(-0.4, 0.4)
        hgt *= 1 - smooth(0.62, 1.0, t) ** 1.3
        top.append((x, yb - max(0.6, hgt) * sc))
    pts = top + [(c.W * 0.9, yb + sc * 0.3), (-30, yb + sc * 0.6)]
    haze = col('#9fb4c8')
    cliff_face(c, pts, col('#6a5a4c'), seed, R=sc * 4.0, streak=2, spec=0.25, haze=haze, haze_amt=0.2)
    front = [(x_, y_ + sc * (4 + 2 * math.sin(i * 0.4))) for i, (x_, y_) in enumerate(top[:int(n * 0.8)])]
    front = front + [(front[-1][0] + sc * 3, yb + sc * 0.4), (-30, yb + sc * 0.6)]
    cliff_face(c, front, col('#4f443c'), seed + 2, R=sc * 2.5, streak=2, spec=0.2, haze=haze, haze_amt=0.12)
    # a sea stack off the point
    stack = rock_poly(c.W * 0.94, yb - sc * 2.6, sc * 2.6, sc * 3.2, seed + 4, flat_base=False)
    stack = [(x_, min(y_, yb + sc * 0.3)) for x_, y_ in stack]
    cliff_face(c, stack, col('#5e5046'), seed + 4, R=sc * 1.5, streak=2, spec=0.2, haze=haze, haze_amt=0.25)
    # jungle crown along the top of the headland
    lay, d = c.layer()
    for k in range(int(n * 0.75)):
        x_, y_ = top[k]
        if rng.random() < 0.45:
            draw_palm(d, x_ + rng.uniform(-5, 5), y_ + sc * 0.8, sc * rng.uniform(7, 11),
                      rng.uniform(-1, 1) * sc * 2, seed + 50 + k)
    for k in range(240):
        t = rng.uniform(0, 0.78)
        i = int(t * n)
        x_ = top[i][0] + rng.uniform(-8, 8)
        y_ = top[i][1] + sc * rng.uniform(-0.2, 1.4)
        pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
        L = sc * rng.uniform(0.8, 1.6)
        draw_leaf(d, x_, y_, -math.pi / 2 + rng.uniform(-1.5, 1.5), L, L * 0.45,
                  np.clip(pc * rng.uniform(0.7, 1.15), 0, 1), bend=0.3, rib=False)
    c.comp(lay, tint=haze, tint_amt=0.3)
    # boulders at the foot and surf against it
    for k in range(10):
        bx = rng.uniform(0.35, 0.95) * c.W
        r = sc * rng.uniform(0.8, 1.8)
        paint_rock(c, rock_poly(bx, yb + sc * 0.2, r, r * 0.6, seed + 70 + k), col('#3a3532'), seed + 70 + k)
    yy = np.arange(int(yb - sc * 2.5), int(yb + sc * 1.2))
    h = len(yy)
    x0 = int(c.W * 0.5)
    tex = snoise(h, c.W - x0, sc * 0.5, seed + 9, 4)
    vert = np.exp(-((yy[:, None] - (yb - sc * 0.2)) / (sc * 1.0)) ** 2)
    horiz = smooth(0.0, 0.25, np.linspace(0, 1, c.W - x0, dtype=F))[None, :]
    a = clamp01((tex - 0.42) * 3.0) * vert * horiz
    over(c.img[yy[0]:yy[-1] + 1, x0:], a, col('#f3fbfb'))


@scene('beach_end')
def bg_beach_end(c):
    bg_beach_along(c, end=True)


def inland_view(c, seed, gap):
    cam = Cam(c, HY)
    day_sky(c, seed, sun=(200, -20))
    X, Z, y0 = cam.ground()
    c.img[y0:] = sand_rgb(X, Z, seed)
    yb, top = jungle_wall_across(c, cam, seed, Z=17.0, gap=gap)
    if gap is not None:
        # trodden path of darker sand leading into the gap, with footprints
        gx0, gx1 = gap[0] * U, gap[1] * U
        rows = c.H - int(yb)
        yy = np.arange(int(yb), c.H, dtype=F)[:, None]
        t = (yy - yb) / (c.H - yb)
        half = (gx1 - gx0) * 0.32 + t * c.W * 0.16
        wob = (snoise(rows, 1, 40, 77, 3)[:, :1] - 0.5) * 60
        edge = np.abs(c.xs - (c.W / 2 + wob)) - half
        en = snoise(rows, c.W, 10, 78, 3)
        m = 1 - smooth(-20, 25, edge + (en - 0.5) * 60)
        over(c.img[int(yb):], m * 0.4, col('#9a7444'))
        rng = np.random.default_rng(seed + 31)
        lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for k in range(26):
            tt = rng.random() ** 0.8
            y = yb + 10 + (c.H - yb - 10) * tt
            sz = 6 + 26 * ((y - yb) / (c.H - yb))
            x = c.W / 2 + rng.uniform(-1, 1) * ((gx1 - gx0) * 0.3 + tt * c.W * 0.13)
            d.ellipse((x - sz * 0.45, y - sz * 0.22, x + sz * 0.45, y + sz * 0.22), fill=(110, 78, 40, 60))
        c.comp(lay.filter(ImageFilter.GaussianBlur(2)))
    grains(c, 90, seed + 2, density=0.02)
    return cam


@scene('beach_land')
def bg_beach_land(c):
    inland_view(c, 51, gap=(96, 144))


@scene('beach_land_wall')
def bg_beach_land_wall(c):
    inland_view(c, 61, gap=None)


# --------------------------------------------------------------------------------------------
# Deep jungle helpers
# --------------------------------------------------------------------------------------------

def trunk(c, xb, yb, xt, yt, wb, wt, base, seed, haze=None, haze_amt=0.0, roots=0.0, moss=0.3,
          light_side=-1.0):
    """Cylindrical tree trunk (working px) with bark streaks, lit from one side."""
    polys = [[(xb - wb, yb), (xb + wb, yb), (xt + wt, yt), (xt - wt, yt)]]
    rng = np.random.default_rng(seed)
    if roots:
        for k in range(4):
            side = -1 if k % 2 == 0 else 1
            spread = wb * roots * rng.uniform(1.2, 2.2)
            h = (yb - yt) * rng.uniform(0.08, 0.16) * roots
            off = rng.uniform(-0.4, 0.4) * wb
            polys.append([(xb + off, yb - h), (xb + off + side * spread, yb + wb * 0.1),
                          (xb + off + side * spread * 0.4, yb + wb * 0.05), (xb, yb)])
    a, box = mask_crop(c, polys=polys, pad=4, blur=0.8)
    if a is None:
        return
    x0, y0, x1, y1 = box
    h, w = a.shape
    yy = np.arange(y0, y1, dtype=F)[:, None]
    xx = np.arange(x0, x1, dtype=F)[None, :]
    t = clamp01((yy - yt) / max(1, (yb - yt)))
    cx = xt + (xb - xt) * t
    hw = wt + (wb - wt) * t
    u = np.clip((xx - cx) / hw, -1.6, 1.6)
    shade = clamp01(0.3 + 0.55 * (0.55 + 0.45 * light_side * -u * 0.9) * np.sqrt(clamp01(1.2 - u * u * 0.45)))
    streak = resize_arr(snoise(max(4, h // 10), w, max(3, wb * 0.25), seed, 4), w, h)
    fine = snoise(h, w, max(2, wb * 0.08), seed + 1, 2)
    shade = shade * (0.75 + 0.5 * streak) * (0.9 + 0.2 * fine)
    rgb = base * shade[..., None]
    if moss:
        mn = snoise(h, w, max(4, wb * 0.6), seed + 2, 3)
        mm = clamp01((mn - 0.55) * 4) * moss * clamp01(0.5 - u * 0.5 * light_side)
        rgb = mix(rgb, col('#4a7a2a') * shade[..., None] * 1.1, mm[..., None])
    if haze is not None:
        rgb = mix(rgb, haze, haze_amt)
    over(c.img, a, rgb, box)


def liana(d, x0, y0, x1, y1, sag, color, width, leaves=0, rng=None, leaf_col=None):
    rng = rng or np.random.default_rng(0)
    pts = []
    for k in range(25):
        t = k / 24
        pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)))
    d.line(pts, fill=rgb255(color) + (255,), width=int(width), joint='curve')
    for k in range(leaves):
        px, py = pts[int(rng.integers(1, 24))]
        L = width * rng.uniform(4, 8)
        draw_leaf(d, px, py, rng.uniform(0, math.pi), L, L * 0.5,
                  np.clip((leaf_col if leaf_col is not None else col('#2f6f2a')) * rng.uniform(0.7, 1.2), 0, 1),
                  bend=0.3, rib=False)


def hanging_vine(d, x, y0, length, color, width, rng, leaf_col=col('#2f6f2a'), sway=0.0):
    pts = []
    for k in range(20):
        t = k / 19
        pts.append((x + sway * length * t * t + math.sin(t * 5 + x) * width, y0 + length * t))
    d.line(pts, fill=rgb255(color) + (255,), width=int(width), joint='curve')
    for k in range(int(length / (width * 5))):
        px, py = pts[int(rng.integers(0, 20))]
        L = width * rng.uniform(3, 6)
        side = rng.choice([-1, 1])
        draw_leaf(d, px, py, math.pi / 2 + side * rng.uniform(0.4, 1.2), L, L * 0.5,
                  np.clip(leaf_col * rng.uniform(0.7, 1.25), 0, 1), bend=0.2, rib=False)


def light_shafts(c, seed, n=5, x_range=(0.1, 0.8), slant=0.35, color=col('#fff6c8'), strength=0.22,
                 y1=None, width=(0.02, 0.06)):
    rng = np.random.default_rng(seed)
    m, d = c.mask()
    y1 = y1 or c.H
    for i in range(n):
        x = rng.uniform(*x_range) * c.W
        w0 = rng.uniform(*width) * c.W
        w1 = w0 * rng.uniform(1.6, 2.6)
        dx = slant * y1
        a = int(rng.uniform(0.4, 1.0) * 255)
        d.polygon([(x - w0, -10), (x + w0, -10), (x + dx + w1, y1), (x + dx - w1, y1)], fill=a)
    a = m2a(m.resize((c.W // 4, c.H // 4)).filter(ImageFilter.GaussianBlur(10)))
    a = resize_arr(a, c.W, c.H)
    fade = np.linspace(1.0, 0.25, c.H, dtype=F)[:, None]
    n_ = resize_arr(snoise(c.H // 8, c.W // 8, 30, seed, 3), c.W, c.H)
    c.img += (a * fade * strength * (0.6 + 0.8 * n_))[..., None] * color


def mist(c, y0_v, y1_v, seed, color, amount=0.4, scale=60):
    y0, y1 = int(y0_v * U), int(y1_v * U)
    h = y1 - y0
    n = resize_arr(snoise(max(4, h // 6), c.W // 6, scale / 6, seed, 4), c.W, h)
    n = resize_arr(resize_arr(n, c.W // 3, h), c.W, h)
    band = np.clip(np.sin(np.linspace(0, math.pi, h, dtype=F)), 0, 1)[:, None] ** 0.7
    a = clamp01(0.3 + (n - 0.5) * 1.6) * band * amount
    over(c.img[y0:y1], a, color)


def jungle_ground(c, cam, seed, path=True, fog=col('#5f8a5a'), fog_d=30.0, path_w=1.0,
                  path_col=col('#8a6c44')):
    X, Z, y0 = cam.ground()
    litter = fbm(X * 1.4, Z * 1.4, seed, 4)
    patches = fbm(X * 0.25, Z * 0.25, seed + 1, 3)
    rgb = mix(col('#2a2213'), col('#5d4a2a'), clamp01(litter * 1.3 - 0.15)[..., None])
    rgb = mix(rgb, col('#304a1c'), clamp01((patches - 0.45) * 3)[..., None] * 0.7)
    pm = None
    if path:
        pc = 0.9 * np.sin(Z * 0.11 + seed) + 0.4 * np.sin(Z * 0.31)
        en = fbm(X * 0.8, Z * 0.8, seed + 2, 3)
        pm = 1 - smooth(path_w * 0.6, path_w * 1.1, np.abs(X - pc) + (en - 0.5) * 0.6)
        prgb = mix(path_col * 0.75, path_col * 1.15, fbm(X * 2.5, Z * 2.5, seed + 3, 3)[..., None])
        rgb = mix(rgb, prgb, pm[..., None])
    rgb = mix(rgb, fog, smooth(2.0, fog_d, Z)[..., None])
    c.img[y0:] = rgb
    return X, Z, y0, pm


def jungle_backdrop(c, seed, hy_v=70, fog=col('#7fae80'), top=col('#c8e4b8'), layers=3, path_gap=None,
                    dark=0.0):
    """Misty layered jungle depth: background colour, distant trunks and foliage layers."""
    vgrad(c, [(0.0, top), (0.45, mix(top, fog, 0.6)), (1.0, fog * 0.8)], 0, int(hy_v * U) + 20)
    rng = np.random.default_rng(seed)
    hy = hy_v * U
    for L in range(layers):
        depth = 1 - L / layers            # 1 = far
        haze_amt = 0.75 * depth + 0.1
        n_tr = 7 + L * 2
        for k in range(n_tr):
            x = rng.uniform(-0.05, 1.05) * c.W
            if path_gap and path_gap[0] * U < x < path_gap[1] * U and L > 0:
                continue
            w = U * rng.uniform(1.2, 2.5) * (1 + L * 0.8)
            ybase = hy + U * (2 + L * 5)
            trunk(c, x, ybase, x + rng.uniform(-1, 1) * w, -20, w, w * 0.7, col('#5a4a3a'), seed * 10 + L * 30 + k,
                  haze=fog, haze_amt=haze_amt, roots=0.6 if L > 0 else 0, moss=0.4)
        lay, d = c.layer(shadows=L > 0)
        # canopy masses across the top
        yt = U * (8 + 10 * depth)

        def topf(x, L=L):
            return -U * 10 + U * 4 * math.sin(x / c.W * 7 + L * 2 + seed)

        def botf_mass(x0, x1, ybot, s):
            pass

        foliage_mass(c, d, topf, -20, c.W + 20, yt + U * 8, seed + L * 7, JUNGLE, leaf=U * (3 + 2.5 * L),
                     density=0.9, base=col('#1f4a26'))
        # undergrowth band at the foot of this layer
        ug_top = hy - U * (6 - L * 2) * (1.2 - depth * 0.6)

        def ugf(x, L=L):
            return ug_top + U * 3 * math.sin(x / c.W * 13 + L * 5 + seed) + U * 1.5 * math.sin(x / c.W * 37)

        gap = None
        if path_gap and L > 0:
            gx0, gx1 = path_gap[0] * U, path_gap[1] * U
            gap = lambda x, y, gx0=gx0, gx1=gx1: gx0 < x < gx1
        foliage_mass(c, d, ugf, -20, c.W + 20, hy + U * (3 + L * 6), seed + L * 11 + 3, JUNGLE,
                     leaf=U * (2.5 + 2.5 * L), density=0.9, base=col('#163a1e'), gap=gap,
                     kinds=('lance', 'broad', 'frond', 'frond'))
        if gap:
            # clear the base fill inside the path gap again by redrawing the background there
            pass
        c.comp(lay, tint=fog, tint_amt=haze_amt * 0.85, dapple=(U * 30, 0.2, seed + L))
        if dark:
            c.img *= 1 - dark * 0.15


def frame_foliage(c, seed, sides=(True, True), top=True, dark=0.55, blur=0, scale=1.0, inset=0.0):
    """Big near leaves framing the picture edges (in shadow, slightly out of focus)."""
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    for side in (0, 1):
        if not sides[side]:
            continue
        for k in range(int(26 * scale)):
            y = rng.uniform(-0.1, 1.05) * c.H
            x = (rng.uniform(-0.08, 0.12 + inset) if side == 0 else rng.uniform(0.88 - inset, 1.08)) * c.W
            a = (0 if side == 0 else math.pi) + rng.uniform(-1.0, 1.0)
            L = U * rng.uniform(14, 30) * scale
            pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
            draw_leaf(d, x, y, a, L, L * rng.uniform(0.3, 0.5), np.clip(pc * dark * rng.uniform(0.7, 1.3), 0, 1),
                      bend=rng.uniform(0.1, 0.5))
        for k in range(int(5 * scale)):
            y = rng.uniform(0.2, 1.0) * c.H
            x = (rng.uniform(-0.05, 0.05) if side == 0 else rng.uniform(0.95, 1.05)) * c.W
            a = (0 if side == 0 else math.pi) + rng.uniform(-0.9, 0.5)
            draw_frond(d, x, y, a, U * rng.uniform(40, 60) * scale, np.clip(col('#2a6a2a') * dark * 1.3, 0, 1),
                       droop=0.5, leaflet=0.3, rng=rng)
    if top:
        for k in range(int(20 * scale)):
            x = rng.uniform(-0.05, 1.05) * c.W
            y = rng.uniform(-0.12, 0.05) * c.H
            a = math.pi / 2 + rng.uniform(-1.1, 1.1)
            L = U * rng.uniform(10, 22) * scale
            pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
            draw_leaf(d, x, y, a, L, L * 0.4, np.clip(pc * dark * rng.uniform(0.8, 1.4), 0, 1), bend=0.3)
    c.comp(lay, blur=blur)


def ferns_along(c, seed, rows, x_fn, size_fn, color=col('#3f8a34'), n=10, alpha=255):
    """Ferns placed along the ground at screen rows (working px)."""
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    items = []
    for i in range(n):
        y = rng.uniform(*rows)
        items.append((y, x_fn(y, rng)))
    items.sort()
    for y, x in items:
        sz = size_fn(y)
        if rng.random() < 0.6:
            draw_fern(d, x, y, sz, np.clip(color * rng.uniform(0.7, 1.15), 0, 1), int(rng.integers(0, 1 << 30)),
                      n=int(rng.integers(6, 11)))
        else:
            draw_broadleaf_bush(d, x, y, sz * 0.8, np.clip(col('#2f7a30') * rng.uniform(0.6, 1.1), 0, 1),
                                int(rng.integers(0, 1 << 30)), n=int(rng.integers(5, 9)))
    c.comp(lay)


# --------------------------------------------------------------------------------------------
# Scenes: jungle
# --------------------------------------------------------------------------------------------

def deep_jungle(c, seed, path=True):
    hy_v = 70
    cam = Cam(c, hy_v, h=1.7)
    jungle_ground(c, cam, seed, path=path, fog=col('#5f8a5a'), fog_d=22)
    gap = (100, 140) if path else None
    jungle_backdrop(c, seed, hy_v=hy_v, path_gap=gap)
    # the ground again in front of the undergrowth (the backdrop covers the far ground)
    X, Z, y0 = cam.ground()
    return cam


@scene('jungle_path')
def bg_jungle_path(c):
    seed = 71
    hy_v = 70
    cam = Cam(c, hy_v)
    vgrad(c, [(0, col('#c8e4b8')), (1, col('#5f8a5a'))], 0, c.H)
    jungle_backdrop(c, seed, hy_v=hy_v, path_gap=(106, 134))
    # ground (only in front of the undergrowth): draw it as an overlay from y = hy+?
    X, Z, y0 = cam.ground(int((hy_v + 6) * U))
    gnd = np.zeros((c.H - y0, c.W, 3), F)
    tmp = Canvas.__new__(Canvas)
    _ = tmp
    litter = fbm(X * 1.4, Z * 1.4, seed, 4)
    patches = fbm(X * 0.25, Z * 0.25, seed + 1, 3)
    gnd = mix(col('#2a2213'), col('#5d4a2a'), clamp01(litter * 1.3 - 0.15)[..., None])
    gnd = mix(gnd, col('#304a1c'), clamp01((patches - 0.45) * 3)[..., None] * 0.7)
    pc = 0.5 * np.sin(Z * 0.15 + 1.0)
    en = fbm(X * 0.8, Z * 0.8, seed + 2, 3)
    pm = 1 - smooth(0.55, 1.0, np.abs(X - pc) + (en - 0.5) * 0.5)
    prgb = mix(col('#6a5236'), col('#a4865a'), fbm(X * 2.5, Z * 2.5, seed + 3, 3)[..., None])
    gnd = mix(gnd, prgb, pm[..., None])
    gnd = mix(gnd, col('#5f8a5a'), smooth(4.0, 26.0, Z)[..., None])
    fade = smooth(0, U * 5, np.arange(c.H - y0, dtype=F))[:, None]
    over(c.img[y0:], fade * 1.0, gnd)
    light_shafts(c, seed, n=6, x_range=(0.05, 0.75), slant=0.3, strength=0.28)
    # ferns and bushes either side of the path
    hy = hy_v * U
    ferns_along(c, seed + 1, (hy + U * 10, c.H + U * 5),
                lambda y, r: (r.uniform(-0.1, 0.36) if r.random() < 0.5 else r.uniform(0.64, 1.1)) * c.W
                if y > hy + U * 25 else (r.uniform(0.0, 0.42) if r.random() < 0.5 else r.uniform(0.58, 1.0)) * c.W,
                lambda y: (y - hy) * 0.55 + U * 3, n=26)
    lay, d = c.layer()
    rng = np.random.default_rng(seed + 5)
    for k in range(7):
        x = rng.uniform(0.0, 1.0) * c.W
        hanging_vine(d, x, -10, c.H * rng.uniform(0.25, 0.6), col('#3a3020'), U * 0.5, rng, sway=rng.uniform(-0.1, 0.1))
    liana(d, -10, U * 20, c.W * 0.45, U * 6, U * 18, col('#3a2e1e'), U * 0.9, leaves=10, rng=rng)
    liana(d, c.W * 0.55, U * 4, c.W + 10, U * 30, U * 14, col('#3a2e1e'), U * 0.8, leaves=8, rng=rng)
    c.comp(lay)
    frame_foliage(c, seed + 9, dark=0.5, blur=3)
    vignette(c, 0.45, 2.4)
    grade(c, sat=1.08, contrast=1.05)


@scene('jungle_wall')
def bg_jungle_wall(c):
    seed = 81
    hy_v = 70
    vgrad(c, [(0, col('#c8e4b8')), (1, col('#5f8a5a'))], 0, c.H)
    jungle_backdrop(c, seed, hy_v=hy_v, layers=2)
    # impenetrable undergrowth right ahead: big leaves, ferns and tangled lianas
    rng = np.random.default_rng(seed)
    lay, d = c.layer()

    def top(x):
        return U * (22 + 8 * math.sin(x / c.W * 6 + 1) + 4 * math.sin(x / c.W * 17))

    foliage_mass(c, d, top, -40, c.W + 40, c.H + 40, seed + 3, JUNGLE, leaf=U * 7.5, density=1.25,
                 base=col('#0c2a14'), kinds=('lance', 'broad', 'broad', 'frond'))
    c.comp(lay, dapple=(U * 30, 0.3, seed))
    lay, d = c.layer()
    for k in range(8):
        liana(d, rng.uniform(-0.1, 0.6) * c.W, rng.uniform(0.1, 0.5) * c.H, rng.uniform(0.4, 1.1) * c.W,
              rng.uniform(0.2, 0.7) * c.H, U * rng.uniform(5, 15), col('#3a2e1e'), U * rng.uniform(0.5, 1.0),
              leaves=6, rng=rng)
    for k in range(10):
        x = rng.uniform(0.05, 0.95) * c.W
        draw_broadleaf_bush(d, x, c.H + U * 4, U * rng.uniform(16, 26), col('#2f7a30') * rng.uniform(0.55, 0.9),
                            seed + k, n=7)
    c.comp(lay)
    light_shafts(c, seed, n=4, x_range=(0.1, 0.6), slant=0.3, strength=0.18)
    frame_foliage(c, seed + 9, dark=0.45, blur=3, scale=0.8)
    vignette(c, 0.45, 2.4)
    grade(c, sat=1.08, contrast=1.05)


@scene('jungle_beach')
def bg_jungle_beach(c):
    seed = 91
    open_sea_view(c, seed, shore_z=24.0)
    grade(c, gamma=1.08, lift=0.06)
    # opening in the foliage around the centre
    rng = np.random.default_rng(seed)
    cx, cy = 120 * U, 66 * U
    rx, ry = 58 * U, 44 * U
    m, md = c.mask()
    md.rectangle((0, 0, c.W, c.H), fill=255)
    pts = []
    for k in range(64):
        a = k / 64 * 2 * math.pi
        r = 1 + 0.12 * math.sin(a * 5 + 1) + 0.06 * math.sin(a * 11)
        pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
    md.polygon(pts, fill=0)
    hole = m2a(m, blur=U * 0.7)
    # the dark leafy surround (only outside the opening)
    lay0, d0 = c.layer()
    foliage_mass(c, d0, lambda x: -U * 12, -40, c.W + 40, c.H + 40, seed + 4, JUNGLE, leaf=U * 7, density=1.0,
                 base=col('#081a0c'), kinds=('lance', 'broad', 'frond'))
    im0 = lay0.image()
    a0 = np.asarray(im0, F) / 255.0
    rgb0 = a0[..., :3] * 0.45
    over(c.img, a0[..., 3] * hole, rgb0)
    # jungle floor leading out to the sand
    yb_open = cy + ry * 0.8
    gy = int(yb_open)
    rows = c.H - gy
    t = np.linspace(0, 1, rows, dtype=F)[:, None]
    tex = snoise(rows, c.W, U * 1.5, seed + 2, 4)
    floor = mix(col('#3a2e1a'), col('#6a5434'), tex[..., None]) * (0.6 + 0.4 * t)[..., None]
    pathm = 1 - smooth(0, U * 6, np.abs(c.xs - cx) - (rx * 0.35 + t * c.W * 0.25))
    floor = mix(floor, col('#8a6c46') * (0.8 + 0.4 * tex)[..., None], (pathm * 0.8)[..., None])
    fm = smooth(0, U * 3, np.arange(rows, dtype=F))[:, None] * np.ones((1, c.W), F)
    over(c.img[gy:], fm * 1.0, floor)
    ferns_along(c, seed + 8, (gy + U * 4, c.H + U * 4),
                lambda y, r: (r.uniform(-0.1, 0.3) if r.random() < 0.5 else r.uniform(0.7, 1.1)) * c.W,
                lambda y: (y - gy) * 0.6 + U * 5, n=14, color=col('#2f6a2a'))
    lay, d = c.layer()
    # leaves around the opening, backlit
    for k in range(260):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.9, 1.9) if k % 2 else rng.uniform(0.92, 1.12)
        x = cx + math.cos(a) * rx * r
        y = cy + math.sin(a) * ry * r
        inward = math.atan2(cy - y, cx - x) + rng.uniform(-0.8, 0.8)
        L = U * rng.uniform(6, 16) * (0.7 + 0.4 * r)
        pc = JUNGLE[int(rng.integers(0, len(JUNGLE)))]
        near = smooth(1.3, 0.95, r)
        bright = 0.35 + 0.6 * near * rng.uniform(0.7, 1.2)
        draw_leaf(d, x, y, inward, L, L * rng.uniform(0.3, 0.5), np.clip(pc * bright, 0, 1), bend=0.25)
    for k in range(6):
        side = -1 if k % 2 else 1
        x = cx + side * rx * rng.uniform(1.0, 1.5)
        y = rng.uniform(0.2, 0.9) * c.H
        draw_frond(d, x, y, (math.pi if side > 0 else 0) + rng.uniform(-0.6, 0.3), U * rng.uniform(35, 50),
                   col('#2a5a26') * 0.8, droop=0.5, rng=rng)
    c.comp(lay)
    # light bleeding round the edges of the opening
    bloom = gblur(1 - hole, U * 6)
    c.img += (bloom * hole * 0.3)[..., None] * col('#fff2c0')
    frame_foliage(c, seed + 3, dark=0.35, blur=4, scale=0.8)
    vignette(c, 0.5, 2.2)


def flower(d, x, y, r, color, center=col('#ffe066'), petals=5, rot=0.0, alpha=255):
    for k in range(petals):
        a = rot + k / petals * 2 * math.pi
        px = x + math.cos(a) * r * 0.55
        py = y + math.sin(a) * r * 0.4
        d.ellipse((px - r * 0.5, py - r * 0.36, px + r * 0.5, py + r * 0.36),
                  fill=rgb255(np.clip(color * (1.05 - 0.15 * math.sin(a)), 0, 1)) + (alpha,))
    d.ellipse((x - r * 0.2, y - r * 0.15, x + r * 0.2, y + r * 0.15), fill=rgb255(center) + (alpha,))


def meadow(c, cam, seed, y_top, flowers=True, grass_col=col('#5aa23a')):
    """Grassy ground with flowers (from screen row y_top working px)."""
    X, Z, y0 = cam.ground(int(y_top))
    n = fbm(X * 0.6, Z * 0.6, seed, 4)
    n2 = fbm(X * 3, Z * 3, seed + 1, 3)
    rgb = mix(grass_col * 0.55, grass_col * 1.15, clamp01(n * 1.2 - 0.1 + (n2 - 0.5) * 0.4 * np.exp(-Z / 8))[..., None])
    pat = fbm(X * 0.15, Z * 0.15, seed + 2, 3)
    rgb = mix(rgb, mix(col('#3a5a22'), col('#7a6a3a'), n2[..., None]), (clamp01((pat - 0.55) * 4) * 0.5)[..., None])
    rgb = mix(rgb, col('#9ab88a'), smooth(10, 60, Z)[..., None] * 0.3)
    c.img[y0:] = rgb
    rng = np.random.default_rng(seed)
    lay, d = c.layer(shadows=False)
    hy = cam.hy
    items = []
    for k in range(2600):
        y = y0 + (c.H - y0) * rng.random() ** 0.7
        items.append((y, rng.uniform(-20, c.W + 20)))
    items.sort()
    palette = [col('#e8323c'), col('#ffd23a'), col('#ff7ab8'), col('#ff8a2a'), col('#b05ae0'), col('#ffffff')]
    for y, x in items:
        sc = (y - hy) / (c.H - hy)
        hgt = U * (2 + 7 * sc) * rng.uniform(0.6, 1.3)
        cc = np.clip(grass_col * rng.uniform(0.55, 1.25), 0, 1)
        draw_blade(d, x, y, hgt, rng.uniform(-0.5, 0.5) * hgt, U * 0.35 * (0.5 + sc), cc)
        if flowers and rng.random() < 0.12:
            fc = palette[int(rng.integers(0, len(palette)))]
            fr = U * (0.6 + 2.2 * sc) * rng.uniform(0.7, 1.2)
            fx, fy = x + rng.uniform(-0.3, 0.3) * hgt, y - hgt * rng.uniform(0.6, 1.0)
            d.line([(fx, fy), (x, y)], fill=rgb255(cc * 0.8) + (255,), width=max(1, int(U * 0.15 * (0.5 + sc))))
            flower(d, fx, fy, fr, fc, rot=rng.uniform(0, 6))
    c.comp(lay)


def exotic_flowers(c, seed, n=6, region=((0.0, 0.25), (0.75, 1.0)), y_range=(0.6, 1.0)):
    """Big hibiscus-like blooms and heliconia near the frame edges."""
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    for k in range(n):
        reg = region[k % len(region)]
        x = rng.uniform(*reg) * c.W
        y = rng.uniform(*y_range) * c.H
        draw_broadleaf_bush(d, x, y + U * 8, U * rng.uniform(10, 16), col('#2f7a30') * rng.uniform(0.7, 1.0),
                            seed + k, n=7)
        for j in range(int(rng.integers(2, 5))):
            fx = x + rng.uniform(-8, 8) * U
            fy = y + rng.uniform(-6, 4) * U
            r = U * rng.uniform(2.5, 4.0)
            colr = [col('#e8203a'), col('#ff5a9a'), col('#ff8c1a'), col('#ffcf2a')][int(rng.integers(0, 4))]
            flower(d, fx, fy, r * 1.4, colr * 0.75, center=colr * 0.5, rot=rng.uniform(0, 6))
            flower(d, fx, fy, r, colr, center=col('#fff0a0'), rot=rng.uniform(0, 6))
            d.line([(fx, fy), (fx + r * 0.6, fy - r * 0.9)], fill=rgb255(col('#ffe080')) + (255,), width=max(1, int(r * 0.08)))
    c.comp(lay)


def tree_line(c, cam, seed, Z, n=7, haze=col('#b8d2e0'), haze_amt=0.15, x_range=(0.0, 1.0), height=(10, 16)):
    """Broad-crowned rainforest trees standing at depth Z."""
    rng = np.random.default_rng(seed)
    sc = cam.f / Z
    _, yb = cam.proj(0, 0, Z)
    for k in range(n):
        x = rng.uniform(*x_range) * c.W
        hgt = rng.uniform(*height) * sc
        r = hgt * rng.uniform(0.28, 0.38)
        trunk(c, x, yb, x + rng.uniform(-0.1, 0.1) * hgt, yb - hgt * 0.8, sc * 0.35, sc * 0.22, col('#6a5a48'),
              seed + k, haze=haze, haze_amt=haze_amt, roots=0.5)
        lay, d = c.layer()
        tree_canopy(d, x, yb - hgt * 0.85, r, JUNGLE, seed + 40 + k, leaf=sc * 1.1,
                    n=int((r / (sc * 1.1)) ** 2 * 16))
        c.comp(lay, tint=haze, tint_amt=haze_amt)


@scene('clearing')
def bg_clearing(c):
    seed = 101
    cam = Cam(c, HY)
    day_sky(c, seed, sun=(60, -10), n=3)
    meadow(c, cam, seed, cam.hy)
    tree_line(c, cam, seed + 3, 40.0, n=8, haze_amt=0.0)
    yb, top = jungle_wall_across(c, cam, seed + 1, Z=26.0, height=5.0, palms=10, far=False)
    # enclosing jungle comes closer on both sides
    for side in (0, 1):
        lay, d = c.layer()
        if side == 0:
            x0, x1 = -40, c.W * 0.24
        else:
            x0, x1 = c.W * 0.76, c.W + 40
        ybot = c.H * 0.84

        def tf(x, side=side):
            u = (x - x0) / (x1 - x0) if side == 1 else (x1 - x) / (x1 - x0)   # 0 at the inner edge
            u = min(1.0, max(0.0, u))
            return ybot - (ybot - U * 6) * math.sqrt(max(0.0, 1 - (1 - u) ** 2)) + U * 3 * math.sin(x * 0.02)

        tx = x1 if side == 0 else x0
        trunk(c, tx - U * 10 if side == 0 else tx + U * 10, ybot, tx, -20, U * 3.5, U * 2.5, col('#6a5a48'), seed + 50 + side,
              roots=0.8)
        foliage_mass(c, d, tf, x0, x1, c.H * 0.9, seed + 5 + side, JUNGLE, leaf=U * 6.5, density=1.1,
                     base=col('#0e3018'), kinds=('lance', 'broad', 'broad', 'frond'))
        c.comp(lay, dapple=(U * 20, 0.25, seed))
    rng = np.random.default_rng(seed)
    lay, d = c.layer(shadows=False)
    palette = [col('#e8323c'), col('#ffd23a'), col('#ff7ab8'), col('#ff8a2a'), col('#b05ae0')]
    for k in range(500):
        y = rng.uniform(0.82, 1.02) * c.H
        x = rng.uniform(-0.02, 1.02) * c.W
        hgt = U * rng.uniform(5, 11)
        draw_blade(d, x, y, hgt, rng.uniform(-0.5, 0.5) * hgt, U * 0.5, np.clip(col('#5aa23a') * rng.uniform(0.5, 1.2), 0, 1))
        if rng.random() < 0.08:
            fx, fy = x, y - hgt
            flower(d, fx, fy, U * rng.uniform(1.6, 2.6), palette[int(rng.integers(0, 5))], rot=rng.uniform(0, 6))
    c.comp(lay)
    exotic_flowers(c, seed + 7, n=5)
    vignette(c, 0.25, 2.5)
    grade(c, sat=1.06)


# --------------------------------------------------------------------------------------------
# Masonry, bamboo, thatch
# --------------------------------------------------------------------------------------------

def hash2(i, j, seed=0):
    """Deterministic pseudo-random value in [0, 1) per integer cell."""
    h = (i.astype(np.int64) * 374761393 + j.astype(np.int64) * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF).astype(F) / 65536.0


def masonry(su, sv, bw, bh, seed, base, mortar=0.12, var=0.25, bevel=0.5, rough=1.0, offset=0.5,
            mortar_col=None):
    """Stone block texture from surface coordinates (any units). Returns (rgb, edge_lam)."""
    row = np.floor(sv / bh)
    shift = (row % 2) * offset * bw + hash2(row, row * 0 + 7, seed) * bw * 0.3
    colm = np.floor((su + shift) / bw)
    fu = (su + shift) / bw - colm
    fv = sv / bh - row
    rnd = hash2(colm, row, seed)
    rnd2 = hash2(colm, row, seed + 1)
    # distance to the block edge (in block units, with a little wobble)
    wob = (fbm(su * 0.7 / bw, sv * 0.7 / bh, seed + 3, 2) - 0.5) * 0.06 * rough
    du = np.minimum(fu, 1 - fu) * bw / bh
    dv = np.minimum(fv, 1 - fv)
    de = np.minimum(du, dv) + wob
    m = smooth(mortar * 0.5, mortar, de)
    # bevel: lit top / left edges, dark bottom / right
    bev = (smooth(mortar * 2.5, mortar, fv * 1.0) * 0.9 - smooth(mortar * 2.5, mortar, (1 - fv)) * 0.9
           + smooth(mortar * 2.0 * bh / bw, mortar * bh / bw, fu) * 0.5 - smooth(mortar * 2.0 * bh / bw, mortar * bh / bw, 1 - fu) * 0.5)
    tex = fbm(su * 3.0 / bh, sv * 3.0 / bh, seed + 5, 4)
    shade = (1 + (rnd - 0.5) * var * 2) * (0.8 + 0.4 * tex)
    rgb = base * shade[..., None]
    rgb = rgb * (1 + (rnd2[..., None] - 0.5) * np.array([0.08, 0.04, -0.06], F))
    mc = mortar_col if mortar_col is not None else base * 0.35
    rgb = mix(np.broadcast_to(mc, rgb.shape), rgb, m[..., None])
    return rgb, bev * bevel * m, m


def bamboo_cols(xx, yy, x0, pole_w, seed, base=col('#c9a45a'), node=60.0, light_side=-1.0):
    """Vertical bamboo poles (working px coordinates)."""
    k = np.floor((xx - x0) / pole_w)
    u = (xx - x0) / pole_w - k
    uu = u * 2 - 1
    rnd = hash2(k, k * 0 + 3, seed)
    shade = 0.45 + 0.55 * np.sqrt(clamp01(1 - uu * uu)) * (0.75 - 0.35 * uu * -light_side)
    shade = shade * (1 - 0.6 * smooth(0.85, 1.0, np.abs(uu)))
    off = rnd * node
    nv = ((yy + off) % node) / node
    nodes = smooth(0.03, 0.0, np.abs(nv - 0.5) - 0.0) * 0.0
    ring = 1 - smooth(0.0, 0.025, np.abs(nv - 0.5))
    tint = 0.85 + 0.3 * rnd
    rgb = base * (shade * tint)[..., None]
    rgb = rgb * (1 - 0.35 * ring)[..., None] + (ring * 0.1 * shade)[..., None]
    return rgb


def thatch(c, poly, seed, base=col('#b08a48'), tiers=6, y_top=None, y_bot=None, stroke=None):
    """Thatched roof painted inside a polygon (working px): straw strokes in ragged tiers."""
    a, box = mask_crop(c, polys=[poly], pad=4)
    x0, y0, x1, y1 = box
    h, w = a.shape
    rng = np.random.default_rng(seed)
    im = Image.new('RGB', (w, h), rgb255(base * 0.45))
    d = ImageDraw.Draw(im)
    stroke = stroke or U * 0.35
    yt = (y_top if y_top is not None else y0) - y0
    yb = (y_bot if y_bot is not None else y1) - y0
    for tier in range(tiers):
        ty0 = yt + (yb - yt) * tier / tiers
        ty1 = yt + (yb - yt) * (tier + 1) / tiers + U * 1.5
        n = int(w * (ty1 - ty0) / (stroke * stroke * 6))
        for k in range(n):
            x = rng.uniform(-10, w + 10)
            y_end = ty1 + rng.uniform(-U * 1.2, U * 0.8)
            ln = rng.uniform(0.5, 1.0) * (ty1 - ty0)
            sh = rng.uniform(0.55, 1.2) * (0.75 + 0.35 * (k % 3) / 2)
            cc = np.clip(base * sh, 0, 1)
            lean = (x - w / 2) / w * ln * 0.25
            d.line([(x - lean, y_end - ln), (x, y_end)], fill=rgb255(cc), width=max(1, int(stroke * rng.uniform(0.6, 1.2))))
        # shadow line under each tier
    arr = np.asarray(im, F) / 255.0
    yy = np.arange(h, dtype=F)[:, None]
    phase = ((yy - yt) / ((yb - yt) / tiers)) % 1.0
    arr = arr * (0.7 + 0.35 * smooth(0.0, 0.6, phase))[..., None]
    lam, _ = shape_lam(a, U * 6)
    arr = arr * (0.8 + 0.3 * lam)[..., None]
    over(c.img, a, arr, box)
    return a, box


def doorway_dark(c, x0, x1, y0, y1, seed, arch=True, inner=col('#120d0a'), floor=None):
    """A dark open doorway (virtual coords): gradient interior, optional round arch top."""
    X0, X1, Y0, Y1 = int(x0 * U), int(x1 * U), int(y0 * U), int(y1 * U)
    w, h = X1 - X0, Y1 - Y0
    xx = (np.arange(X0, X1, dtype=F)[None, :] - (X0 + X1) / 2) / (w / 2)
    yy = np.arange(Y0, Y1, dtype=F)[:, None]
    m = np.ones((h, w), F)
    if arch:
        r = w / 2
        cy = Y0 + r
        inside = (xx ** 2 + ((yy - cy) / r) ** 2) <= 1.0
        m = np.where(yy < cy, inside.astype(F), 1.0)
        m = gblur(m, 1.2)
    t = (yy - Y0) / h
    g = clamp01(1 - np.abs(xx) * 0.5)
    rgb = inner * (0.6 + 0.6 * g * t)[..., None]
    if floor is not None:
        fl = smooth(0.7, 0.9, t)
        rgb = mix(rgb, floor, (fl * 0.5)[..., None])
    tex = snoise(h, w, U, seed, 3)
    rgb = rgb * (0.85 + 0.3 * tex)[..., None]
    over(c.img[Y0:Y1, X0:X1], m, rgb)
    return m


# --------------------------------------------------------------------------------------------
# Scenes: tower, hut
# --------------------------------------------------------------------------------------------

def jungle_surround(c, cam, seed, Z=24.0, trees=True, ground='meadow'):
    day_sky(c, seed, sun=(40, -10), n=3, horizon=cam.hy / U)
    if ground == 'meadow':
        meadow(c, cam, seed, cam.hy, flowers=False, grass_col=col('#4f8a34'))
    if trees:
        tree_line(c, cam, seed + 3, Z * 1.5, n=8, haze_amt=0.15, height=(11, 15))
    jungle_wall_across(c, cam, seed + 1, Z=Z, height=7.0, palms=12, far=False)


def side_ferns(c, seed, y0_v=96):
    ferns_along(c, seed, (y0_v * U, c.H + U * 6),
                lambda y, r: (r.uniform(-0.08, 0.16) if r.random() < 0.5 else r.uniform(0.84, 1.08)) * c.W,
                lambda y: U * 8 + (y - y0_v * U) * 0.5, n=12)


def earth_patch(c, cx, cy, rx, ry, seed, color=col('#8a6a42'), strength=0.85):
    """Trodden bare earth on the ground (virtual)."""
    a, box = mask_crop(c, ellipses=[P(cx - rx, cy - ry, cx + rx, cy + ry)], blur=U * 3)
    if a is None:
        return
    tex = snoise(a.shape[0], a.shape[1], U * 2, seed, 4)
    rgb = color * (0.75 + 0.5 * tex)[..., None]
    al = a * clamp01(0.6 + (tex - 0.5) * 2) * strength
    over(c.img, al, rgb, box)


@scene('tower_out')
def bg_tower_out(c):
    seed = 111
    cam = Cam(c, HY)
    jungle_surround(c, cam, seed)
    earth_patch(c, 120, 128, 70, 12, seed)
    cx = 120 * U
    R = 52 * U
    x0, x1 = int(cx - R), int(cx + R)
    yb0 = 121 * U
    hy = cam.hy
    xx = np.arange(x0, x1, dtype=F)[None, :]
    u = np.clip((xx - cx) / R, -0.999, 0.999)
    th = np.arcsin(u)
    cosv = np.sqrt(1 - u * u)
    s_arc = th * R / U                  # arc length (virtual)
    # silhouette: top with crenellations and a broken section
    merl = ((s_arc + 203) % 16.0) < 8.0
    colidx = np.floor((s_arc + 200) / 6.0)
    ruin = clamp01((u - 0.1) / 0.5)
    drop = np.round(ruin * (2.0 + 3.5 * hash2(colidx, colidx * 0 + 1, seed))) * 6.0
    top_v = 14 - 2.5 * cosv + np.where(merl, 0, 5.0) * (ruin < 0.05) + drop
    top_px = top_v * U
    base_px = yb0 + 3.5 * U * cosv
    yy = np.arange(0, c.H, dtype=F)[:, None]
    m = (yy >= top_px) & (yy <= base_px)
    m = gblur(m.astype(F), 1.0)
    # surface coordinates, with course lines curving about the eye level
    sv = (yy - (yy - hy) * 0.07 * cosv) / U
    rgb, bev, _ = masonry(np.broadcast_to(s_arc, m.shape), np.broadcast_to(sv, m.shape), 12.0, 6.0, seed,
                       col('#a89c84'), mortar=0.07, var=0.3, offset=0.4)
    light = clamp01(np.cos(th + 0.8)) ** 0.8 * 0.95 + 0.12
    rgb = rgb * (light * (1 + bev * 0.6))[..., None]
    # weathering: dark streaks from the top, moss near the base
    streak = resize_arr(snoise(c.H // 16, x1 - x0, U * 3, seed + 4, 3), x1 - x0, c.H)
    rgb = rgb * (0.85 + 0.3 * streak)[..., None]
    mossn = fbm(xx / U * 0.15, yy / U * 0.15, seed + 6, 4)
    moss = clamp01((mossn - 0.45) * 3) * (0.3 + 0.7 * smooth(80 * U, 120 * U, yy))
    rgb = mix(rgb, col('#4a6a2a') * light[..., None] * 1.1, (moss * 0.65)[..., None])
    over(c.img[:, x0:x1], m, rgb)
    # ground contact shadow + doorway
    contact_shadow(c, 120, 123, 56, 4, 0.4)
    doorway_dark(c, 104, 136, 70, 120.5, seed, inner=col('#140e0a'), floor=col('#3a2a1a'))
    # voussoirs around the arch
    lay, d = c.layer()
    for k in range(13):
        a0 = math.pi + k / 13 * math.pi
        a1 = math.pi + (k + 1) / 13 * math.pi
        r0, r1 = 16 * U, 20.5 * U
        ccx, ccy = 120 * U, 86 * U
        pts = [(ccx + math.cos(a0) * r0, ccy + math.sin(a0) * r0), (ccx + math.cos(a0) * r1, ccy + math.sin(a0) * r1),
               (ccx + math.cos(a1) * r1, ccy + math.sin(a1) * r1), (ccx + math.cos(a1) * r0, ccy + math.sin(a1) * r0)]
        sh = 0.75 + 0.3 * ((k * 7) % 5) / 5 + 0.15 * math.cos((a0 + a1) / 2 + 0.5)
        d.polygon(pts, fill=rgb255(col('#b5aa92') * sh) + (255,))
        d.line(pts[:2], fill=rgb255(col('#3a3328')) + (255,), width=int(U * 0.4))
    for side in (-1, 1):
        for k in range(4):
            yj = 86 * U + k * 8.6 * U
            xj = 120 * U + side * 16 * U
            d.rectangle((min(xj, xj + side * 4.5 * U), yj, max(xj, xj + side * 4.5 * U), yj + 8.2 * U),
                        fill=rgb255(col('#ada28a') * (0.8 + 0.08 * k)) + (255,))
    c.comp(lay)
    # vines and bushes
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    for k in range(9):
        vx = (cx - R * 0.9) + rng.random() * R * 1.8
        if 100 * U < vx < 140 * U:
            continue
        uu = (vx - cx) / R
        ytop = float(np.interp(vx, xx[0], top_px[0])) + U * 2
        hanging_vine(d, vx, ytop, U * rng.uniform(25, 70), col('#3a4a1e'), U * 0.5, rng, leaf_col=col('#3f7f2a'))
    for k in range(40):
        vx = rng.uniform(cx - R * 1.05, cx + R * 1.05)
        if 100 * U < vx < 140 * U:
            continue
        ybase = yb0 + U * 3
        draw_broadleaf_bush(d, vx, ybase + U * rng.uniform(0, 3), U * rng.uniform(5, 11), col('#2f7a30') * rng.uniform(0.6, 1.1),
                            seed + k, n=6)
    # ivy creeping over the top of the ruin
    for k in range(45):
        vx = rng.uniform(cx - R * 0.2, cx + R)
        ytop = float(np.interp(vx, xx[0], top_px[0]))
        L = U * rng.uniform(2, 4)
        draw_leaf(d, vx, ytop + rng.uniform(-1, 8) * U, rng.uniform(0, 2 * math.pi), L, L * 0.6,
                  np.clip(col('#3f7f2a') * rng.uniform(0.7, 1.2), 0, 1), bend=0.2, rib=False)
    c.comp(lay)
    side_ferns(c, seed + 9)
    vignette(c, 0.3, 2.4)


@scene('hut_out')
def bg_hut_out(c):
    seed = 121
    cam = Cam(c, HY)
    jungle_surround(c, cam, seed)
    earth_patch(c, 120, 124, 85, 16, seed, strength=0.9)
    # walls: bamboo poles between x 66..174, from y 58 down to the ground at 114
    wx0, wx1 = 66 * U, 174 * U
    wy0, wy1 = 58 * U, 114 * U
    xx = np.arange(int(wx0), int(wx1), dtype=F)[None, :]
    yy = np.arange(int(wy0), int(wy1), dtype=F)[:, None]
    rgb = bamboo_cols(xx, yy, wx0, U * 4.2, seed, base=col('#c9a45a'), node=U * 14)
    rgb = rgb * (1 - 0.5 * smooth(wy0 + U * 14, wy0, yy))[..., None]   # shadow under the eaves
    c.img[int(wy0):int(wy1), int(wx0):int(wx1)] = rgb
    # lashings: horizontal rails
    lay, d = c.layer()
    for ry in (70, 100):
        d.rectangle((wx0 - U, ry * U, wx1 + U, ry * U + U * 2.2), fill=rgb255(col('#8a6a3a')) + (255,))
        d.rectangle((wx0 - U, ry * U, wx1 + U, ry * U + U * 0.6), fill=rgb255(col('#b08a52')) + (255,))
        for k in range(18):
            lx = wx0 + (wx1 - wx0) * (k + 0.5) / 18
            d.line([(lx - U * 0.8, ry * U - U * 0.3), (lx + U * 0.8, ry * U + U * 2.5)], fill=rgb255(col('#5a4020')) + (255,),
                   width=int(U * 0.4))
    # corner posts
    for px in (wx0 - U * 2, wx1 - U * 1):
        d.rectangle((px, wy0 - U * 2, px + U * 3, wy1 + U), fill=rgb255(col('#6a4a2a')) + (255,))
        d.rectangle((px, wy0 - U * 2, px + U * 1, wy1 + U), fill=rgb255(col('#8a6a3a')) + (255,))
    c.comp(lay)
    doorway_dark(c, 104, 136, 72, 114, seed, arch=False, inner=col('#1a120c'), floor=col('#4a3420'))
    # door frame
    lay, d = c.layer()
    d.rectangle((103 * U, 70 * U, 105.5 * U, 114 * U), fill=rgb255(col('#7a5530')) + (255,))
    d.rectangle((134.5 * U, 70 * U, 137 * U, 114 * U), fill=rgb255(col('#6a4828')) + (255,))
    d.rectangle((101 * U, 69 * U, 139 * U, 72 * U), fill=rgb255(col('#8a6238')) + (255,))
    c.comp(lay)
    # thatched roof
    roof = [(120 * U, 6 * U), (200 * U, 60 * U), (196 * U, 64 * U), (44 * U, 64 * U), (40 * U, 60 * U)]
    thatch(c, roof, seed, base=col('#c09a58'), tiers=7, y_top=6 * U, y_bot=64 * U)
    # ridge cap
    lay, d = c.layer()
    d.polygon([(120 * U, 3 * U), (126 * U, 10 * U), (114 * U, 10 * U)], fill=rgb255(col('#7a5a30')) + (255,))
    c.comp(lay)
    contact_shadow(c, 120, 115, 60, 3, 0.4)
    # plants at the foot of the walls
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    for k in range(16):
        x = rng.uniform(60, 180) * U
        if 98 * U < x < 142 * U:
            continue
        draw_broadleaf_bush(d, x, 116 * U, U * rng.uniform(5, 9), col('#2f7a30') * rng.uniform(0.6, 1.0), seed + k, n=5)
    c.comp(lay)
    side_ferns(c, seed + 9)
    vignette(c, 0.3, 2.4)


# --------------------------------------------------------------------------------------------
# Scenes: marsh
# --------------------------------------------------------------------------------------------

def dead_tree(d, x, y, h, seed, color=col('#6a6458'), width=None, depth=5, alpha=255, mirror_y=None):
    """Bare dead tree from (x, y) up (working px). mirror_y draws its reflection instead."""
    rng = np.random.default_rng(seed)
    width = width or h * 0.06

    def yy(v):
        return v if mirror_y is None else 2 * mirror_y - v

    def branch(x0, y0, ang, L, w, lvl):
        x1 = x0 + math.cos(ang) * L
        y1 = y0 + math.sin(ang) * L
        mx = (x0 + x1) / 2 + rng.uniform(-0.12, 0.12) * L
        my = (y0 + y1) / 2 + rng.uniform(-0.05, 0.05) * L
        shade = 0.8 + 0.3 * rng.random()
        d.line([(x0, yy(y0)), (mx, yy(my)), (x1, yy(y1))], fill=rgb255(np.clip(color * shade, 0, 1)) + (alpha,),
               width=max(1, int(w)), joint='curve')
        if lvl <= 0 or L < 6:
            return
        nb = 2 if rng.random() < 0.7 else 3
        for k in range(nb):
            a2 = ang + rng.uniform(-0.75, 0.75)
            if rng.random() < 0.15 and lvl < depth - 1:
                continue
            branch(x1, y1, a2, L * rng.uniform(0.55, 0.8), w * 0.62, lvl - 1)

    # trunk
    d.polygon([(x - width, yy(y)), (x + width, yy(y)), (x + width * 0.4 + h * 0.05, yy(y - h * 0.55)),
               (x - width * 0.4 + h * 0.05, yy(y - h * 0.55))], fill=rgb255(color * 0.85) + (alpha,))
    branch(x + h * 0.05, y - h * 0.5, -math.pi / 2 + rng.uniform(-0.3, 0.3), h * 0.32, width * 0.8, depth)
    branch(x + h * 0.02, y - h * 0.3, -math.pi / 2 - rng.uniform(0.5, 1.0), h * 0.3, width * 0.5, depth - 1)
    branch(x + h * 0.03, y - h * 0.38, -math.pi / 2 + rng.uniform(0.5, 1.0), h * 0.28, width * 0.5, depth - 1)


def reed_clump(d, x, y, h, seed, color=col('#6a8a3a'), n=18, cattails=True, mirror_y=None, alpha=255):
    rng = np.random.default_rng(seed)
    for k in range(n):
        bx = x + rng.uniform(-0.25, 0.25) * h
        bh = h * rng.uniform(0.5, 1.1)
        lean = rng.uniform(-0.3, 0.3) * bh
        cc = np.clip(color * rng.uniform(0.6, 1.2), 0, 1)
        if mirror_y is None:
            draw_blade(d, bx, y, bh, lean, max(2, h * 0.03), cc, alpha=alpha)
        else:
            pts_l, pts_r = [], []
            for i in range(7):
                t = i / 6
                px = bx + lean * t * t
                py = 2 * mirror_y - (y - bh * t)
                ww = max(2, h * 0.03) * (1 - t) * 0.5 + 0.3
                pts_l.append((px - ww, py))
                pts_r.append((px + ww, py))
            d.polygon(pts_l + pts_r[::-1], fill=rgb255(cc) + (alpha,))
        if cattails and mirror_y is None and rng.random() < 0.25:
            tx, ty = bx + lean * 0.8, y - bh * 0.85
            d.ellipse((tx - h * 0.02, ty - h * 0.07, tx + h * 0.02, ty + h * 0.07), fill=rgb255(col('#5a3a1e')) + (alpha,))


def marsh_scene(c, seed, boards=True, deep=False):
    cam = Cam(c, HY)
    sky(c, HY + 1, stops=[(0.0, col('#7fa3b8')), (0.6, col('#b9cfc8')), (1.0, col('#dfe6cf'))], sun=(60, 5),
        sun_col=col('#fff2c8'), sun_r=50, sun_str=0.25)
    cloud_bank(c, HY - 6, seed, n=4, size=(30, 60), lit=col('#eef2e8'), shade=col('#9aaea8'), alpha=0.8)
    # far bank of jungle, very hazy
    _, ybf = cam.proj(0, 0, 90)
    lay, d = c.layer()
    foliage_mass(c, d, lambda x: ybf - U * (7 + 3 * math.sin(x / c.W * 8 + seed) + 2 * math.sin(x / c.W * 21)),
                 -20, c.W + 20, ybf + U * 2, seed + 1, JUNGLE, leaf=U * 1.6, density=0.8, base=col('#2a4a30'))
    rng = np.random.default_rng(seed)
    for k in range(6):
        draw_palm(d, rng.uniform(0, c.W), ybf, U * rng.uniform(12, 18), rng.uniform(-1, 1) * U * 2, seed + 40 + k)
    c.comp(lay, tint=col('#b9c8bc'), tint_amt=0.55)
    hy = int(cam.hy)
    # water: reflections of what is above the horizon, rippled
    X, Z, y0 = cam.ground()
    rows = c.H - y0
    ys = np.arange(y0, c.H)
    src = np.clip(2 * cam.hy - ys, 0, hy).astype(int)
    rip = (fbm(X * 0.6, Z * 2.5, seed + 3, 4) - 0.5)
    sx = np.clip((c.xs + rip * 30 * np.exp(-Z / 20)).astype(int), 0, c.W - 1)
    refl = gblur(c.img[:hy + 1], 3)[src[:, None], sx]
    murk = mix(col('#2a3a1c'), col('#3e4a26'), fbm(X * 0.3, Z * 0.3, seed + 4, 3)[..., None])
    if deep:
        murk = col('#06090a') + murk * 0.15
    fres = (0.25 + 0.6 * smooth(2, 50, Z))[..., None]
    if deep:
        fres = fres * 0.7
    water = mix(murk, refl * (0.85 + rip[..., None] * 0.6), fres)
    # duckweed / scum
    if not deep:
        weed = fbm(X * 0.35, Z * 0.35, seed + 5, 4)
        wm = clamp01((weed - 0.56) * 6) * (1 - smooth(25, 60, Z))
        wc = mix(col('#5a7a2a'), col('#8aa03a'), fbm(X * 3, Z * 3, seed + 6, 2)[..., None])
        water = mix(water, wc, (wm * 0.85)[..., None])
    c.img[y0:] = water
    # mid-distance dead trees and their reflections
    lay, d = c.layer(shadows=False)
    rl, rd = c.layer(shadows=False)
    for k in range(5):
        Zt = rng.uniform(18, 45)
        Xt = rng.choice([-1, 1]) * rng.uniform(4, 16)
        x, yb = cam.proj(Xt, 0, Zt)
        hgt = cam.f / Zt * rng.uniform(5, 9)
        sd = seed + 60 + k
        dead_tree(d, x, yb, hgt, sd, color=col('#6e675c'))
        dead_tree(rd, x, yb, hgt, sd, color=col('#4a463e'), mirror_y=yb)
        reed_clump(d, x, yb, hgt * 0.25, sd, n=10)
    c.comp(rl, blur=4, opacity=0.4)
    c.comp(lay, tint=col('#b9c8bc'), tint_amt=0.3)
    mist(c, HY - 6, HY + 14, seed + 7, col('#e6eee0'), amount=0.55)
    if boards:
        # tussocks and duckboards leading ahead
        lay, d = c.layer()
        planks = []
        Zp = 2.0
        while Zp < 46:
            planks.append(Zp)
            Zp += 0.42 + rng.uniform(0, 0.08)
        for Zp in reversed(planks):
            if rng.random() < 0.06:
                continue
            xc = 0.4 * math.sin(Zp * 0.12) + 0.2 * math.sin(Zp * 0.4)
            w2 = 0.6
            dz = 0.3
            a_ = cam.proj(xc - w2, 0.08, Zp + dz)
            b_ = cam.proj(xc + w2, 0.08, Zp + dz)
            c_ = cam.proj(xc + w2, 0.08, Zp)
            d_ = cam.proj(xc - w2, 0.08, Zp)
            e_ = cam.proj(xc + w2, 0.0, Zp)
            f_ = cam.proj(xc - w2, 0.0, Zp)
            sh = rng.uniform(0.75, 1.1) * (1 - smooth(10, 45, Zp) * 0.4)
            tilt = rng.uniform(-0.03, 0.03) * (c_[0] - d_[0])
            d.polygon([d_, c_, e_, f_], fill=rgb255(col('#3a2c1c') * sh) + (255,))
            d.polygon([a_, b_, (c_[0], c_[1] + tilt), (d_[0], d_[1] - tilt)], fill=rgb255(col('#8a7050') * sh) + (255,))
        for k in range(18):
            Zt = rng.uniform(3, 30)
            side = rng.choice([-1, 1])
            Xt = side * rng.uniform(1.3, 4.0) + 0.4 * math.sin(Zt * 0.12)
            x, yb = cam.proj(Xt, 0, Zt)
            sc = cam.f / Zt
            d.chord((x - sc * 0.7, yb - sc * 0.45, x + sc * 0.7, yb + sc * 0.45), 180, 360, fill=rgb255(col('#4a5a26')) + (255,))
            d.chord((x - sc * 0.55, yb - sc * 0.38, x + sc * 0.35, yb + sc * 0.2), 180, 360, fill=rgb255(col('#5f7030')) + (255,))
            d.ellipse((x - sc * 0.75, yb - sc * 0.06, x + sc * 0.75, yb + sc * 0.1), fill=rgb255(col('#2a3418')) + (255,))
            reed_clump(d, x, yb, sc * rng.uniform(0.6, 1.1), seed + 100 + k, color=col('#7a9a3a'), n=14, cattails=False)
        c.comp(lay)
    # reeds framing the foreground
    lay, d = c.layer()
    rl, rd = c.layer(shadows=False)
    for k in range(14):
        side = k % 2
        x = (rng.uniform(-0.05, 0.22) if side == 0 else rng.uniform(0.78, 1.05)) * c.W
        y = rng.uniform(0.75, 1.0) * c.H
        h = U * rng.uniform(25, 50)
        reed_clump(d, x, y, h, seed + 200 + k, n=24)
        reed_clump(rd, x, y, h * 0.5, seed + 200 + k, n=24, mirror_y=y, cattails=False)
    c.comp(rl, blur=3, opacity=0.35)
    c.comp(lay)
    mist(c, HY + 10, 120, seed + 8, col('#e8f0e0'), amount=0.12 if deep else 0.2, scale=90)
    # rising steam
    for k in range(4):
        x0_ = rng.uniform(0.15, 0.85) * c.W
        a, box = mask_crop(c, ellipses=[(x0_ - U * 7, U * 35, x0_ + U * 7, U * 80)], blur=U * 5)
        tex = snoise(a.shape[0] // 3, a.shape[1], U * 3, seed + 300 + k, 4)
        tex = resize_arr(tex, a.shape[1], a.shape[0])
        over(c.img, a * clamp01((tex - 0.4) * 2.0) * 0.2, col('#f2f6ee'), box)
    vignette(c, 0.3, 2.4)
    grade(c, sat=0.95)


@scene('marsh')
def bg_marsh(c):
    marsh_scene(c, 131, boards=True)


@scene('marsh_wall')
def bg_marsh_wall(c):
    marsh_scene(c, 141, boards=False, deep=True)


# --------------------------------------------------------------------------------------------
# Volcanic helpers and scenes
# --------------------------------------------------------------------------------------------

HOT_SKY = [(0.0, col('#3f78b8')), (0.5, col('#86b4d8')), (0.85, col('#d6d8c4')), (1.0, col('#efe2c0'))]


def smoke_plume(c, x, y, seed, height, width, drift=0.6, dark=col('#5a5450'), lit=col('#d8d0c8'), alpha=0.9,
                glow_col=None):
    """Billowing plume rising from (x, y) (virtual), drifting right."""
    rng = np.random.default_rng(seed)
    n = 14
    for k in range(n):
        t = k / (n - 1)
        px = x + drift * height * t ** 1.4 + rng.uniform(-1, 1) * width * 0.15
        py = y - height * t
        r = width * (0.35 + 1.1 * t) * rng.uniform(0.8, 1.2)
        circ = [(px + rng.uniform(-0.5, 0.5) * r, py + rng.uniform(-0.3, 0.3) * r, r * rng.uniform(0.5, 0.8))
                for _ in range(4)]
        puff(c, circ, seed * 7 + k, mix(lit, dark, 0.15 + 0.3 * (1 - t)), dark, alpha * (1 - 0.5 * t ** 2),
             soft=2.0)
    if glow_col is not None:
        glow(c, x * U, y * U, width * U * 1.2, glow_col, 0.6)


def cone_poly(cx, base_y, peak_y, half_w, crater_w, seed, n=60):
    rng = np.random.default_rng(seed)
    left, right = [], []
    for i in range(n + 1):
        t = i / n                     # 0 base, 1 top
        y = base_y - (base_y - peak_y) * t
        w = crater_w + (half_w - crater_w) * (1 - t) ** 1.9
        left.append((cx - w + rng.uniform(-0.3, 0.3), y))
        right.append((cx + w + rng.uniform(-0.3, 0.3), y))
    rim = []
    for i in range(1, 12):
        t = i / 12
        rim.append((cx - crater_w + 2 * crater_w * t, peak_y + 1.2 * math.sin(math.pi * t) + rng.uniform(-0.6, 0.6)))
    return [(x * U, y * U) for x, y in left + rim + right[::-1]]


def volcano_cone(c, cx, base_y, peak_y, half_w, crater_w, seed, haze=col('#a8b8c8'), haze_amt=0.3, green=True,
                 glow_top=False, fade_base=False):
    pts = cone_poly(cx, base_y, peak_y, half_w, crater_w, seed)
    a, box = mask_crop(c, polys=[pts], pad=8, blur=1)
    h, w = a.shape
    x0, y0, x1, y1 = box
    xx = (np.arange(x0, x1, dtype=F)[None, :] - cx * U) / (half_w * U)
    yy = (np.arange(y0, y1, dtype=F)[:, None] - peak_y * U) / ((base_y - peak_y) * U)
    # gullies radiating down the cone
    ang = xx / (0.15 + yy)
    gul = fbm(ang * 6, yy * 2.5, seed, 5, ridged=True)
    side = clamp01(0.55 - xx * 0.9)
    shade = 0.3 + 0.75 * side * (0.6 + 0.8 * gul)
    base = mix(col('#4a403a'), col('#7a6a5c'), clamp01(gul)[..., None])
    rgb = base * shade[..., None]
    if green:
        gm = smooth(0.5, 0.75, yy + (fbm(ang * 3, yy * 3, seed + 1, 4) - 0.5) * 0.7)
        canopy = fbm(xx * 60, yy * 40, seed + 4, 3)
        greens = mix(col('#163a1c'), col('#4a8a34'), clamp01(side * (0.4 + 0.5 * gul) + (canopy - 0.5) * 0.8)[..., None])
        rgb = mix(rgb, greens, gm[..., None])
    rgb = mix(rgb, haze, haze_amt)
    if glow_top:
        gt = np.exp(-((yy) / 0.08) ** 2) * clamp01(1 - np.abs(xx) * 3)
        rgb = rgb + col('#ff6a20') * (gt * 0.8)[..., None]
    if fade_base:
        a = a * (1 - smooth(0.55, 1.0, yy + (fbm(xx * 5, yy * 5, seed + 9, 3) - 0.5) * 0.3))
    over(c.img, a, rgb, box)


def scree_rgb(X, Z, seed, dark=col('#2c2826'), light=col('#6e6258'), path=None, path_col=col('#8f7e68')):
    n = fbm(X * 0.5, Z * 0.5, seed, 4)
    st = fbm(X * 4.0, Z * 4.0, seed + 1, 3)
    stones = clamp01((st - 0.55) * 6)
    t = clamp01(n * 1.1 - 0.1)
    rgb = mix(dark, light, t[..., None])
    rgb = rgb * (1 + (stones * 0.35 - clamp01((0.42 - st) * 6) * 0.25) * np.exp(-Z / 15))[..., None]
    if path is not None:
        rgb = mix(rgb, path_col * (0.8 + 0.4 * st)[..., None], path[..., None])
    return rgb


def heat_haze(c, y0_v, y1_v, seed, amp=2.5):
    y0, y1 = int(y0_v * U), int(y1_v * U)
    rows = np.arange(y0, y1)
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 3)
    shift = (np.sin(rows * 0.11 + ph[0]) + 0.5 * np.sin(rows * 0.37 + ph[1])) * amp * U / 6
    shift *= np.sin(np.linspace(0, math.pi, len(rows)))
    out = c.img[y0:y1].copy()
    xs = np.arange(c.W)
    for i, r in enumerate(rows):
        sx = np.clip((xs + shift[i]).astype(int), 0, c.W - 1)
        out[i] = c.img[r, sx]
    c.img[y0:y1] = out


def volcanic_ground(c, cam, seed, path=True, path_w=0.9, dark=col('#2c2826'), light=col('#6e6258')):
    X, Z, y0 = cam.ground()
    pm = None
    if path:
        pc = 0.6 * np.sin(Z * 0.08 + seed) + 0.3 * np.sin(Z * 0.23)
        en = fbm(X * 0.9, Z * 0.9, seed + 2, 3)
        pm = (1 - smooth(path_w * 0.5, path_w * 1.2, np.abs(X - pc) + (en - 0.5) * 0.7)) * 0.75
    rgb = scree_rgb(X, Z, seed, dark, light, pm)
    rgb = mix(rgb, col('#b8b4a8'), smooth(30, 400, Z)[..., None] * 0.55)
    c.img[y0:] = rgb
    return X, Z, y0


def scatter_boulders(c, cam, seed, n, z_range, x_range, size=(0.5, 1.6), base=col('#2e2a28'), avoid=None,
                     haze=col('#b8b4a8')):
    rng = np.random.default_rng(seed)
    items = []
    for k in range(n):
        Z = rng.uniform(*z_range)
        X = rng.uniform(*x_range)
        if avoid and abs(X) < avoid:
            X = math.copysign(avoid + abs(X), X if X else 1)
        items.append((Z, X, rng.uniform(*size), k))
    items.sort(reverse=True)
    for Z, X, r, k in items:
        x, y = cam.proj(X, 0, Z)
        sc = cam.f / Z
        R_ = r * sc
        contact_shadow(c, x / U + R_ * 0.2 / U, y / U, R_ * 1.1 / U, R_ * 0.2 / U, 0.45)
        pts = rock_poly(x, y - R_ * 0.45, R_, R_ * 0.75, seed * 100 + k)
        hz = float(smooth(10, 150, Z)) * 0.5
        paint_rock(c, pts, mix(base, haze, hz), seed * 100 + k, spec=0.2, amb=0.3)


@scene('rocks_path')
def bg_rocks_path(c, wall=False):
    seed = 151 if not wall else 161
    cam = Cam(c, HY)
    sky(c, HY + 1, stops=HOT_SKY, sun=(50, -5), sun_r=70, sun_str=0.3)
    wisps(c, 5, 30, seed, amount=0.15)
    volcano_cone(c, 175, HY + 1, 18, 75, 9, seed, haze=col('#b4bcc4'), haze_amt=0.42)
    smoke_plume(c, 175, 17, seed, 16, 6, drift=1.2, alpha=0.75)
    # distant ridge
    lay, d = c.layer()
    pts = [(0, HY * U + 4)]
    rng = np.random.default_rng(seed)
    for i in range(41):
        x = i / 40 * c.W
        pts.append((x, (HY - 4 - 3 * math.sin(i * 0.5 + seed) - rng.uniform(0, 1.5)) * U))
    pts.append((c.W, HY * U + 4))
    d.polygon(pts, fill=rgb255(col('#7a7470')) + (255,))
    c.comp(lay, tint=col('#c0c0c0'), tint_amt=0.35)
    volcanic_ground(c, cam, seed, path=not wall)
    scatter_boulders(c, cam, seed, 40, (6, 120), (-40, 40), avoid=2.5 if not wall else None)
    if wall:
        # a jumble of big black boulders right ahead
        rng = np.random.default_rng(seed + 1)
        items = []
        for k in range(26):
            Z = rng.uniform(7, 11)
            X = rng.uniform(-9, 9)
            r = rng.uniform(1.4, 3.0)
            hgt = rng.uniform(0, 1) * 2.5
            items.append((Z, X, r, hgt, k))
        items.sort(reverse=True)
        for Z, X, r, hgt, k in items:
            x, y = cam.proj(X, hgt, Z)
            sc = cam.f / Z
            pts = rock_poly(x, y - r * sc * 0.4, r * sc, r * sc * 0.8, seed * 10 + k, rough=0.28)
            paint_rock(c, pts, col('#262222'), seed * 10 + k, spec=0.3, amb=0.25)
    else:
        scatter_boulders(c, cam, seed + 5, 10, (3, 9), (-8, 8), size=(0.4, 1.0), avoid=1.8)
    heat_haze(c, HY - 10, HY + 12, seed)
    vignette(c, 0.3, 2.4)
    grade(c, sat=1.05, contrast=1.05)


@scene('rocks_wall')
def bg_rocks_wall(c):
    bg_rocks_path(c, wall=True)


def lava_ground(c, cam, seed, y_from=None, glow_amt=1.0):
    X, Z, y0 = cam.ground(y_from)
    flow = fbm(X * 0.4 + fbm(X * 0.1, Z * 0.1, seed + 3, 3) * 3, Z * 1.2, seed, 5)
    rope = np.sin((Z * 9 + X * 2.5 + flow * 30)) * 0.5 + 0.5
    lump = fbm(X * 1.5, Z * 1.5, seed + 11, 4)
    rgb = mix(col('#121010'), col('#4a4240'), clamp01(flow * 0.9 - 0.15 + (lump - 0.5) * 0.9 + rope * 0.2 * np.exp(-Z / 8))[..., None])
    # glossy sheen catching the sky
    sheen = clamp01((rope - 0.85) * 5) * np.exp(-Z / 10) * 0.12
    rgb = rgb + sheen[..., None] * col('#8090a0')
    n1 = fbm(X * 0.22, Z * 0.22, seed + 7, 3)
    n2 = fbm(X * 0.5, Z * 0.5, seed + 8, 3)
    w1 = np.abs(n1 - 0.5)
    w2 = np.abs(n2 - 0.5)
    cr = np.maximum(1 - w1 / 0.03, 1 - w2 / 0.016 + (n1 - 0.5) * 2 - 0.3)
    cr = clamp01(cr)
    crack = smooth(0.0, 0.6, cr) * (1 - smooth(60, 200, Z))
    cr = 0.9 + 0.1 * cr
    hot = mix(col('#ff3a08'), col('#ffd060'), smooth(0.93, 0.99, cr)[..., None])
    rgb = mix(rgb, hot, (crack * glow_amt)[..., None])
    c.img[y0:] = rgb
    # glow halo around cracks
    full = np.zeros((c.H, c.W), F)
    full[y0:] = crack
    g = gblur(full, U * 1.5)
    c.img += (g * 0.7 * glow_amt)[..., None] * col('#ff5a10')
    return X, Z, y0


@scene('lava_field')
def bg_lava_field(c):
    seed = 171
    cam = Cam(c, HY)
    sky(c, HY + 1, stops=[(0.0, col('#3a3c4a')), (0.5, col('#7a6a66')), (0.85, col('#c08a60')), (1.0, col('#e0a070'))],
        sun=(170, 40), sun_col=col('#ffb070'), sun_r=60, sun_str=0.3)
    smoke_plume(c, 30, HY - 2, seed, 60, 10, drift=2.0, dark=col('#3a3434'), lit=col('#8a7a74'), alpha=0.8)
    volcano_cone(c, 205, HY + 1, 24, 60, 8, seed, haze=col('#8a7a74'), haze_amt=0.4, green=False, glow_top=True)
    smoke_plume(c, 205, 23, seed + 1, 22, 7, drift=0.8, dark=col('#3a3434'), lit=col('#9a8a84'), alpha=0.85,
                glow_col=col('#ff6a20'))
    lava_ground(c, cam, seed)
    # steaming vents
    rng = np.random.default_rng(seed)
    for k in range(6):
        Z = rng.uniform(5, 40)
        X = rng.uniform(-14, 14)
        x, y = cam.proj(X, 0, Z)
        sc = cam.f / Z
        a, box = mask_crop(c, ellipses=[(x - sc * 0.8, y - sc * 5, x + sc * 0.8, y)], blur=sc * 0.6)
        if a is None:
            continue
        tex = snoise(a.shape[0], a.shape[1], max(3, sc * 0.4), seed + k, 4)
        over(c.img, a * clamp01((tex - 0.4) * 2) * 0.45, col('#e8e0dc'), box)
    vignette(c, 0.35, 2.3)
    grade(c, contrast=1.05)


@scene('volcano')
def bg_volcano(c):
    seed = 181
    cam = Cam(c, HY + 4)
    sky(c, HY + 5, stops=HOT_SKY, sun=(40, -5), sun_r=70, sun_str=0.25)
    smoke_plume(c, 122, 22, seed, 26, 9, drift=1.4, alpha=0.9)
    volcano_cone(c, 120, HY + 6, 22, 130, 12, seed, haze=col('#b4bcc4'), haze_amt=0.15, glow_top=True)
    X, Z, y0 = volcanic_ground(c, cam, seed, path=True, path_w=0.8)
    # path climbing the cone in zigzags
    lay, d = c.layer(shadows=False)
    zig = [(120, HY + 5), (112, HY + 1), (128, HY - 6), (115, HY - 13), (126, HY - 20), (119, HY - 27), (122, 30)]
    d.line([(x * U, y * U) for x, y in zig], fill=(160, 140, 115, 200), width=int(U * 0.8), joint='curve')
    c.comp(lay, blur=2)
    scatter_boulders(c, cam, seed, 30, (6, 60), (-30, 30), avoid=2.2)
    heat_haze(c, HY - 6, HY + 14, seed, amp=1.5)
    vignette(c, 0.3, 2.4)
    grade(c, sat=1.05, contrast=1.05)


@scene('spring')
def bg_spring(c):
    seed = 191
    cam = Cam(c, HY)
    sky(c, HY + 1, stops=HOT_SKY, sun=(50, -5))
    cloud_bank(c, HY - 4, seed, n=3)
    volcano_cone(c, 70, HY + 1, 26, 70, 9, seed, haze=col('#b4bcc4'), haze_amt=0.4)
    smoke_plume(c, 70, 25, seed, 14, 5, drift=1.5, alpha=0.7)
    volcanic_ground(c, cam, seed, path=False)
    scatter_boulders(c, cam, seed, 25, (12, 120), (-40, 40), avoid=4)
    # rocks enclosing the pool
    rng = np.random.default_rng(seed)
    cxp, cyp = 120 * U, 118 * U
    rxp, ryp = 46 * U, 11 * U
    # the source rock behind the pool
    src = rock_poly(146 * U, 104 * U, 26 * U, 20 * U, seed + 3, rough=0.25)
    paint_rock(c, src, col('#3a3432'), seed + 3, spec=0.25)
    # pool
    xx = (c.xs - cxp) / rxp
    yy = (c.ys - cyp) / ryp
    rr = xx * xx + yy * yy + (snoise(c.H, c.W, U * 6, seed + 5, 3) - 0.5) * 0.3
    pm = 1 - smooth(0.9, 1.0, rr)
    depth = clamp01(1 - rr)
    water = mix(col('#3fb0b0'), col('#0f4a5a'), (depth ** 0.7)[..., None])
    # sky reflection at the far edge, ripples, caustic sparkle
    rip = snoise(c.H, c.W, U * 1.2, seed + 6, 3)
    water = water + (clamp01(-yy * 0.8) * 0.25)[..., None] * col('#bfe4f0')
    ring = np.sin(np.sqrt(((c.xs - 140 * U) / 1.6) ** 2 + ((c.ys - 112 * U) * 1.6) ** 2) / U * 2.2) * 0.5 + 0.5
    water = water * (0.9 + 0.2 * rip[..., None]) + (ring * 0.06 * depth)[..., None]
    over(c.img, pm, water)
    # stones and moss rim
    lay, d = c.layer()
    for k in range(34):
        a = k / 34 * 2 * math.pi + rng.uniform(-0.05, 0.05)
        x = cxp + math.cos(a) * rxp * rng.uniform(0.98, 1.08)
        y = cyp + math.sin(a) * ryp * rng.uniform(0.95, 1.12)
        r = U * rng.uniform(3, 6) * (0.8 + 0.4 * (math.sin(a) + 1) / 2)
        pts = rock_poly(x, y, r, r * 0.6, seed + 20 + k)
        d.polygon(pts, fill=(0, 0, 0, 255))
    rim, _ = lay, d
    c.comp(lay, opacity=0)
    for k in range(34):
        a = k / 34 * 2 * math.pi + rng.uniform(-0.05, 0.05)
        x = cxp + math.cos(a) * rxp * rng.uniform(0.98, 1.08)
        y = cyp + math.sin(a) * ryp * rng.uniform(0.95, 1.12)
        if math.sin(a) < -0.2 and 125 * U < x < 170 * U:
            continue
        r = U * rng.uniform(3, 6) * (0.8 + 0.4 * (math.sin(a) + 1) / 2)
        pts = rock_poly(x, y, r, r * 0.6, seed + 20 + k)
        paint_rock(c, pts, mix(col('#3a3432'), col('#3a5a2a'), rng.uniform(0, 0.5)), seed + 20 + k, spec=0.25)
    # ferns and moss: life around the water
    ferns_along(c, seed + 7, (100 * U, 116 * U), lambda y, r: (r.uniform(0.18, 0.3) if r.random() < 0.5 else r.uniform(0.7, 0.85)) * c.W,
                lambda y: U * 10, n=8, color=col('#4a9a3a'))
    # trickle from the rock into the pool
    lay, d = c.layer(shadows=False)
    sx, sy = 140 * U, 92 * U
    pts_l, pts_r = [], []
    for k in range(21):
        t = k / 20
        x = sx - t * U * 3 + math.sin(t * 9) * U * 0.3
        y = sy + t * (113 * U - sy)
        w = U * (0.6 + 0.5 * t)
        pts_l.append((x - w, y))
        pts_r.append((x + w, y))
    d.polygon(pts_l + pts_r[::-1], fill=(190, 230, 240, 200))
    d.line([(p[0] - U * 0.2, p[1]) for p in pts_l], fill=(240, 252, 255, 230), width=int(U * 0.35))
    d.ellipse((sx - U * 7, 111 * U, sx + U * 3, 115 * U), fill=(230, 245, 250, 150))
    c.comp(lay, blur=1)
    glow(c, sx - U * 2, 113 * U, U * 4, col('#ffffff'), 0.2)
    heat_haze(c, HY - 6, HY + 8, seed, amp=1.2)
    vignette(c, 0.3, 2.4)
    grade(c, sat=1.05)


@scene('slope_up')
def bg_slope_up(c):
    seed = 201
    sky(c, 60, stops=[(0.0, col('#4a7ab0')), (0.7, col('#9ab8d0')), (1.0, col('#d8d4c4'))])
    # smoke billowing beyond the rim
    smoke_plume(c, 132, 46, seed, 50, 18, drift=0.9, dark=col('#4a4444'), lit=col('#c8c0b8'), alpha=0.95)
    # the steep ash slope rising to the rim
    rng = np.random.default_rng(seed)
    rim = []
    for i in range(61):
        x = i / 60 * 240
        rim.append((x, 36 + 6 * math.sin(i * 0.21 + 1) + 3 * math.sin(i * 0.67) + rng.uniform(-0.8, 0.8) - 6 * math.exp(-((x - 120) / 40) ** 2)))
    pts = [(x * U, y * U) for x, y in rim] + [(c.W, c.H), (0, c.H)]
    a, box = mask_crop(c, polys=[pts], pad=2, blur=1)
    x0, y0, x1, y1 = box
    h, w = a.shape
    xx = np.arange(x0, x1, dtype=F)[None, :] / U - 120
    yy = np.arange(y0, y1, dtype=F)[:, None] / U
    # streaks converge towards the rim (perspective of the slope)
    t = clamp01((yy - 30) / 106)
    u = xx / (0.25 + t)
    streak = fbm(u * 0.25, yy * 0.05, seed, 5)
    gr = fbm(u * 2.5, yy * 0.8, seed + 1, 3)
    rgb = mix(col('#3a3230'), col('#7a6a5e'), clamp01(streak * 1.2 - 0.1 + (gr - 0.5) * 0.3 * t)[..., None])
    light = 0.75 + 0.35 * clamp01(-xx / 120 + 0.5)
    rgb = rgb * light[..., None] * (0.7 + 0.4 * t)[..., None]
    # reddish oxidised patches
    ox = fbm(xx * 0.05, yy * 0.08, seed + 2, 3)
    rgb = mix(rgb, col('#7a4a32'), (clamp01((ox - 0.6) * 4) * 0.5)[..., None])
    over(c.img, a, rgb, box)
    # rocks and lava bombs on the slope, bigger near
    for k in range(30):
        yv = rng.uniform(42, 136)
        tt = (yv - 36) / 100
        xv = rng.uniform(0, 240)
        if 100 < xv < 140 and yv > 90:
            continue
        r = 0.6 + 7 * tt ** 1.6 * rng.uniform(0.6, 1.3)
        paint_rock(c, rock_poly(xv * U, yv * U, r * U, r * U * 0.6, seed + k), col('#2a2424'), seed + k, spec=0.25)
    # rim rocks silhouette
    for k in range(18):
        xv = rng.uniform(0, 240)
        yv = float(np.interp(xv, [p[0] for p in rim], [p[1] for p in rim]))
        r = rng.uniform(1.5, 4)
        paint_rock(c, rock_poly(xv * U, (yv + r * 0.3) * U, r * U, r * U * 0.8, seed + 50 + k, flat_base=False),
                   col('#2a2222'), seed + 50 + k, spec=0.3)
    vignette(c, 0.3, 2.4)


def island_terrain(X, Z, seed, cx=0.0, cz=2600.0, R=1600.0):
    """Shared island map (metres on the sea plane): returns (land mask 0..1, height-ish 0..1)."""
    dx = (X - cx) / R
    dz = (Z - cz) / (R * 0.8)
    r = np.sqrt(dx * dx + dz * dz)
    ang = np.arctan2(dz, dx)
    coast = 1.0 + 0.18 * (fbm(np.cos(ang) * 2 + 5, np.sin(ang) * 2 + 5, seed, 4) - 0.5) * 2
    land = 1 - smooth(coast - 0.02, coast + 0.02, r)
    height = clamp01(1 - r / coast)
    return land, height, r / coast


@scene('slope_down')
def bg_slope_down(c):
    seed = 211
    hy_v = 34
    cam = Cam(c, hy_v, h=700.0, fov=80)
    sky(c, hy_v + 1, stops=[(0.0, col('#3a72b8')), (0.7, col('#8ab8e0')), (1.0, col('#d8ecf4'))])
    cloud_bank(c, hy_v - 3, seed, n=5, size=(14, 26))
    X, Z, y0 = cam.ground()
    land, hgt, rr = island_terrain(X, Z + 0.0, seed, cx=-200, cz=1500, R=1500)
    sea = sea_rgb(X, Z, np.clip((rr - 1) * 1500, 0, 600) + 5, seed + 1, sun_x=None, W=c.W)
    jung = mix(col('#1e4a22'), col('#4a8a34'), fbm(X * 0.01, Z * 0.01, seed + 2, 5)[..., None])
    jung = jung * (0.8 + 0.4 * fbm(X * 0.04, Z * 0.04, seed + 3, 3))[..., None]
    beach = smooth(0.94, 0.985, rr) * land
    rgb = mix(sea, jung, land[..., None])
    rgb = mix(rgb, col('#e8d29a'), beach[..., None])
    # surf line
    surf = smooth(0.99, 1.0, rr) * (1 - smooth(1.0, 1.02, rr))
    rgb = mix(rgb, col('#f0fafa'), (surf * 0.8)[..., None])
    rgb = mix(rgb, col('#a8c4dc'), smooth(800, 9000, Z)[..., None] * 0.6)
    c.img[y0:] = rgb
    # the volcano's own slope in the foreground (dark ash, falling away)
    rng = np.random.default_rng(seed)
    pts = [(0, 92 * U)]
    for i in range(41):
        x = i / 40 * c.W
        pts.append((x, (100 + 12 * math.sin(i * 0.15) + 8 * (i / 40) ** 2 + rng.uniform(-0.6, 0.6)) * U))
    pts += [(c.W, c.H), (0, c.H)]
    cliff_face(c, pts, col('#4a3e38'), seed, R=U * 8, streak=1, spec=0.1)
    for k in range(14):
        xv = rng.uniform(0, 240)
        yv = rng.uniform(108, 134)
        r = rng.uniform(1.5, 5)
        paint_rock(c, rock_poly(xv * U, yv * U, r * U, r * U * 0.6, seed + k), col('#2a2424'), seed + k, spec=0.25)
    vignette(c, 0.25, 2.4)


@scene('crater')
def bg_crater(c):
    seed = 221
    sky(c, 40, stops=[(0.0, col('#2a3048')), (0.7, col('#6a5a60')), (1.0, col('#a07868'))])
    rng = np.random.default_rng(seed)
    # far wall of the crater bowl, horizontal strata, lit from the lava below
    far = []
    for i in range(41):
        far.append((i / 40 * c.W, (24 + 4 * math.sin(i * 0.3) + 2 * math.sin(i * 1.1) + rng.uniform(-0.6, 0.6)) * U))
    far += [(c.W, 124 * U), (0, 124 * U)]
    a, box = mask_crop(c, polys=[far], pad=2, blur=1)
    x0, y0, x1, y1 = box
    yy = np.arange(y0, y1, dtype=F)[:, None] / U
    xx = np.arange(x0, x1, dtype=F)[None, :] / U
    strata = fbm(xx * 0.02, yy * 0.22 + fbm(xx * 0.03, yy * 0.03, seed + 9, 2) * 4, seed, 5)
    gul = fbm(xx * 0.12, yy * 0.035, seed + 1, 4, ridged=True)
    bump = fbm(xx * 0.3, yy * 0.3, seed + 2, 4)
    t = clamp01(strata * 1.3 - 0.15)
    rgb = mix(col('#1e1818'), col('#5a4238'), t[..., None]) * (0.7 + 0.5 * gul + (bump - 0.5) * 0.4)[..., None]
    up = smooth(35, 92, yy)
    rgb = rgb * (0.55 + 0.45 * (1 - up))[..., None] + col('#ff5a1a') * (up ** 1.5 * 0.55 * (0.4 + 0.6 * gul))[..., None]
    over(c.img, a, rgb, box)
    # inner side walls sloping down to the lake
    for side in (0, 1):
        if side == 0:
            pts = [(0, 30 * U), (20 * U, 42 * U), (45 * U, 72 * U), (62 * U, 92 * U), (40 * U, 104 * U), (0, 110 * U)]
        else:
            pts = [(c.W, 34 * U), (215 * U, 48 * U), (190 * U, 76 * U), (176 * U, 92 * U), (205 * U, 104 * U), (c.W, 110 * U)]
        a, box = mask_crop(c, polys=[pts], pad=4, blur=1.5)
        x0, y0, x1, y1 = box
        yy = np.arange(y0, y1, dtype=F)[:, None] / U
        xx = np.arange(x0, x1, dtype=F)[None, :] / U
        strata = fbm(xx * 0.05, yy * 0.2 + xx * (0.08 if side == 0 else -0.08), seed + 20 + side, 5)
        bump = fbm(xx * 0.25, yy * 0.25, seed + 22 + side, 4)
        lam, _ = shape_lam(a, U * 8, (0.4 if side == 0 else -0.4, 0.9))
        rgb = mix(col('#141010'), col('#3e2e28'), clamp01(strata * 1.3 - 0.15 + (bump - 0.5) * 0.5)[..., None])
        up = smooth(40, 95, yy)
        rgb = rgb + col('#ff5a1a') * (clamp01(lam * 0.6 + up * 0.7) ** 1.5 * 0.5)[..., None]
        over(c.img, a, rgb, box)
    # lava lake: crust plates separated by glowing seams
    xx = (c.xs - 120 * U) / (92 * U)
    yy = (c.ys - 93 * U) / (11 * U)
    rr = xx * xx + yy * yy
    lm = 1 - smooth(0.9, 1.0, rr + (snoise(c.H, c.W, U * 4, seed + 2, 3) - 0.5) * 0.25)
    u = c.xs / U - 120 + c.ys * 0
    v = (c.ys / U - 80) * 4.0 + c.xs * 0
    cells = fbm(u * 0.1, v * 0.1, seed + 3, 4, ridged=True)
    seam = smooth(0.7, 0.93, cells)
    crust = mix(col('#1e0e0a'), col('#4a2216'), fbm(u * 0.4, v * 0.4, seed + 4, 3)[..., None])
    hot = mix(col('#ff3a06'), col('#ffe070'), smooth(0.85, 1.0, cells)[..., None])
    lava = mix(crust, hot, seam[..., None])
    lava = lava + col('#ff6a10') * (0.35 * (1 - clamp01(rr)) ** 2)[..., None]
    over(c.img, lm, lava)
    g = gblur(lm * (0.3 + seam), U * 8)
    c.img += (g * 0.55)[..., None] * col('#ff5010')
    for k in range(4):
        smoke_plume(c, rng.uniform(60, 180), 90, seed + 10 + k, 45, 6, drift=0.4, dark=col('#4a3430'),
                    lit=col('#c09080'), alpha=0.3)
    # rim rocks in the foreground, dark, edges lit orange from below
    rim = []
    for i in range(41):
        x = i / 40 * c.W
        y = 106 + 6 * math.cos(i / 40 * math.pi * 2) + 3 * math.sin(i * 0.9) + rng.uniform(-0.8, 0.8)
        rim.append((x, y * U))
    rim += [(c.W, c.H), (0, c.H)]
    a, box = mask_crop(c, polys=[rim], pad=4, blur=1.5)
    lam, _ = shape_lam(a, U * 3, (0.0, -1.0))
    tex = snoise(a.shape[0], a.shape[1], U * 3, seed + 6, 5)
    rgb = col('#1c1818') * (0.7 + 0.6 * tex)[..., None] + col('#ff7a2a') * (clamp01(lam) ** 2 * 0.8)[..., None]
    over(c.img, a, rgb, box)
    for k in range(8):
        xv = rng.uniform(0, 240)
        if 90 < xv < 150:
            continue
        yv = rng.uniform(116, 134)
        r = rng.uniform(4, 9)
        paint_rock(c, rock_poly(xv * U, yv * U, r * U, r * U * 0.7, seed + 30 + k), col('#2a2222'), seed + 30 + k,
                   light=(0.2, -1.0), spec=0.3, lit_col=col('#ff8a3a'))
    glow(c, 120 * U, 95 * U, 70 * U, col('#ff4a10'), 0.12, power=1.5)
    vignette(c, 0.4, 2.2)


@scene('crater_rim')
def bg_crater_rim(c):
    seed = 231
    hy_v = 60
    cam = Cam(c, hy_v, h=800.0, fov=75)
    sky(c, hy_v + 1, stops=[(0.0, col('#2f6abf')), (0.7, col('#8ab8e0')), (1.0, col('#dcecf2'))], sun=(40, 0))
    cloud_bank(c, hy_v - 3, seed, n=4, size=(16, 30))
    X, Z, y0 = cam.ground()
    land, hgt, rr = island_terrain(X, Z, seed, cx=500, cz=-200, R=1800)
    sea = sea_rgb(X, Z, np.zeros_like(Z) + 200, seed + 1, W=c.W)
    rgb = mix(sea, col('#2f6a2a'), land[..., None])
    rgb = mix(rgb, col('#a8c4dc'), smooth(800, 12000, Z)[..., None] * 0.65)
    c.img[y0:] = rgb
    # ash ground of the rim
    rng = np.random.default_rng(seed)
    pts = [(0, 80 * U)]
    for i in range(41):
        x = i / 40 * c.W
        pts.append((x, (84 - 6 * math.sin(i / 40 * math.pi) + 2 * math.sin(i * 0.7) + rng.uniform(-0.5, 0.5)) * U))
    pts += [(c.W, c.H), (0, c.H)]
    a, box = mask_crop(c, polys=[pts], pad=2, blur=1)
    x0, y0_, x1, y1 = box
    yy = np.arange(y0_, y1, dtype=F)[:, None] / U
    xx = np.arange(x0, x1, dtype=F)[None, :] / U - 120
    t = clamp01((yy - 78) / 58)
    u = xx / (0.3 + t)
    n = fbm(u * 0.3, yy * 0.3, seed + 2, 5)
    gr = fbm(xx * 1.5, yy * 1.5, seed + 3, 3)
    rgb = mix(col('#4a4240'), col('#8a7e74'), clamp01(n * 1.2 - 0.1 + (gr - 0.5) * 0.4 * t)[..., None])
    rgb = mix(rgb, col('#8a5a3a'), (clamp01((fbm(xx * 0.05, yy * 0.1, seed + 4, 3) - 0.6) * 4) * 0.4)[..., None])
    over(c.img, a, rgb, box)
    for k in range(22):
        xv = rng.uniform(0, 240)
        yv = rng.uniform(88, 136)
        r = 0.5 + 5 * ((yv - 84) / 52) ** 1.5 * rng.uniform(0.5, 1.2)
        if 95 < xv < 145 and yv > 110:
            continue
        paint_rock(c, rock_poly(xv * U, yv * U, r * U, r * U * 0.6, seed + k), col('#2e2828'), seed + k, spec=0.25)
    # a wisp of smoke drifting over from the crater behind
    smoke_plume(c, 10, 100, seed + 9, 70, 10, drift=0.6, alpha=0.3)
    vignette(c, 0.3, 2.4)


# --------------------------------------------------------------------------------------------
# Ray-cast rooms (caves, tunnels, temple, interiors)
# --------------------------------------------------------------------------------------------

INF = np.float32(1e9)
TORCH = col('#ffad5a')


class Ray:
    """Per-pixel view rays for a pinhole camera at the origin looking along +Z.
    Coordinates: x right, y up (relative to the eye), z forward; the floor is at y = -eye."""

    def __init__(self, c, hy_v=68, fov=75.0, eye=1.6, cx_v=None):
        self.c = c
        self.f = (c.W / 2) / math.tan(math.radians(fov / 2))
        self.cx = c.W / 2 if cx_v is None else cx_v * U
        self.hy = hy_v * U
        self.eye = eye
        H, W = c.H, c.W
        self.dx = np.broadcast_to((c.xs - self.cx) / self.f, (H, W)).astype(F)
        self.dy = np.broadcast_to(-(c.ys - self.hy) / self.f, (H, W)).astype(F)

    def plane(self, axis, value):
        d = {'x': self.dx, 'y': self.dy}.get(axis)
        if axis == 'z':
            return np.full(self.dx.shape, value, F)
        with np.errstate(divide='ignore', invalid='ignore'):
            t = np.where(np.abs(d) > 1e-6, value / d, INF)
        return np.where(t > 1e-3, t, INF).astype(F)

    def cylinder(self, R, zc, xc=0.0):
        """Inside of a vertical cylinder of radius R centred at (xc, zc)."""
        a = self.dx * self.dx + 1.0
        b = -2 * (xc * self.dx + zc)
        cc = xc * xc + zc * zc - R * R
        disc = np.maximum(b * b - 4 * a * cc, 0)
        return ((-b + np.sqrt(disc)) / (2 * a)).astype(F)

    def pos(self, t):
        return np.stack([self.dx * t, self.dy * t, t], axis=-1)

    def project(self, X, Y, Z):
        """World point (y relative to the eye) to working pixels."""
        return self.cx + X / Z * self.f, self.hy - Y / Z * self.f

    @staticmethod
    def combine(ts, k=0.0):
        """Nearest hit of several surfaces (smooth-min with radius k rounds the corners).
        Returns (t, index of the nearest surface)."""
        stack = np.stack(ts, axis=0)
        idx = np.argmin(stack, axis=0)
        tmin = np.min(stack, axis=0)
        if k > 0:
            e = np.exp(-np.clip((stack - tmin[None]) / k, 0, 50))
            tmin = tmin - k * np.log(np.sum(e, axis=0))
        return tmin.astype(F), idx


def normals(P, view_dx, view_dy):
    dPy, dPx = np.gradient(P, axis=(0, 1))
    N = np.cross(dPy, dPx)
    n = np.linalg.norm(N, axis=-1, keepdims=True) + 1e-9
    N = N / n
    d = np.stack([view_dx, view_dy, np.ones_like(view_dx)], axis=-1)
    flip = np.sum(N * d, axis=-1, keepdims=True) > 0
    return np.where(flip, -N, N).astype(F)


def light_up(P, N, lights, ambient=0.0, spec=0.0):
    """Diffuse lighting from point lights [(pos, colour, intensity, radius)]."""
    total = np.zeros(P.shape, F) + np.asarray(ambient, F)
    for pos, colr, inten, rad in lights:
        L = np.asarray(pos, F)[None, None, :] - P
        dist = np.linalg.norm(L, axis=-1) + 1e-6
        ndl = np.clip(np.sum(N * L, axis=-1) / dist, 0, 1)
        ndl = 0.15 + 0.85 * ndl          # a little wrap-around so nothing is pitch black next to the light
        att = inten / (1.0 + (dist / rad) ** 2)
        total += (ndl * att)[..., None] * np.asarray(colr, F)
        if spec:
            V = -P / (np.linalg.norm(P, axis=-1, keepdims=True) + 1e-6)
            Hh = L / dist[..., None] + V
            Hh = Hh / (np.linalg.norm(Hh, axis=-1, keepdims=True) + 1e-6)
            sp = np.clip(np.sum(N * Hh, axis=-1), 0, 1) ** 30 * att * spec
            total += sp[..., None] * np.asarray(colr, F)
    return total


_noise3_cache = {}


def vnoise3(x, y, z, seed):
    """Smooth 3D value noise (64-periodic lattice)."""
    if seed not in _noise3_cache:
        _noise3_cache[seed] = np.random.default_rng(seed + 555).random(64 * 64 * 64).astype(F)
    t = _noise3_cache[seed]
    xi = np.floor(x)
    yi = np.floor(y)
    zi = np.floor(z)
    fx, fy, fz = x - xi, y - yi, z - zi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    fz = fz * fz * (3 - 2 * fz)
    xi = xi.astype(np.int64) & 63
    yi = yi.astype(np.int64) & 63
    zi = zi.astype(np.int64) & 63
    x1 = (xi + 1) & 63
    y1 = (yi + 1) & 63
    z1 = (zi + 1) & 63

    def g(a, b, c_):
        return t[(a * 4096) + (b * 64) + c_]

    c00 = g(xi, yi, zi) + (g(x1, yi, zi) - g(xi, yi, zi)) * fx
    c10 = g(xi, y1, zi) + (g(x1, y1, zi) - g(xi, y1, zi)) * fx
    c01 = g(xi, yi, z1) + (g(x1, yi, z1) - g(xi, yi, z1)) * fx
    c11 = g(xi, y1, z1) + (g(x1, y1, z1) - g(xi, y1, z1)) * fx
    c0 = c00 + (c10 - c00) * fy
    c1 = c01 + (c11 - c01) * fy
    return c0 + (c1 - c0) * fz


def fbm3(P, scale, seed, octaves=4, gain=0.5, ridged=False):
    x = (P[..., 0] * scale).astype(F)
    y = (P[..., 1] * scale).astype(F)
    z = (P[..., 2] * scale).astype(F)
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        n = vnoise3(x + o * 13.7, y - o * 7.3, z + o * 3.1, seed * 17 + o)
        if ridged:
            n = (1 - np.abs(2 * n - 1)) ** 2
        total = total + n * amp
        norm += amp
        amp *= gain
        x, y, z = x * 2.02 + y * 0.1, y * 2.02 - z * 0.1, z * 2.02 + x * 0.05
    return total / norm


def tri_weights(N0):
    return None


def rock_albedo(P, W, seed, base=col('#8a7866'), dark=col('#5a4a3c')):
    """Rock colour: mottling, faint strata and colour drift (3D noise)."""
    n1 = fbm3(P, 2.2, seed, 4)
    strata = fbm(P[..., 1] * 2.5 + n1 * 3, P[..., 1] * 0.1, seed + 4, 3)
    hue = fbm3(P, 0.3, seed + 10, 2)
    t = clamp01(0.55 + (n1 - 0.5) * 1.6 + (strata - 0.5) * 0.3)
    alb = mix(dark, base, t[..., None])
    alb = alb * (1 + (hue[..., None] - 0.5) * np.array([0.5, 0.2, -0.3], F))
    return alb


def cave_bump(P, W, seed, amp=0.18, scale=1.2, octaves=4):
    return (fbm3(P, scale, seed, octaves, gain=0.45) - 0.5) * amp


def tonemap(rgb, exposure=1.3):
    return (1 - np.exp(-np.clip(rgb, 0, None) * exposure)).astype(F)


def finish_underground(c, amount=0.65, seed=0):
    vignette(c, amount, 2.0)
    grain(c, 0.012, seed)


def render_cave(c, seed, D=9.0, half_w=3.2, ceil=1.8, k=0.35, bump=0.25, opening=None, torch=True, hy_v=68,
                base=col('#a8927a'), dark=col('#5e4c3e'), lights=None, ambient=0.0, extra=None, eye=1.6,
                fov=75.0, back=True, torch_power=16.0, big=3.0, disp_fn=None, albedo_fn=None):
    """A torch-lit rocky cavern / tunnel. opening: function(P) -> mask of a dark passage in the back wall."""
    r = Ray(c, hy_v, fov, eye)
    surfaces = [r.plane('y', -eye), r.plane('y', ceil), r.plane('x', -half_w), r.plane('x', half_w)]
    if back:
        surfaces.append(r.plane('z', D))
    t, idx = Ray.combine(surfaces, k)
    P = r.pos(t)
    # how much each pixel is floor (flatter, gravelly) vs rock wall
    wf = smooth(-eye + 0.5, -eye + 0.1, P[..., 1])
    if disp_fn is not None:
        t = disp_fn(r, P, t, idx)
    else:
        n_big = (fbm3(P, 0.28, seed, 3) - 0.5) * 3.0
        n_mid = (fbm3(P, 1.1, seed + 1, 3) - 0.5) * 3.0
        t = t + n_big * bump * big * 0.35 * (1 - 0.85 * wf) + n_mid * bump * 0.35 * (1 - 0.6 * wf)
        P = r.pos(t)
        t = t + (fbm3(P, 3.5, seed + 2, 3, ridged=True) - 0.5) * bump * 0.25 * (1 - 0.5 * wf)
    if opening is not None:
        om = opening(r, P)
        t = np.where(om > 0.5, t + 30.0, t)
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    if albedo_fn is not None:
        alb = albedo_fn(P, N, idx, wf)
    else:
        alb = rock_albedo(P, None, seed, base, dark)
        gravel = mix(col('#3a3026'), col('#7a6852'), fbm3(P, 6.0, seed + 5, 3)[..., None])
        alb = mix(alb, gravel, (wf * 0.7)[..., None])
    # cavity darkening: recesses (further than their surroundings) get less light
    tb = gblur(t, U * 2.5)
    ao = clamp01(1 - np.clip(t - tb, 0, None) * 2.5 / np.maximum(t, 1) ** 0.5)
    if lights is None:
        lights = []
    if torch:
        lights = lights + [((-0.5, 0.15, 0.3), TORCH, torch_power, 1.5)]
    lit = light_up(P, N, lights, ambient, spec=0.0)
    shine = light_up(P, N, lights, 0.0, spec=0.3) - lit + np.asarray(ambient, F)
    rgb = tonemap((alb * lit + shine * 0.4) * ao[..., None], 1.1)
    if extra is not None:
        rgb = extra(r, P, N, t, rgb)
    c.img = rgb.astype(F)
    return r, P, N, t


def arch_mask(r, P, cx, y0, y1, half_w, D, rough=0.0, seed=0):
    """Screen-space mask of an arch-shaped hole in the plane z = D (world units, y relative to the eye)."""
    x0_, yb = r.project(cx - half_w, y0, D)
    x1_, _ = r.project(cx + half_w, y0, D)
    _, yt = r.project(cx, y1, D)
    xs = r.c.xs
    ys = r.c.ys
    w = (x1_ - x0_) / 2
    xc = (x0_ + x1_) / 2
    u = (xs - xc) / w
    ycap = yt + w
    sh = np.where(ys < ycap, np.sqrt(u * u + ((ys - ycap) / w) ** 2), np.abs(u))
    lim = 1.0
    if rough:
        lim = 1.0 + (snoise(r.c.H, r.c.W, U * 2, seed, 4) - 0.5) * rough
    m = (sh < lim) & (ys < yb)
    return gblur(np.broadcast_to(m, (r.c.H, r.c.W)).astype(F), 1.5)


@scene('cave_wall')
def bg_cave_wall(c):
    render_cave(c, 241, D=7.5, half_w=3.5, ceil=1.6, k=1.3, bump=0.45, big=7.0)
    finish_underground(c, seed=241)


@scene('cave_opening')
def bg_cave_opening(c):
    def opening(r, P):
        return arch_mask(r, P, 0.0, -1.6, 0.6, 1.0, 7.5, rough=0.12, seed=7)

    def extra(r, P, N, t, rgb):
        m = opening(r, P)
        m = gblur(m, U * 0.5)
        inner = gblur(m, U * 4)
        rgb = rgb * (1 - m[..., None]) * (1 - 0.5 * gblur(m, U * 2)[..., None] * (1 - m[..., None])) \
            + (col('#0c0806') * (0.3 + inner[..., None])) * m[..., None]
        return rgb
        return rgb

    render_cave(c, 251, D=7.5, half_w=3.5, ceil=1.6, k=1.3, bump=0.4, opening=opening, extra=extra, big=7.0)
    finish_underground(c, seed=251)


@scene('tunnel_path')
def bg_tunnel_path(c):
    render_cave(c, 261, D=60, half_w=1.5, ceil=0.9, k=0.7, bump=0.3, back=False, torch_power=8.0, big=4.0)
    finish_underground(c, seed=261)


@scene('tunnel_wall')
def bg_tunnel_wall(c):
    render_cave(c, 271, D=8.0, half_w=1.5, ceil=0.9, k=0.7, bump=0.3, torch_power=8.0, big=4.0)
    finish_underground(c, seed=271)


# --------------------------------------------------------------------------------------------
# Underground: temple, stalactites, crystals, lair, diamond chamber, cellar
# --------------------------------------------------------------------------------------------

def relief_map(seed, w_m=9.0, h_m=4.0, ppm=120, centre_gap=1.4):
    """Height map of carved reliefs for the temple wall: a meander frieze, sun discs, serpents and
    seated figures (x from -w_m/2, y from the floor up). Returns (array, ppm, x0)."""
    W, H = int(w_m * ppm), int(h_m * ppm)
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed)

    def X(x):
        return (x + w_m / 2) * ppm

    def Y(y):
        return H - y * ppm

    # meander (Greek key) frieze at 2.3..2.6 m
    y0, y1 = 2.3, 2.62
    step = 0.32
    x = -w_m / 2
    while x < w_m / 2:
        pts = [(x, y0), (x, y1), (x + step * 0.8, y1), (x + step * 0.8, y0 + 0.1), (x + step * 0.3, y0 + 0.1),
               (x + step * 0.3, y1 - 0.1)]
        d.line([(X(a), Y(b)) for a, b in pts], fill=200, width=int(0.05 * ppm))
        x += step
    d.rectangle((0, Y(y1 + 0.06), W, Y(y1 + 0.02)), fill=160)
    d.rectangle((0, Y(y0 - 0.02), W, Y(y0 - 0.06)), fill=160)
    for side in (-1, 1):
        # panels with seated figures
        for k in range(2):
            cx = side * (centre_gap + 0.9 + k * 1.5)
            d.rectangle((X(cx - 0.62), Y(2.05), X(cx + 0.62), Y(0.55)), outline=150, width=int(0.05 * ppm))
            # seated figure: head, halo, body, crossed legs, arms
            d.ellipse((X(cx - 0.3), Y(1.95), X(cx + 0.3), Y(1.35)), outline=120, width=int(0.03 * ppm))
            d.ellipse((X(cx - 0.13), Y(1.8), X(cx + 0.13), Y(1.5)), fill=230)
            d.polygon([(X(cx - 0.25), Y(1.45)), (X(cx + 0.25), Y(1.45)), (X(cx + 0.3), Y(0.95)), (X(cx - 0.3), Y(0.95))], fill=210)
            d.ellipse((X(cx - 0.45), Y(1.0), X(cx + 0.45), Y(0.72)), fill=200)
            d.line([(X(cx - 0.25), Y(1.35)), (X(cx - 0.1), Y(1.1)), (X(cx + 0.1), Y(1.1)), (X(cx + 0.25), Y(1.35))],
                   fill=240, width=int(0.06 * ppm))
        # sun disc with rays above the frieze
        sx = side * (centre_gap + 2.2)
        d.ellipse((X(sx - 0.25), Y(3.35), X(sx + 0.25), Y(2.85)), fill=220)
        for a in range(12):
            ang = a / 12 * 2 * math.pi
            d.line([(X(sx + math.cos(ang) * 0.3), Y(3.1 + math.sin(ang) * 0.3)),
                    (X(sx + math.cos(ang) * 0.45), Y(3.1 + math.sin(ang) * 0.45))], fill=180, width=int(0.04 * ppm))
        # a serpent along the base
        pts = [(X(side * (centre_gap + 0.2 + t * 3.2)), Y(0.3 + 0.08 * math.sin(t * 18))) for t in np.linspace(0, 1, 40)]
        d.line(pts, fill=200, width=int(0.07 * ppm), joint='curve')
        hx, hy = pts[-1]
        d.ellipse((hx - 0.08 * ppm, hy - 0.06 * ppm, hx + 0.1 * ppm, hy + 0.06 * ppm), fill=220)
    arr = np.asarray(im.filter(ImageFilter.GaussianBlur(0.02 * ppm)), F) / 255.0
    return arr, ppm, w_m / 2


def sample_map(arr, ppm, x0, u, v):
    """Samples a map at world (u, v) metres (u from -x0, v from the floor up)."""
    H, W = arr.shape
    xi = np.clip(((u + x0) * ppm).astype(np.int64), 0, W - 1)
    yi = np.clip((H - v * ppm).astype(np.int64), 0, H - 1)
    inside = (u > -x0) & (u < x0) & (v > 0) & (v < H / ppm)
    return np.where(inside, arr[yi, xi], 0.0)


def temple(c, seed, opening=False):
    eye = 1.6
    D = 7.6
    hw = 4.6
    relief, ppm, rx0 = relief_map(seed)

    def disp(r, P, t, idx):
        # idx: 0 floor, 1 ceiling, 2 left, 3 right, 4 back
        back = idx == 4
        v = P[..., 1] + eye
        u = P[..., 0]
        rel = sample_map(relief, ppm, rx0, u, v)
        _, _, m = masonry(u, v, 1.1, 0.55, seed, col('#ffffff'), mortar=0.05)
        t = t - np.where(back, rel * 0.14 + m * 0.03, 0)
        # side walls: blocks too
        side = (idx == 2) | (idx == 3)
        _, _, ms = masonry(P[..., 2], v, 1.1, 0.55, seed + 1, col('#ffffff'), mortar=0.05)
        t = t - np.where(side, ms * 0.02 * np.abs(r.dx) / (np.abs(r.dx) + 0.05), 0)
        # floor flagstones
        fl = idx == 0
        _, _, mf = masonry(P[..., 0], P[..., 2], 1.2, 1.2, seed + 2, col('#ffffff'), mortar=0.03)
        t = t - np.where(fl, mf * 0.015 / np.maximum(np.abs(r.dy), 0.05) * 0.05, 0)
        Pd = r.pos(t)
        t = t + (fbm3(Pd, 6.0, seed + 3, 3) - 0.5) * 0.02
        return t

    def alb(P, N, idx, wf):
        v = P[..., 1] + eye
        u = P[..., 0]
        rgb_b, _, _ = masonry(u, v, 1.1, 0.55, seed, col('#a8927a'), mortar=0.04, var=0.25)
        rgb_s, _, _ = masonry(P[..., 2], v, 1.1, 0.55, seed + 1, col('#a8927a'), mortar=0.05, var=0.15)
        rgb_f, _, _ = masonry(P[..., 0], P[..., 2], 1.2, 1.2, seed + 2, col('#8a7a66'), mortar=0.03, var=0.2)
        out = np.where((idx == 4)[..., None], rgb_b, np.where(((idx == 2) | (idx == 3))[..., None], rgb_s, rgb_f))
        rel = sample_map(relief, ppm, rx0, u, v) * (idx == 4)
        out = out * (1 - 0.25 * rel[..., None])
        grime = fbm3(P, 0.8, seed + 4, 3)
        return out * (0.75 + 0.5 * grime[..., None])

    op = None
    if opening:
        def op(r, P):
            x0_, yb = r.project(-0.75, -eye, D)
            x1_, yt = r.project(0.75, -eye + 1.9, D)
            m = (r.c.xs > x0_) & (r.c.xs < x1_) & (r.c.ys > yt) & (r.c.ys < yb)
            return np.broadcast_to(m, (c.H, c.W)).astype(F)

    def extra(r, P, N, t, rgb):
        if opening:
            m = gblur(op(r, P), 1.5)
            inner = gblur(m, U * 3)
            rgb = rgb * (1 - m[..., None]) + col('#0a0705') * (0.3 + inner[..., None]) * m[..., None]
        return rgb

    r = Ray(c, 68, 75.0, eye)
    surfaces = [r.plane('y', -eye), r.plane('y', 2.2), r.plane('x', -hw), r.plane('x', hw), r.plane('z', D)]
    t, idx = Ray.combine(surfaces, 0.0)
    P = r.pos(t)
    t = disp(r, P, t, idx)
    if op is not None:
        t = np.where(op(r, P) > 0.5, t + 20, t)
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    a = alb(P, N, idx, None)
    lights = [((-0.9, 0.3, 0.6), TORCH, 18.0, 1.6)]
    lit = light_up(P, N, lights, 0.0)
    rgb = tonemap(a * lit, 1.1)
    rgb = extra(r, P, N, t, rgb)
    c.img = rgb.astype(F)
    if opening:
        # a lintel stone over the passage
        x0_, yt = r.project(-0.95, -eye + 2.05, D - 0.05)
        x1_, yb = r.project(0.95, -eye + 1.85, D - 0.05)
        lay, d = c.layer()
        d.rectangle((x0_, yt, x1_, yb), fill=rgb255(col('#5a4836')) + (255,))
        d.rectangle((x0_, yt, x1_, yt + (yb - yt) * 0.3), fill=rgb255(col('#7a634a')) + (255,))
        c.comp(lay)
    finish_underground(c, seed=seed)


@scene('temple_wall')
def bg_temple_wall(c):
    temple(c, 281)


@scene('temple_opening')
def bg_temple_opening(c):
    temple(c, 281, opening=True)


def cone_feature(c, r, X, Y0, Z, length, rad, seed, down=True, base=col('#8c7660'), lights=None, wet=0.3):
    """A stalactite (down) or stalagmite (up) at world position, shaded by the torch."""
    xs_, ys_ = r.project(X, Y0, Z)
    tip_y = Y0 - length if down else Y0 + length
    xt, yt = r.project(X + rad * 0.2, tip_y, Z)
    _, = [0]
    xr = rad * r.f / Z
    rng = np.random.default_rng(seed)
    pts = []
    n = 14
    for i in range(n + 1):
        t = i / n
        w = xr * (1 - t) ** 1.3 * (1 + 0.15 * math.sin(t * 9 + seed))
        pts.append((xs_ + (xt - xs_) * t - w, ys_ + (yt - ys_) * t))
    for i in range(n, -1, -1):
        t = i / n
        w = xr * (1 - t) ** 1.3 * (1 + 0.15 * math.cos(t * 7 + seed))
        pts.append((xs_ + (xt - xs_) * t + w, ys_ + (yt - ys_) * t))
    a, box = mask_crop(c, polys=[pts], pad=3, blur=0.8)
    if a is None:
        return
    x0, y0, x1, y1 = box
    xx = np.arange(x0, x1, dtype=F)[None, :]
    yy = np.arange(y0, y1, dtype=F)[:, None]
    tt = clamp01((yy - ys_) / (yt - ys_)) if yt != ys_ else 0
    cxl = xs_ + (xt - xs_) * tt
    wl = np.maximum(xr * (1 - tt) ** 1.3, 1)
    u = np.clip((xx - cxl) / wl, -1, 1)
    # lit from the torch on the left
    lam = 0.35 + 0.65 * np.sqrt(clamp01(1 - u * u)) * (0.7 - 0.5 * u)
    ring = fbm(xx * 0.0 + tt * 12, u * 3, seed, 4)
    dist = math.sqrt(X * X + (Y0 - 0.2) ** 2 + Z * Z)
    att = 16.0 / (1 + (dist / 1.6) ** 2)
    rgb = base * (lam * (0.8 + 0.4 * ring))[..., None] * TORCH * att
    rgb = rgb + (clamp01(1 - np.abs(u + 0.45) * 5) * wet * att * 0.3)[..., None]
    rgb = tonemap(rgb, 1.1)
    over(c.img, a, rgb, box)


@scene('stalactites')
def bg_stalactites(c):
    seed = 291
    r, P, N, t = render_cave(c, seed, D=16, half_w=3.5, ceil=2.6, k=1.0, bump=0.4, big=6.0, back=True)
    rng = np.random.default_rng(seed)
    items = []
    for k in range(70):
        Z = rng.uniform(2.5, 15)
        X = rng.uniform(-3.4, 3.4)
        L = rng.uniform(0.4, 2.4) * (0.4 if abs(X) < 0.9 else 1.0)
        items.append((Z, X, L, k, True))
    for k in range(26):
        Z = rng.uniform(2.5, 14)
        X = rng.choice([-1, 1]) * rng.uniform(1.4, 3.3)
        items.append((Z, X, rng.uniform(0.3, 1.4), 100 + k, False))
    items.sort(reverse=True)
    for Z, X, L, k, down in items:
        if down:
            cone_feature(c, r, X, 2.6 - 0.2, Z, L, 0.08 + 0.06 * L, seed + k, True)
        else:
            cone_feature(c, r, X, -1.6, Z, L, 0.12 + 0.08 * L, seed + k, False)
    finish_underground(c, seed=seed)


@scene('lit_room')
def bg_lit_room(c):
    seed = 301
    rng = np.random.default_rng(seed)
    spots = []
    for k in range(7):
        side = -1 if k % 2 else 1
        X = side * rng.uniform(1.8, 3.2)
        Z = rng.uniform(3.0, 9.0)
        Y = rng.uniform(-1.5, 0.8)
        spots.append((X, Y, Z))
    spots.append((0.6, -1.5, 8.5))
    lights = [((x * 0.85, y, z), col('#4dffb0'), 1.1, 0.8) for x, y, z in spots]
    lights.append(((0, 1.5, 6), col('#3060ff'), 0.08, 4.0))
    r, P, N, t = render_cave(c, seed, D=10, half_w=3.6, ceil=2.0, k=1.2, bump=0.45, big=6.0, torch=False,
                             lights=lights, ambient=col('#03080a'), base=col('#9aa8a0'), dark=col('#3a4a48'))
    # crystal clusters and glowing fungi at the light spots
    lay, d = c.layer(shadows=False)
    gl = np.zeros((c.H, c.W), F)
    for (X, Y, Z) in sorted(spots, key=lambda s: -s[2]):
        x, y = r.project(X, Y, Z)
        sc = r.f / Z
        for j in range(int(rng.integers(4, 8))):
            ang = -math.pi / 2 + rng.uniform(-0.9, 0.9) + (0.4 if X < 0 else -0.4)
            L = sc * rng.uniform(0.25, 0.7)
            w = sc * rng.uniform(0.06, 0.12)
            ca, sa = math.cos(ang), math.sin(ang)
            nx, ny = -sa, ca
            p0 = (x + nx * w, y + ny * w)
            p1 = (x - nx * w, y - ny * w)
            tip = (x + ca * L, y + sa * L)
            mid0 = (x + ca * L * 0.8 + nx * w, y + sa * L * 0.8 + ny * w)
            mid1 = (x + ca * L * 0.8 - nx * w, y + sa * L * 0.8 - ny * w)
            d.polygon([p0, mid0, tip, mid1, p1], fill=(90, 255, 190, 255))
            d.polygon([p0, mid0, tip, (x + ca * L * 0.5, y + sa * L * 0.5)], fill=(200, 255, 235, 255))
        for j in range(int(rng.integers(2, 5))):
            fx = x + rng.uniform(-0.5, 0.5) * sc
            fy = y + rng.uniform(0.1, 0.3) * sc
            fr = sc * rng.uniform(0.07, 0.15)
            d.line([(fx, fy), (fx, fy - fr * 1.6)], fill=(150, 220, 200, 255), width=max(1, int(fr * 0.35)))
            d.chord((fx - fr, fy - fr * 2.4, fx + fr, fy - fr * 0.9), 180, 360, fill=(120, 255, 210, 255))
    c.comp(lay)
    im = lay.image()
    al = np.asarray(im, F)[..., 3] / 255.0
    g = gblur(al, U * 3) + gblur(al, U * 10) * 0.8
    c.img += (g * 0.6)[..., None] * col('#40ffa8')
    finish_underground(c, amount=0.5, seed=seed)


def bone(d, x, y, L, ang, w, color):
    ca, sa = math.cos(ang), math.sin(ang)
    x0, y0 = x - ca * L / 2, y - sa * L / 2 * 0.4
    x1, y1 = x + ca * L / 2, y + sa * L / 2 * 0.4
    d.line([(x0, y0), (x1, y1)], fill=rgb255(color) + (255,), width=max(2, int(w)))
    for (ex, ey) in ((x0, y0), (x1, y1)):
        for o in (-1, 1):
            d.ellipse((ex - w * 0.8 + o * sa * w * 0.6, ey - w * 0.55 - o * ca * w * 0.3,
                       ex + w * 0.8 + o * sa * w * 0.6, ey + w * 0.55 - o * ca * w * 0.3), fill=rgb255(color) + (255,))


def skull(d, x, y, s, color):
    d.ellipse((x - s, y - s * 1.1, x + s, y + s * 0.5), fill=rgb255(color) + (255,))
    d.rectangle((x - s * 0.55, y + s * 0.2, x + s * 0.55, y + s * 0.75), fill=rgb255(color * 0.9) + (255,))
    for o in (-1, 1):
        d.ellipse((x + o * s * 0.45 - s * 0.28, y - s * 0.35, x + o * s * 0.45 + s * 0.28, y + s * 0.12), fill=(15, 8, 6, 255))
    d.polygon([(x, y + s * 0.05), (x - s * 0.12, y + s * 0.3), (x + s * 0.12, y + s * 0.3)], fill=(20, 10, 8, 255))


@scene('lair')
def bg_lair(c):
    seed = 311
    red = ((0.5, -2.2, 16.0), col('#ff3010'), 4.0, 4.0)

    def extra(r, P, N, t, rgb):
        # a glowing chasm across the far floor
        x0_, y0_ = r.project(0, -1.6, 13.0)
        _, y1_ = r.project(0, -1.6, 17.0)
        n = snoise(c.H, c.W, U * 6, seed, 3)
        band = smooth(y1_ - U * 2, y1_ + U * 2, c.ys + (n - 0.5) * U * 8) * (1 - smooth(y0_ - U * 4, y0_ + U * 2, c.ys + (n - 0.5) * U * 10))
        band = np.broadcast_to(band, (c.H, c.W))
        hot = mix(col('#ff2a08'), col('#ffb040'), clamp01((n - 0.4) * 3)[..., None])
        rgb = mix(rgb, hot, (band * 0.9)[..., None])
        rgb = rgb + (gblur(band, U * 8) * 0.6)[..., None] * col('#ff4010')
        return rgb

    r, P, N, t = render_cave(c, seed, D=24, half_w=10, ceil=5.0, k=2.5, bump=0.6, big=8.0, lights=[red],
                             ambient=col('#120404'), extra=extra, torch_power=14.0)
    # bones scattered on the floor
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    items = []
    for k in range(60):
        Z = rng.uniform(2.2, 12)
        X = rng.uniform(-6, 6)
        if abs(X) < 0.8 and Z < 6:
            continue
        items.append((Z, X, k))
    items.sort(reverse=True)
    for Z, X, k in items:
        x, y = r.project(X, -1.6, Z)
        sc = r.f / Z
        dist = math.sqrt(X * X + 3 + Z * Z)
        att = min(1.0, 3.0 / (1 + (dist / 3.5) ** 2) + 0.1)
        colr = np.clip(col('#e8d8b8') * att * mix(np.ones(3, F), col('#ffb070'), 0.5), 0, 1)
        if rng.random() < 0.15:
            skull(d, x, y - sc * 0.08, sc * 0.11, colr)
        else:
            bone(d, x, y, sc * rng.uniform(0.25, 0.5), rng.uniform(0, math.pi), sc * 0.035, colr)
    c.comp(lay)
    finish_underground(c, amount=0.55, seed=seed)


@scene('diamond_room')
def bg_diamond_room(c):
    seed = 321
    beam = ((0.0, 1.9, 4.0), col('#f4f8ff'), 3.5, 1.3)
    r, P, N, t = render_cave(c, seed, D=6.2, half_w=2.8, ceil=2.0, k=1.0, bump=0.4, big=6.0, lights=[beam],
                             torch_power=6.0)
    # shaft of light from a hole in the roof
    lay, d = c.layer(shadows=False)
    xa, ya = r.project(-0.35, 2.4, 4.0)
    xb, _ = r.project(0.35, 2.4, 4.0)
    xc_, yc = r.project(-0.75, -1.6, 4.0)
    xd, _ = r.project(0.75, -1.6, 4.0)
    d.polygon([(xa, -10), (xb, -10), (xd, yc), (xc_, yc)], fill=(255, 255, 255, 150))
    c.comp(lay, blur=U * 2)
    hole = gblur(np.broadcast_to(((c.xs > xa) & (c.xs < xb) & (c.ys < U * 4)), (c.H, c.W)).astype(F), U)
    over(c.img, hole, col('#ffffff'))
    # pool of light on the floor
    a, box = mask_crop(c, ellipses=[(xc_ - U * 4, yc - U * 4, xd + U * 4, yc + U * 5)], blur=U * 3)
    c.img[box[1]:box[3], box[0]:box[2]] += (a * 0.35)[..., None] * col('#fff8f0')
    # carved stone pedestal: top at y 96, centred on x 120
    cx = 120 * U
    top = 96 * U
    _, base_y = r.project(0, -1.6, 4.0)
    hgt = base_y - top
    w = hgt * 0.36
    shapes = [
        (top - hgt * 0.02, top + hgt * 0.1, w * 1.05),          # top slab
        (top + hgt * 0.1, top + hgt * 0.18, w * 0.85),          # moulding
        (top + hgt * 0.18, base_y - hgt * 0.2, w * 0.6),        # shaft
        (base_y - hgt * 0.2, base_y - hgt * 0.1, w * 0.85),     # base moulding
        (base_y - hgt * 0.1, base_y, w * 1.0),                  # plinth
    ]
    for (y0, y1, hw) in shapes:
        X0, X1 = int(cx - hw), int(cx + hw)
        Y0, Y1 = int(y0), int(y1)
        xx = (np.arange(X0, X1, dtype=F)[None, :] - cx) / hw
        yy = np.arange(Y0, Y1, dtype=F)[:, None]
        tex = snoise(Y1 - Y0, X1 - X0, U * 0.8, seed + Y0, 3)
        lam = np.sqrt(clamp01(1 - xx * xx * 0.9)) * (0.75 - 0.3 * xx)
        topl = clamp01(1 - (yy - Y0) / (U * 1.2)) * 0.6
        v = (0.3 + 0.8 * lam + topl) * (0.85 + 0.3 * tex)
        rgb = col('#c8bca8') * v[..., None] * mix(np.ones(3, F), col('#eef4ff'), 0.5)
        c.img[Y0:Y1, X0:X1] = rgb
    # carved band on the shaft
    lay, d = c.layer(shadows=False)
    for k in range(5):
        yk = top + hgt * (0.3 + 0.1 * k)
        d.line([(cx - w * 0.55, yk), (cx + w * 0.55, yk)], fill=(70, 62, 52, 160), width=int(U * 0.3))
    d.d.ellipse((cx - w * 0.25, top + hgt * 0.36, cx + w * 0.25, top + hgt * 0.56), outline=(70, 62, 52, 200), width=int(U * 0.4))
    c.comp(lay)
    contact_shadow(c, 120, base_y / U, w * 1.3 / U, 1.5, 0.5)
    glow(c, cx, top - U * 2, U * 10, col('#ffffff'), 0.25)
    finish_underground(c, amount=0.55, seed=seed)


@scene('cellar')
def bg_cellar(c):
    seed = 331
    eye = 1.6
    D = 4.2
    hw = 2.0
    ceil = 0.9
    r = Ray(c, 50, 90.0, eye)
    surfaces = [r.plane('y', -eye), r.plane('y', ceil), r.plane('x', -hw), r.plane('x', hw), r.plane('z', D)]
    t, idx = Ray.combine(surfaces, 0.0)
    P = r.pos(t)
    hole = (idx == 1) & (np.abs(P[..., 0]) < 0.55) & (np.abs(P[..., 2] - 3.4) < 0.55)
    v = P[..., 1] + eye
    rgb_b, _, mb = masonry(P[..., 0], v, 0.6, 0.3, seed, col('#8a7660'), mortar=0.1, var=0.35)
    rgb_s, _, ms = masonry(P[..., 2], v, 0.6, 0.3, seed + 1, col('#8a7660'), mortar=0.1, var=0.35)
    rgb_f, _, mf = masonry(P[..., 0], P[..., 2], 0.6, 0.6, seed + 2, col('#6a5a48'), mortar=0.06, var=0.3)
    side = ((idx == 2) | (idx == 3))
    m = np.where(idx == 4, mb, np.where(side, ms, mf))
    t = t - m * 0.04 + (fbm3(P, 5.0, seed + 3, 3) - 0.5) * 0.05
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    alb = np.where((idx == 4)[..., None], rgb_b, np.where(side[..., None], rgb_s, rgb_f))
    alb = np.where((idx == 1)[..., None], col('#5a4630') * (0.8 + 0.4 * fbm(P[..., 0] * 8, P[..., 2] * 1, seed, 3))[..., None], alb)
    alb = alb * (0.7 + 0.6 * fbm3(P, 0.9, seed + 4, 3))[..., None]
    lights = [((0.0, 0.7, 3.4), col('#e8f0ff'), 3.0, 1.2), ((-0.4, 0.1, 0.3), TORCH, 1.5, 1.0)]
    rgb = tonemap(alb * light_up(P, N, lights, col('#0a0a0c')), 1.1)
    hm = gblur(hole.astype(F), 2)
    rgb = mix(rgb, mix(col('#bfe0ff'), col('#ffffff'), 0.5)[None, None, :] * np.ones_like(rgb), hm[..., None])
    c.img = rgb.astype(F)
    # light shaft
    lay, d = c.layer(shadows=False)
    pa = r.project(-0.55, ceil, 2.9)
    pb = r.project(0.55, ceil, 2.9)
    pc = r.project(0.75, -eye, 3.7)
    pd = r.project(-0.35, -eye, 3.7)
    d.polygon([pa, pb, pc, pd], fill=(230, 240, 255, 90))
    c.comp(lay, blur=U * 2.5)
    # wooden ladder up to the trapdoor
    lay, d = c.layer()
    for xr_ in (-0.32, 0.32):
        b0 = r.project(xr_, -eye, 3.85)
        b1 = r.project(xr_ * 0.95, ceil + 0.4, 3.3)
        w = 0.05 * r.f / 3.6
        d.polygon([(b0[0] - w, b0[1]), (b0[0] + w, b0[1]), (b1[0] + w * 0.9, b1[1]), (b1[0] - w * 0.9, b1[1])],
                  fill=rgb255(col('#8a6a44')) + (255,))
        d.line([(b0[0] - w * 0.6, b0[1]), (b1[0] - w * 0.5, b1[1])], fill=rgb255(col('#c09a68')) + (255,), width=int(w * 0.5))
    for k in range(9):
        f = (k + 0.5) / 9
        z = 3.85 - 0.55 * f
        y = -eye + (ceil + 0.4 + eye) * f
        a_ = r.project(-0.32, y, z)
        b_ = r.project(0.32, y, z)
        hh = 0.035 * r.f / z
        d.rectangle((a_[0], a_[1] - hh, b_[0], a_[1] + hh), fill=rgb255(col('#9a7650')) + (255,))
        d.rectangle((a_[0], a_[1] - hh, b_[0], a_[1] - hh * 0.3), fill=rgb255(col('#c8a070')) + (255,))
    c.comp(lay)
    contact_shadow(c, 120, r.project(0, -eye, 3.85)[1] / U, 12, 1.2, 0.4)
    finish_underground(c, amount=0.6, seed=seed)


# --------------------------------------------------------------------------------------------
# Daylit interiors: tower, hut, hangar
# --------------------------------------------------------------------------------------------

_outside_cache = {}


def outside_view(kind, seed, hy=HY):
    """A bright outdoor picture (full canvas array) to show through doorways."""
    key = (kind, seed, hy)
    if key in _outside_cache:
        return _outside_cache[key]
    c2 = Canvas(240, 136)
    cam = Cam(c2, hy)
    if kind == 'jungle':
        jungle_surround(c2, cam, seed, Z=14.0, trees=False)
        side_ferns(c2, seed + 1, 100)
    elif kind == 'clearing':
        jungle_surround(c2, cam, seed, Z=22.0)
        earth_patch(c2, 120, 110, 80, 20, seed, strength=0.9)
    elif kind == 'runway':
        day_sky(c2, seed, sun=(60, -10), n=4, horizon=hy)
        meadow(c2, cam, seed, cam.hy, flowers=False, grass_col=col('#6aa040'))
        X, Z, y0 = cam.ground()
        strip = (1 - smooth(6, 9, np.abs(X))) * (1 - smooth(200, 600, Z))
        tex = fbm(X * 0.5, Z * 0.5, seed, 3)
        over(c2.img[y0:], strip * 0.55, mix(col('#8a9a5a'), col('#b0b080'), tex[..., None]))
        jungle_wall_across(c2, cam, seed + 3, Z=120.0, height=12.0, palms=14, far=False)
    img = c2.img.copy()
    _outside_cache[key] = img
    return img


def daylight_beam(c, quad, alpha=0.35, color=(255, 246, 220), blur=None):
    lay, d = c.layer(shadows=False)
    d.polygon(quad, fill=tuple(color) + (int(255 * alpha),))
    c.comp(lay, blur=blur or U * 2)


def tower_interior(c, seed, door=False):
    eye = 1.6
    R = 4.0
    zc = 2.8
    r = Ray(c, 64, 75.0, eye)
    t_wall = r.cylinder(R, zc)
    t_floor = r.plane('y', -eye)
    t = np.minimum(t_wall, t_floor)
    is_floor = t_floor < t_wall
    P = r.pos(t)
    ang = np.arctan2(P[..., 0], P[..., 2] - zc)
    u = ang * R
    v = P[..., 1] + eye
    rgb_w, _, mw = masonry(u, v, 0.8, 0.42, seed, col('#968a74'), mortar=0.07, var=0.4, offset=0.45, rough=3.0)
    # floor: packed dirt with stones
    fn = fbm(P[..., 0] * 1.5, P[..., 2] * 1.5, seed + 1, 4)
    fs = fbm(P[..., 0] * 7, P[..., 2] * 7, seed + 2, 3)
    rgb_f = mix(col('#4a3a28'), col('#7a6448'), fn[..., None]) * (1 + clamp01((fs - 0.6) * 4)[..., None] * 0.3)
    t = t - np.where(is_floor, 0, mw * 0.04) + (fbm3(P, 4.0, seed + 3, 3) - 0.5) * 0.04
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    alb = np.where(is_floor[..., None], rgb_f, rgb_w)
    alb = alb * (0.7 + 0.6 * fbm3(P, 0.7, seed + 4, 3))[..., None]
    # moss and damp low on the wall
    damp = smooth(1.2, 0.0, v) * (1 - is_floor)
    alb = mix(alb, col('#3a4a2a'), (damp * 0.5)[..., None])
    # slit window to the left, open doorway straight ahead
    wa = -0.85
    wx, wz = R * math.sin(wa), zc + R * math.cos(wa)
    win = (~is_floor) & (np.abs(ang - wa) < 0.05) & (v > 1.5) & (v < 3.0)
    lights = [((wx * 0.8, 0.6, wz * 0.9), col('#e8f0ff'), 1.2, 2.0),
              ((0.6, -1.4, 3.5), col('#fff4dc'), 1.6, 0.9)]
    amb = col('#0b0c10')
    dm = None
    if door:
        dm = (~is_floor) & (np.abs(u) < 0.85) & (v < 1.9 + np.sqrt(np.clip(0.85 ** 2 - u * u, 0, None)))
        lights.append(((0.0, -0.4, zc + R - 0.4), col('#fff2d8'), 5.0, 1.8))
        amb = col('#14140f')
    lit = light_up(P, N, lights, amb)
    rgb = tonemap(alb * lit, 1.2)
    if door:
        dmf = gblur(dm.astype(F), 1.5)
        out = outside_view('jungle', seed)
        out = tonemap(out * 1.6, 1.0) * 1.05
        rgb = mix(rgb, out, dmf[..., None])
        # daylight spilling across the floor from the doorway
        x0_, y0_ = r.project(-0.85, -eye, zc + R - 0.05)
        x1_, _ = r.project(0.85, -eye, zc + R - 0.05)
        x2_, y2_ = r.project(1.6, -eye, 1.8)
        x3_, _ = r.project(-1.6, -eye, 1.8)
        c.img = rgb.astype(F)
        daylight_beam(c, [(x0_, y0_), (x1_, y0_), (x2_, y2_), (x3_, y2_)], 0.28, blur=U * 4)
        bloom = gblur(dmf, U * 5)
        c.img += (bloom * (1 - dmf) * 0.35)[..., None] * col('#fff6e0')
    else:
        c.img = rgb.astype(F)
    # the slit window and its shaft of light
    wm = gblur(win.astype(F), 1.5)
    over(c.img, wm, col('#ffffff'))
    c.img += (gblur(wm, U * 3) * 0.6 + gblur(wm, U * 10) * 0.3)[..., None] * col('#e8f0ff')
    a_ = r.project(wx * 0.99, 3.0 - eye, wz * 0.99)
    b_ = r.project(wx * 0.99, 1.5 - eye, wz * 0.99)
    f0 = r.project(0.2, -eye, 3.2)
    f1 = r.project(1.0, -eye, 3.9)
    daylight_beam(c, [a_, (a_[0] + U * 2, a_[1]), f1, f0, b_], 0.4, blur=U * 2)
    fa, box = mask_crop(c, ellipses=[(f0[0] - U * 6, f0[1] - U * 3, f1[0] + U * 6, f0[1] + U * 4)], blur=U * 2.5)
    c.img[box[1]:box[3], box[0]:box[2]] += (fa * 0.3)[..., None] * col('#fff4dc')
    vignette(c, 0.45, 2.2)
    grain(c, 0.01, seed)


@scene('tower_in')
def bg_tower_in(c):
    tower_interior(c, 341)


@scene('tower_in_door')
def bg_tower_in_door(c):
    tower_interior(c, 341, door=True)


def plank_tex(u, v, width, seed, base):
    k = np.floor(u / width)
    f = u / width - k
    rnd = hash2(k, k * 0 + 5, seed)
    grain_ = fbm(u * 3 + rnd * 10, v * 0.4, seed + 1, 4)
    seam = smooth(0.0, 0.04, np.minimum(f, 1 - f))
    rgb = base * ((0.75 + 0.35 * rnd) * (0.8 + 0.4 * grain_) * (0.5 + 0.5 * seam))[..., None]
    return rgb, seam


def hut_interior(c, seed, door=False):
    eye = 1.6
    D = 6.0
    hw = 3.0
    ceil = 1.0
    r = Ray(c, 56, 75.0, eye)
    surf = [r.plane('y', -eye), r.plane('y', ceil), r.plane('x', -hw), r.plane('x', hw), r.plane('z', D)]
    t, idx = Ray.combine(surf, 0.0)
    P = r.pos(t)
    v = P[..., 1] + eye
    xs = P[..., 0]
    back = bamboo_cols(xs, v, -hw, 0.13, seed, base=col('#b8924e'), node=0.5)
    sides, _ = plank_tex(v, P[..., 2], 0.22, seed + 1, col('#8a6a44'))
    floor, fseam = plank_tex(P[..., 0], P[..., 2], 0.28, seed + 2, col('#7a5a38'))
    roof = mix(col('#4a3a22'), col('#7a6038'), fbm(P[..., 0] * 10, P[..., 2] * 1.5, seed + 3, 3)[..., None])
    alb = np.where((idx == 4)[..., None], back, np.where(((idx == 2) | (idx == 3))[..., None], sides,
                                                         np.where((idx == 1)[..., None], roof, floor)))
    t = t + (fbm3(P, 5.0, seed + 4, 3) - 0.5) * 0.02
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    lights = [((0.0, 0.5, -0.5), col('#ffe8c0'), 3.2, 3.0), ((2.0, 0.5, 4.0), col('#fff0d0'), 1.2, 1.5)]
    dm = None
    if door:
        dm = (idx == 4) & (np.abs(xs) < 0.62) & (v < 2.05)
        lights.append(((0.0, -0.3, D - 0.3), col('#fff4dc'), 6.0, 1.8))
    rgb = tonemap(alb * light_up(P, N, lights, col('#1c140c')), 1.15)
    c.img = rgb.astype(F)
    rng = np.random.default_rng(seed)
    # light through the gaps between the bamboo poles
    gaps = np.zeros((c.H, c.W), F)
    for k in range(7):
        gx = -hw + 0.13 * int(rng.integers(2, 44))
        if door and abs(gx) < 0.8:
            continue
        x_, y0_ = r.project(gx, ceil - 0.1, D)
        _, y1_ = r.project(gx, -eye + rng.uniform(0.3, 1.0), D)
        x0i = int(x_)
        gaps[int(y0_):int(y1_), x0i:x0i + 3] = rng.uniform(0.6, 1.0)
    gaps = gblur(gaps, 1.0)
    over(c.img, clamp01(gaps * 1.5), col('#fff6d8'))
    c.img += (gblur(gaps, U * 1.5) * 0.4)[..., None] * col('#ffe8b0')
    # sun beams from the right wall onto the floor
    for k in range(3):
        z0 = 1.5 + k * 1.3
        a_ = r.project(hw - 0.01, 0.4, z0)
        b_ = r.project(hw - 0.01, 0.4, z0 + 0.12)
        f0 = r.project(hw - 1.8, -eye, z0 - 0.3)
        f1 = r.project(hw - 1.8, -eye, z0 - 0.15)
        daylight_beam(c, [a_, b_, f1, f0], 0.22, blur=U * 1.2)
    if door:
        dmf = gblur(dm.astype(F), 1.5)
        out = tonemap(outside_view('clearing', seed, 56) * 1.6, 1.0) * 1.05
        c.img = mix(c.img, out, dmf[..., None])
        x0_, y0_ = r.project(-0.62, -eye, D)
        x1_, _ = r.project(0.62, -eye, D)
        x2_, y2_ = r.project(1.2, -eye, 2.2)
        x3_, _ = r.project(-1.2, -eye, 2.2)
        daylight_beam(c, [(x0_, y0_), (x1_, y0_), (x2_, y2_), (x3_, y2_)], 0.3, blur=U * 3)
        c.img += (gblur(dmf, U * 5) * (1 - dmf) * 0.3)[..., None] * col('#fff6e0')
        # door posts
        lay, d = c.layer()
        for sx in (-0.62, 0.62):
            p0 = r.project(sx, -eye, D - 0.02)
            p1 = r.project(sx, 2.15 - eye, D - 0.02)
            w = 0.07 * r.f / D
            d.rectangle((p1[0] - w, p1[1], p1[0] + w, p0[1]), fill=rgb255(col('#5a3e22')) + (255,))
        q0 = r.project(-0.75, 2.2 - eye, D - 0.02)
        q1 = r.project(0.75, 2.05 - eye, D - 0.02)
        d.rectangle((q0[0], q0[1], q1[0], q1[1]), fill=rgb255(col('#6a4a2a')) + (255,))
        c.comp(lay)
    else:
        # shelves with old jars on the back wall
        lay, d = c.layer()
        for (x0s, x1s) in ((-2.6, -0.8), (0.8, 2.6)):
            for hs in (1.05, 1.75):
                a_ = r.project(x0s, hs - eye, D - 0.02)
                b_ = r.project(x1s, hs - eye, D - 0.02)
                th = 0.05 * r.f / D
                d.rectangle((a_[0], a_[1], b_[0], a_[1] + th), fill=rgb255(col('#6a4a2a')) + (255,))
                d.rectangle((a_[0], a_[1] + th, b_[0], a_[1] + th * 2.2), fill=rgb255(col('#2a1a0e')) + (120,))
                for b in (x0s + 0.1, x1s - 0.1):
                    p0 = r.project(b, hs - eye, D - 0.02)
                    p1 = r.project(b, hs - 0.25 - eye, D - 0.02)
                    d.polygon([p0, (p0[0] + th, p0[1]), (p1[0] + th, p1[1])], fill=rgb255(col('#5a3e22')) + (255,))
                xj = x0s + 0.15
                while xj < x1s - 0.2:
                    jw = rng.uniform(0.12, 0.22)
                    jh = rng.uniform(0.18, 0.4)
                    bx, by = r.project(xj + jw / 2, hs - eye, D - 0.15)
                    W_ = jw * r.f / D
                    H_ = jh * r.f / D
                    cj = [col('#a0583a'), col('#8a6a3a'), col('#5a4a3a'), col('#c08a5a'), col('#3a4a3a')][int(rng.integers(0, 5))]
                    cj = cj * rng.uniform(0.8, 1.1)
                    body = (bx - W_ / 2, by - H_ * 0.85, bx + W_ / 2, by)
                    d.ellipse(body, fill=rgb255(cj) + (255,))
                    d.rectangle((bx - W_ * 0.22, by - H_, bx + W_ * 0.22, by - H_ * 0.7), fill=rgb255(cj * 0.9) + (255,))
                    d.rectangle((bx - W_ * 0.28, by - H_ * 1.04, bx + W_ * 0.28, by - H_ * 0.96), fill=rgb255(cj * 1.1) + (255,))
                    d.ellipse((bx - W_ * 0.38, by - H_ * 0.72, bx - W_ * 0.12, by - H_ * 0.35), fill=rgb255(np.clip(cj * 1.5, 0, 1)) + (170,))
                    xj += jw + rng.uniform(0.04, 0.12)
        c.comp(lay)
    vignette(c, 0.45, 2.2)
    grain(c, 0.01, seed)


@scene('hut_in')
def bg_hut_in(c):
    hut_interior(c, 351)


@scene('hut_in_door')
def bg_hut_in_door(c):
    hut_interior(c, 351, door=True)


# --------------------------------------------------------------------------------------------
# Hangar (outside and inside), palm top
# --------------------------------------------------------------------------------------------

def corrugated_rgb(u, v, period, seed, base=col('#8a8e8a'), rust=0.6, light_dir=1.0, panel_h=None):
    """Corrugated iron: vertical ridges (u across, v down/up, same units), rust streaks and stains."""
    ph = u / period * 2 * math.pi
    ridge = np.sin(ph)
    shade = 0.78 + 0.22 * ridge * light_dir
    streak = fbm(u * 3.0 / period, v * 0.15 / period, seed, 4)
    blot = fbm(u * 0.3 / period, v * 0.3 / period, seed + 1, 4)
    r_amt = clamp01((blot - 0.45) * 2.5 * rust + (streak - 0.5) * 1.2 * rust)
    rust_col = mix(col('#6a3a1c'), col('#b0602a'), streak[..., None])
    rgb = mix(base, rust_col, r_amt[..., None]) * shade[..., None]
    if panel_h:
        seam = smooth(0.0, 0.03, np.abs((v / panel_h) % 1.0 - 0.5) - 0.465)
        rgb = rgb * 0.8 * (1 - 0.35 * seam)[..., None]
    return rgb, ridge


def concrete_rgb(u, v, seed, base=col('#9a968c')):
    n = fbm(u * 0.8, v * 0.8, seed, 5)
    fine = fbm(u * 6, v * 6, seed + 1, 3)
    cr = fbm(u * 0.4, v * 0.4, seed + 2, 4)
    crack = 1 - smooth(0.0, 0.012, np.abs(cr - 0.5))
    rgb = base * (0.75 + 0.4 * n + (fine - 0.5) * 0.2)[..., None] * (1 - 0.5 * crack)[..., None]
    return rgb


def weeds(c, y0_v, y1_v, seed, n=400, x_range=(0, 240), colr=col('#5a8a30'), hmax=12):
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    items = sorted((rng.uniform(y0_v, y1_v) * U, rng.uniform(*x_range) * U) for _ in range(n))
    for y, x in items:
        sc = 0.4 + 0.6 * (y / U - y0_v) / max(1, (y1_v - y0_v))
        h = U * hmax * sc * rng.uniform(0.4, 1.1)
        if rng.random() < 0.85:
            draw_blade(d, x, y, h, rng.uniform(-0.5, 0.5) * h, U * 0.45 * sc, np.clip(colr * rng.uniform(0.5, 1.2), 0, 1))
        else:
            draw_broadleaf_bush(d, x, y, h * 0.8, np.clip(col('#3a7a2a') * rng.uniform(0.6, 1.1), 0, 1),
                                int(rng.integers(0, 1 << 30)), n=5)
    c.comp(lay)


@scene('hangar_out')
def bg_hangar_out(c):
    seed = 361
    cam = Cam(c, HY)
    day_sky(c, seed, sun=(40, -10), n=4)
    tree_line(c, cam, seed + 3, 60, n=10, haze_amt=0.25, height=(14, 22))
    meadow(c, cam, seed, cam.hy, flowers=False, grass_col=col('#5a8a38'))
    # concrete apron
    X, Z, y0 = cam.ground()
    apron = (1 - smooth(16, 18, np.abs(X))) * (Z < 40)
    over(c.img[y0:], apron * 0.9, concrete_rgb(X, Z, seed))
    weed_m = clamp01((fbm(X * 0.6, Z * 0.6, seed + 4, 3) - 0.55) * 4) * apron
    over(c.img[y0:], weed_m * 0.8, col('#4a7a2a') * (0.7 + 0.5 * fbm(X * 4, Z * 4, seed + 5, 2))[..., None])
    # facade
    x0, x1 = 14 * U, 226 * U
    yb = 112 * U
    xx = np.arange(int(x0), int(x1), dtype=F)[None, :]
    u = (xx - x0) / U
    roof = (36 - 16 * np.sqrt(clamp01(1 - ((u - 106) / 106) ** 2))) * U
    yy = np.arange(0, int(yb), dtype=F)[:, None]
    m = (yy >= roof).astype(F)
    rgb, ridge = corrugated_rgb(np.broadcast_to(u, m.shape), np.broadcast_to(yy / U, m.shape), 2.2, seed,
                                base=col('#8c8c84'), rust=0.9, panel_h=24)
    rgb = rgb * (0.85 + 0.15 * (u / 212))[..., None]
    over(c.img[:int(yb), int(x0):int(x1)], gblur(m, 1.0), rgb)
    # roof edge trim
    lay, d = c.layer()
    pts = [(x0 + k * (x1 - x0) / 60, float(36 - 16 * math.sqrt(max(0.0, 1 - ((k * 212 / 60 - 106) / 106) ** 2))) * U) for k in range(61)]
    d.line(pts, fill=rgb255(col('#4a3a30')) + (255,), width=int(U * 1.6))
    d.line([(p[0], p[1] - U * 0.5) for p in pts], fill=rgb255(col('#9a7a5a')) + (255,), width=int(U * 0.5))
    # two great sliding doors
    for (dx0, dx1) in ((50, 120), (120, 190)):
        d.rectangle((dx0 * U, 40 * U, dx1 * U, yb), fill=(0, 0, 0, 0))
    c.comp(lay)
    for k, (dx0, dx1) in enumerate(((50.5, 119.5), (120.5, 189.5))):
        X0, X1, Y0, Y1 = int(dx0 * U), int(dx1 * U), int(40 * U), int(yb)
        uu = (np.arange(X0, X1, dtype=F)[None, :]) / U
        vv = np.arange(Y0, Y1, dtype=F)[:, None] / U
        drgb, _ = corrugated_rgb(np.broadcast_to(uu, (Y1 - Y0, X1 - X0)), np.broadcast_to(vv, (Y1 - Y0, X1 - X0)),
                                 1.6, seed + 10 + k, base=col('#7a8478'), rust=1.0, panel_h=18)
        c.img[Y0:Y1, X0:X1] = drgb * 0.92
    lay, d = c.layer()
    steel = col('#4a4440')
    d.rectangle((48 * U, 37 * U, 192 * U, 40 * U), fill=rgb255(steel) + (255,))        # rail
    d.rectangle((48 * U, 37 * U, 192 * U, 37.8 * U), fill=rgb255(col('#7a6a5a')) + (255,))
    for (dx0, dx1) in ((50, 120), (120, 190)):
        for (a0, a1) in ((dx0, dx0 + 2), (dx1 - 2, dx1)):
            d.rectangle((a0 * U, 40 * U, a1 * U, yb), fill=rgb255(steel) + (255,))
        for yv in (40, 75, 110):
            d.rectangle((dx0 * U, yv * U, dx1 * U, (yv + 2) * U), fill=rgb255(steel) + (255,))
        d.line([(dx0 * U + U, 42 * U), (dx1 * U - U, 75 * U)], fill=rgb255(steel) + (255,), width=int(U * 1.4))
        d.line([(dx0 * U + U, 77 * U), (dx1 * U - U, 110 * U)], fill=rgb255(steel) + (255,), width=int(U * 1.4))
        for xw in (dx0 + 8, dx1 - 8):
            d.ellipse((xw * U - U * 1.6, 36.5 * U, xw * U + U * 1.6, 39.7 * U), fill=rgb255(col('#2a2622')) + (255,))
    d.rectangle((117 * U, 85 * U, 119 * U, 92 * U), fill=rgb255(col('#2a2622')) + (255,))
    d.rectangle((121 * U, 85 * U, 123 * U, 92 * U), fill=rgb255(col('#2a2622')) + (255,))
    # rust drips from the rail
    rng = np.random.default_rng(seed)
    for k in range(30):
        xd_ = rng.uniform(50, 190) * U
        d.line([(xd_, 40 * U), (xd_ + rng.uniform(-3, 3), (40 + rng.uniform(5, 30)) * U)], fill=(120, 60, 25, 110), width=int(U * 0.6))
    c.comp(lay)
    contact_shadow(c, 120, 113, 108, 3, 0.45)
    # vines climbing the walls and roof edge
    lay, d = c.layer()
    for k in range(10):
        xv = rng.choice([rng.uniform(15, 48), rng.uniform(192, 225)]) * U
        hanging_vine(d, xv, (30 + rng.uniform(0, 10)) * U, U * rng.uniform(30, 80), col('#3a4a1e'), U * 0.6, rng,
                     leaf_col=col('#3f7f2a'))
    for k in range(5):
        xv = rng.uniform(55, 185) * U
        hanging_vine(d, xv, 37 * U, U * rng.uniform(8, 22), col('#3a4a1e'), U * 0.5, rng, leaf_col=col('#4a8a2a'))
    for k in range(18):
        x_ = rng.choice([rng.uniform(5, 50), rng.uniform(190, 235)]) * U
        draw_broadleaf_bush(d, x_, 114 * U, U * rng.uniform(8, 16), col('#2f7a30') * rng.uniform(0.6, 1.0), seed + k, n=7)
    c.comp(lay)
    weeds(c, 108, 136, seed + 7, n=500, hmax=10)
    side_ferns(c, seed + 9)
    vignette(c, 0.3, 2.4)


def oblique_wall_scene(c, seed, kind):
    """Ray-cast hangar walls in daylight. kind: 'side' (one long wall receding to the right) or
    'corner' (an inside corner of the foundation with open ground in front)."""
    eye = 1.7
    hy_v = 62
    r = Ray(c, hy_v, 75.0, eye)
    tmp = Canvas(240, 136)
    cam = Cam(tmp, hy_v)
    day_sky(tmp, seed, sun=(40, -10), n=4)
    tree_line(tmp, cam, seed + 3, 50, n=10, haze_amt=0.25, height=(14, 22))
    meadow(tmp, cam, seed, cam.hy, flowers=False, grass_col=col('#5a8a38'))
    c.img = tmp.img
    if kind == 'side':
        # wall plane: z = 5 + 0.55 x  (recedes to the right)
        a, z0 = 0.55, 5.0
        t_w = z0 / np.maximum(1 - a * r.dx, 1e-3)
        t_w = np.where(1 - a * r.dx > 1e-3, t_w, INF)
        P = r.pos(t_w)
        h = P[..., 1] + eye
        wall = (h > 0) & (h < 6.5) & (t_w < INF)
        along = P[..., 0] * math.sqrt(1 + a * a)
        mats = [(wall, along, h, t_w)]
        found = None
    else:
        t_b = r.plane('z', 7.5)
        t_r = r.plane('x', 2.4)
        Pb = r.pos(t_b)
        Pr = r.pos(t_r)
        hb = Pb[..., 1] + eye
        hr = Pr[..., 1] + eye
        wb = (hb > 0) & (hb < 6.5) & (Pb[..., 0] < 2.4) & (Pb[..., 0] > -3.0)
        wr = (hr > 0) & (hr < 6.5) & (Pr[..., 2] < 7.5) & (Pr[..., 2] > 2.0) & ~wb
        mats = [(wb, Pb[..., 0], hb, t_b), (wr, -Pr[..., 2], hr, t_r)]
    for (m, uu, hh, tt) in mats:
        rgb, ridge = corrugated_rgb(uu, hh, 0.14, seed, base=col('#8a8a82'), rust=1.0, panel_h=1.6)
        found = hh < 0.7
        conc = concrete_rgb(uu * 3, hh * 3, seed + 2, col('#a09a8e'))
        rgb = np.where(found[..., None], conc, rgb)
        # shading: lit by the sun from the left, darker low down (grime) and further away
        rgb = rgb * (0.85 - 0.25 * smooth(1.5, 0.0, hh) * (1 - found))[..., None]
        rgb = mix(rgb, col('#b8c8d0'), smooth(10, 60, tt)[..., None] * 0.4)
        mm = gblur(m.astype(F), 1.0)
        over(c.img, mm, rgb)
        # roof edge line
        edge = (np.abs(hh - 6.5) < 0.12) & (np.abs(uu) < 1e5)
        over(c.img, gblur((m | edge).astype(F) * edge, 1.0) * 0.9, col('#4a3a30'))
        # foundation top edge highlight
        fe = (np.abs(hh - 0.7) < 0.04) & m
        over(c.img, gblur(fe.astype(F), 1.0) * 0.7, col('#d8d2c4'))
    if kind == 'corner':
        X, Z, y0 = Cam(c, hy_v, h=eye).ground()
        gm = 1 - smooth(3.0, 4.5, np.sqrt((X - 0.6) ** 2 + ((Z - 4.5) * 0.9) ** 2))
        gnd = mix(col('#5a4632'), col('#8a7458'), fbm(X * 2, Z * 2, seed + 6, 4)[..., None])
        pebbles = clamp01((fbm(X * 9, Z * 9, seed + 7, 2) - 0.6) * 5)
        gnd = gnd * (1 + pebbles * 0.4)[..., None]
        over(c.img[y0:], gm * (Z < 7.5) * 0.95, gnd)
        weeds(c, 96, 136, seed + 7, n=260, x_range=(0, 60), hmax=12)
        weeds(c, 96, 136, seed + 8, n=200, x_range=(200, 240), hmax=12)
        weeds(c, 92, 100, seed + 11, n=80, x_range=(60, 200), hmax=5)
    else:
        weeds(c, 70, 136, seed + 7, n=700, hmax=14)
    rng = np.random.default_rng(seed)
    lay, d = c.layer()
    for k in range(8):
        xv = rng.uniform(20, 230) * U
        hanging_vine(d, xv, rng.uniform(0, 20) * U, U * rng.uniform(15, 50), col('#3a4a1e'), U * 0.6, rng, leaf_col=col('#3f7f2a'))
    c.comp(lay)
    side_ferns(c, seed + 9)
    vignette(c, 0.3, 2.4)


@scene('hangar_side')
def bg_hangar_side(c):
    oblique_wall_scene(c, 371, 'side')


@scene('hangar_corner')
def bg_hangar_corner(c):
    oblique_wall_scene(c, 381, 'corner')


def hangar_interior(c, seed, mode='plain'):
    eye = 1.7
    D = 24.0
    hw = 12.0
    ceil = 7.0
    r = Ray(c, 86, 80.0, eye)
    surf = [r.plane('y', -eye), r.plane('y', ceil), r.plane('x', -hw), r.plane('x', hw), r.plane('z', D)]
    t, idx = Ray.combine(surf, 0.0)
    P = r.pos(t)
    h = P[..., 1] + eye
    if mode == 'ramp':
        # rectangular opening in the floor with a ramp descending away from us
        z0r, z1r, xr = 6.0, 16.0, 2.6
        fl = (idx == 0) & (np.abs(P[..., 0]) < xr) & (P[..., 2] > z0r) & (P[..., 2] < z1r)
        s_ = 0.15
        with np.errstate(divide='ignore', invalid='ignore'):
            t_ramp = (-eye + z0r * s_) / (r.dy + s_)
        t_side = np.where(r.dx > 0, r.plane('x', xr), r.plane('x', -xr))
        t_end = r.plane('z', z1r)
        t_in = np.minimum(np.where(t_ramp > 0, t_ramp, INF), np.minimum(t_side, t_end))
        t = np.where(fl, t_in, t)
        idx = np.where(fl, np.where(t_in == t_ramp, 10, np.where(t_in == t_end, 11, 12)), idx)
        P = r.pos(t)
        h = P[..., 1] + eye
    # materials
    wall_u = np.where(idx == 4, P[..., 0], P[..., 2])
    walls, ridge = corrugated_rgb(wall_u, h, 0.15, seed, base=col('#7a7c76'), rust=0.8, panel_h=1.8)
    floor = concrete_rgb(P[..., 0], P[..., 2], seed + 1, col('#8a867c'))
    oil = clamp01((fbm(P[..., 0] * 0.3, P[..., 2] * 0.3, seed + 2, 4) - 0.6) * 5)
    floor = floor * (1 - 0.6 * oil)[..., None] + (oil * 0.04)[..., None] * col('#6080a0')
    roofc, _ = corrugated_rgb(P[..., 0], P[..., 2], 0.3, seed + 3, base=col('#5a5a56'), rust=0.6)
    alb = np.where(((idx == 2) | (idx == 3) | (idx == 4))[..., None], walls,
                   np.where((idx == 1)[..., None], roofc, floor))
    if mode == 'ramp':
        ramp_c = concrete_rgb(P[..., 0] * 2, P[..., 2], seed + 4, col('#7a766c'))
        alb = np.where((idx >= 10)[..., None], ramp_c, alb)
    # bump: corrugations on walls
    disp = np.where((idx == 2) | (idx == 3) | (idx == 4), ridge * 0.03, 0)
    t2 = t - disp * np.abs(r.dx * 0 + 1)
    P2 = r.pos(t2)
    N = normals(P2, r.dx, r.dy)
    rng = np.random.default_rng(seed)
    holes = [(rng.uniform(-9, 9), rng.uniform(6, 20)) for _ in range(4)]
    lights = [((hx, ceil - 0.3, hz), col('#fff6e4'), 6.0, 3.0) for hx, hz in holes]
    lights.append(((0, 2.5, 4), col('#a8b8d0'), 1.5, 8.0))
    amb = col('#14161a')
    door_m = None
    if mode in ('doors', 'open'):
        lights.append(((0, 1.0, D - 1.0), col('#fff4e0'), 6.0 if mode == 'open' else 1.5, 6.0))
    rgb = tonemap(alb * light_up(P2, N, lights, amb), 1.2)
    if mode == 'ramp':
        depth = clamp01((-(P[..., 1] + eye)) / 1.6)
        rgb = rgb * (1 - 0.85 * depth * (idx >= 10))[..., None]
        rgb = np.where((idx == 11)[..., None], rgb * 0.05, rgb)
        rgb = np.where((idx == 12)[..., None], rgb * 0.6, rgb)
    c.img = rgb.astype(F)
    # doors in the back wall
    if mode in ('doors', 'open'):
        dx0, dx1, dh = -9.0, 9.0, 7.0
        a_ = r.project(dx0, dh - eye, D - 0.05)
        b_ = r.project(dx1, -eye, D - 0.05)
        X0, Y0, X1, Y1 = int(a_[0]), int(a_[1]), int(b_[0]), int(b_[1])
        if mode == 'open':
            out = tonemap(outside_view('runway', seed, 86) * 1.5, 1.0) * 1.05
            om = np.zeros((c.H, c.W), F)
            om[Y0:Y1, X0:X1] = 1
            om = gblur(om, 1.5)
            c.img = mix(c.img, out, om[..., None])
            # light pouring in across the floor
            p0 = r.project(dx0, -eye, D)
            p1 = r.project(dx1, -eye, D)
            p2 = r.project(dx1 + 4, -eye, 3.0)
            p3 = r.project(dx0 - 4, -eye, 3.0)
            daylight_beam(c, [p0, p1, p2, p3], 0.3, blur=U * 4)
            c.img += (gblur(om, U * 6) * (1 - om) * 0.5)[..., None] * col('#fff6e0')
            # door leaves pushed aside, seen edge-on against the side walls
            lay, d = c.layer()
            for sx in (-1, 1):
                q0 = r.project(sx * 9.3, dh - eye, D - 0.3)
                q1 = r.project(sx * 11.6, -eye, D - 0.3)
                d.rectangle((min(q0[0], q1[0]), q0[1], max(q0[0], q1[0]), q1[1]), fill=rgb255(col('#3a3e38')) + (255,))
            c.comp(lay)
        else:
            uu = np.arange(X0, X1, dtype=F)[None, :]
            vv = np.arange(Y0, Y1, dtype=F)[:, None]
            drgb, _ = corrugated_rgb(np.broadcast_to(uu / U, (Y1 - Y0, X1 - X0)), np.broadcast_to(vv / U, (Y1 - Y0, X1 - X0)),
                                     1.0, seed + 5, base=col('#5a6258'), rust=1.0, panel_h=10)
            yl = (vv - Y0) / (Y1 - Y0)
            drgb = drgb * (0.35 + 0.25 * yl)[..., None]
            c.img[Y0:Y1, X0:X1] = drgb
            lay, d = c.layer()
            steel = col('#26241f')
            midx = (X0 + X1) / 2
            for xs_ in (X0, midx - U * 0.6, midx + U * 0.6, X1):
                d.rectangle((xs_ - U * 0.8, Y0, xs_ + U * 0.8, Y1), fill=rgb255(steel) + (255,))
            for fy in (0.0, 0.5, 1.0):
                yy_ = Y0 + (Y1 - Y0) * fy
                d.rectangle((X0, yy_ - U * 0.8, X1, yy_ + U * 0.8), fill=rgb255(steel) + (255,))
            for (a0, a1) in ((X0, midx), (midx, X1)):
                d.line([(a0, Y0), (a1, (Y0 + Y1) / 2)], fill=rgb255(steel) + (255,), width=int(U * 1.0))
                d.line([(a0, (Y0 + Y1) / 2), (a1, Y1)], fill=rgb255(steel) + (255,), width=int(U * 1.0))
            c.comp(lay)
            # daylight leaking through the central seam and under the doors
            lk = np.zeros((c.H, c.W), F)
            lk[Y0:Y1, int(midx - U * 0.25):int(midx + U * 0.25)] = 1
            lk[Y1 - int(U * 0.6):Y1, X0:X1] = 0.8
            over(c.img, gblur(lk, 1.0), col('#fff6e0'))
            c.img += (gblur(lk, U * 2) * 0.6 + gblur(lk, U * 8) * 0.3)[..., None] * col('#ffe8c0')
            p0 = r.project(-0.2, -eye, D)
            p1 = r.project(0.2, -eye, D)
            p2 = r.project(1.5, -eye, 6)
            p3 = r.project(-1.5, -eye, 6)
            daylight_beam(c, [p0, p1, p2, p3], 0.18, blur=U * 2)
    # roof trusses
    lay, d = c.layer()
    steel = col('#2a2824')
    for zt in np.arange(3.0, D, 3.5):
        a_ = r.project(-hw, ceil - 0.2, zt)
        b_ = r.project(hw, ceil - 0.2, zt)
        lo_l = r.project(-hw, ceil - 1.6, zt)
        lo_r = r.project(hw, ceil - 1.6, zt)
        w = max(2, int(0.18 * r.f / zt))
        d.line([a_, b_], fill=rgb255(steel) + (255,), width=w)
        d.line([lo_l, lo_r], fill=rgb255(steel) + (255,), width=w)
        for k in range(13):
            xk = -hw + k * 2 * hw / 12
            p_top = r.project(xk, ceil - 0.2, zt)
            p_bot = r.project(xk + (hw / 12 if k % 2 == 0 else -hw / 12), ceil - 1.6, zt)
            d.line([p_top, p_bot], fill=rgb255(steel) + (255,), width=max(1, w // 2))
        # columns down the walls
        for sx in (-1, 1):
            c0 = r.project(sx * (hw - 0.2), ceil, zt)
            c1 = r.project(sx * (hw - 0.2), -eye, zt)
            d.line([c0, c1], fill=rgb255(steel) + (255,), width=w)
    c.comp(lay)
    # holes in the roof with shafts of daylight
    for hx, hz in holes:
        a_ = r.project(hx - 0.5, ceil, hz)
        b_ = r.project(hx + 0.5, ceil, hz)
        f0 = r.project(hx + 1.0, -eye, hz - 1.5)
        f1 = r.project(hx + 2.0, -eye, hz - 1.5)
        daylight_beam(c, [a_, b_, f1, f0], 0.18, blur=U * 2.5)
        hm, box = mask_crop(c, ellipses=[(a_[0], a_[1] - U * 0.6, b_[0], a_[1] + U * 0.6)], blur=1.5)
        if hm is not None:
            over(c.img, hm, col('#f4f8ff'), box)
        fa, box = mask_crop(c, ellipses=[(f0[0] - U * 3, f0[1] - U * 1.5, f1[0] + U * 3, f0[1] + U * 1.5)], blur=U * 1.5)
        if fa is not None:
            c.img[box[1]:box[3], box[0]:box[2]] += (fa * 0.3)[..., None] * col('#fff4dc')
    if mode == 'ramp':
        # hazard edge along the opening
        lay, d = c.layer()
        for (za, zb) in ((6.0, 6.0),):
            pa = r.project(-2.6, -eye, za)
            pb = r.project(2.6, -eye, za)
            d.line([pa, pb], fill=rgb255(col('#c8b040')) + (255,), width=int(U * 0.8))
        for sx in (-2.6, 2.6):
            pa = r.project(sx, -eye, 6.0)
            pb = r.project(sx, -eye, 16.0)
            d.line([pa, pb], fill=rgb255(col('#a89038')) + (255,), width=int(U * 0.5))
        c.comp(lay)
    vignette(c, 0.45, 2.2)
    grain(c, 0.012, seed)


@scene('hangar_in')
def bg_hangar_in(c):
    hangar_interior(c, 391)


@scene('hangar_in_doors')
def bg_hangar_in_doors(c):
    hangar_interior(c, 401, 'doors')


@scene('hangar_in_open')
def bg_hangar_in_open(c):
    hangar_interior(c, 401, 'open')


@scene('hangar_in_ramp')
def bg_hangar_in_ramp(c):
    hangar_interior(c, 411, 'ramp')


@scene('palm_top')
def bg_palm_top(c):
    seed = 421
    hy_v = 34
    cam = Cam(c, hy_v, h=16.0, fov=80)
    sky(c, hy_v + 1, sun=(60, -10), sun_r=50)
    cloud_bank(c, hy_v - 3, seed, n=5, size=(10, 22))

    def dist(X, Z):
        return Z - (40 + 6 * np.sin(X * 0.03) + 0.04 * X)

    beach_scene(c, cam, seed, None, dist, sun_x=c.W * 0.25, waves=((2.0, 4.0), (9.0, 5.0), (20.0, 6.0)))
    # other palm crowns below and the jungle edge at the bottom left
    lay, d = c.layer()
    rng = np.random.default_rng(seed)
    for k in range(5):
        x = rng.uniform(-0.1, 0.35) * c.W
        y = c.H * rng.uniform(0.85, 1.05)
        draw_palm(d, x, y + U * 40, U * 50, rng.uniform(-5, 5) * U, seed + k, crown=0.9)
    c.comp(lay)
    # fronds of our palm framing the view (close, slightly out of focus)
    lay, d = c.layer()
    for k in range(7):
        side = k % 3
        if side == 0:
            x, y, a = -U * 4, rng.uniform(-0.1, 0.15) * c.H, rng.uniform(-0.2, 0.6)
        elif side == 1:
            x, y, a = c.W + U * 4, rng.uniform(-0.1, 0.2) * c.H, math.pi + rng.uniform(-0.6, 0.2)
        else:
            x, y, a = rng.choice([0.15, 0.85]) * c.W, -U * 8, math.pi / 2 + rng.uniform(-0.6, 0.6)
        draw_frond(d, x, y, a, U * rng.uniform(70, 95), np.clip(col('#3a8a30') * rng.uniform(0.7, 1.05), 0, 1),
                   droop=0.5, leaflet=0.3, rng=rng, width=U * 2.0)
    c.comp(lay, blur=3)
    vignette(c, 0.3, 2.4)


# --------------------------------------------------------------------------------------------
# Full-screen pictures (240 x 224 virtual)
# --------------------------------------------------------------------------------------------

def stars(c, y1_v, seed, n=500, fade=True):
    rng = np.random.default_rng(seed)
    lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(n):
        x = rng.uniform(0, c.W)
        y = rng.uniform(0, y1_v * U) * rng.random() ** 0.3
        r_ = rng.uniform(0.8, 2.6) * (2.0 if rng.random() < 0.03 else 1.0)
        a = int(255 * rng.uniform(0.3, 1.0) * ((1 - y / (y1_v * U)) if fade else 1))
        d.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 250, 235, max(0, a)))
    c.comp(lay.filter(ImageFilter.GaussianBlur(0.6)))


def sparkle(c, x, y, size, color=col('#ffffff'), strength=1.0):
    """A four-pointed star glint (working px)."""
    lay = Image.new('L', (c.W, c.H), 0)
    d = ImageDraw.Draw(lay)
    for ang, ln in ((0, 1.0), (math.pi / 2, 1.0), (math.pi / 4, 0.45), (3 * math.pi / 4, 0.45)):
        dx, dy = math.cos(ang) * size * ln, math.sin(ang) * size * ln
        w = size * 0.05
        nx, ny = -math.sin(ang) * w, math.cos(ang) * w
        d.polygon([(x - dx, y - dy), (x + nx, y + ny), (x + dx, y + dy), (x - nx, y - ny)], fill=255)
    a = m2a(lay, blur=1.5)
    c.img += (a * strength)[..., None] * color
    glow(c, x, y, size * 0.25, color, strength * 0.8)


@scene('title', full=True)
def bg_title(c):
    seed = 501
    hy_v = 150
    sky(c, hy_v + 1, stops=[(0.0, col('#0b1030')), (0.35, col('#1f2a5a')), (0.62, col('#5a3a6a')),
                            (0.82, col('#c0584a')), (0.94, col('#f0904a')), (1.0, col('#ffc070'))])
    stars(c, 90, seed, n=420)
    # moon with a halo
    mx, my = 196 * U, 72 * U
    glow(c, mx, my, U * 16, col('#c8d0ff'), 0.35, power=1.6)
    a, box = mask_crop(c, ellipses=[(mx - U * 8, my - U * 8, mx + U * 8, my + U * 8)], blur=1.5)
    tex = snoise(a.shape[0], a.shape[1], U * 2.5, seed, 4)
    over(c.img, a, col('#f4f0dc') * (0.82 + 0.3 * tex)[..., None], box)
    # low clouds lit from below by the sunset
    for k, (x, y, w) in enumerate(((40, 128, 60), (110, 136, 46), (170, 124, 55), (225, 138, 40))):
        cloud(c, x, y, w, w * 0.22, seed + k, lit=col('#ff9a6a'), shade=col('#3a2a4a'), alpha=0.85, light=(0.0, 1.0))
    # the island: volcano with red glow and smoke, dark jungle slopes
    smoke_plume(c, 92, 84, seed + 3, 20, 7, drift=2.2, dark=col('#2a2030'), lit=col('#8a5a5a'), alpha=0.85)
    volcano_cone(c, 92, hy_v + 2, 82, 120, 10, seed, haze=col('#2a2440'), haze_amt=0.55, green=True, glow_top=True)
    glow(c, 92 * U, 83 * U, U * 14, col('#ff4a1a'), 0.6)
    lay, d = c.layer()
    rng = np.random.default_rng(seed)
    foliage_mass(c, d, lambda x: (hy_v - 8 - 6 * math.sin(x / c.W * 5 + 1) - 4 * math.exp(-((x / U - 92) / 40) ** 2)) * U,
                 -20, c.W + 20, (hy_v + 1) * U, seed + 4, [col('#1a2a2a'), col('#223030'), col('#1a2626')], leaf=U * 1.6,
                 density=0.9, base=col('#101a1c'))
    for k in range(10):
        draw_palm(d, rng.uniform(0, c.W), (hy_v - 3) * U, U * rng.uniform(16, 24), rng.uniform(-3, 3) * U, seed + 10 + k,
                  frond_col=col('#1a2a28'), trunk_col=col('#20262a'))
    c.comp(lay)
    # sea with reflections of the sunset and the moon
    cam = Cam(c, hy_v, h=6.0)
    X, Z, y0 = cam.ground()
    n = fbm(X * 0.08, Z * 0.5, seed + 5, 5)
    sea = mix(col('#0e1a3a'), col('#2a3a6a'), n[..., None])
    sea = mix(sea, col('#f08a4a'), (smooth(400, 40, Z) * 0 + smooth(30, 600, Z) * 0.45 * clamp01((n - 0.4) * 2))[..., None])
    xs = (c.xs - mx) / U
    path = np.exp(-(xs / (5 + 0.004 * Z)) ** 2) * clamp01((fbm(X * 0.3, Z * 1.5, seed + 6, 3) - 0.45) * 4)
    sea = sea + path[..., None] * col('#e8e8ff') * 0.8
    c.img[y0:] = sea
    # beach with the wreck and palms in the foreground
    lay, d = c.layer()
    beach = [(0, 196 * U)]
    for k in range(41):
        x = k / 40 * c.W
        beach.append((x, (194 - 6 * math.sin(k / 40 * math.pi) + 1.5 * math.sin(k * 0.7)) * U))
    beach += [(c.W, c.H), (0, c.H)]
    d.polygon(beach, fill=rgb255(col('#3a2e34')) + (255,))
    c.comp(lay)
    a, box = mask_crop(c, polys=[beach], pad=2)
    tex = snoise(a.shape[0], a.shape[1], U * 3, seed + 7, 4)
    yy = np.linspace(0, 1, a.shape[0], dtype=F)[:, None]
    over(c.img, a, mix(col('#5a4048'), col('#2a1e24'), yy)[..., None][..., 0] * (0.8 + 0.4 * tex)[..., None]
         if False else mix(col('#6a4a4a'), col('#24181e'), yy[..., None]) * (0.8 + 0.4 * tex)[..., None], box)
    foam_y = [(x, y - U * 0.8) for x, y in beach[1:42]]
    lay, d = c.layer(shadows=False)
    d.line(foam_y, fill=(240, 200, 180, 160), width=int(U * 0.8))
    c.comp(lay, blur=2)
    # the wreck, silhouetted on the beach
    lay, d = c.layer(shadows=False)
    wx, wy = 52 * U, 200 * U
    hull = [(wx - U * 26, wy - U * 6), (wx + U * 20, wy - U * 10), (wx + U * 26, wy - U * 14), (wx + U * 22, wy - U * 3),
            (wx + U * 8, wy + U * 2), (wx - U * 18, wy + U * 2)]
    d.polygon(hull, fill=rgb255(col('#140e12')) + (255,))
    d.line([(wx - U * 2, wy - U * 7), (wx + U * 30, wy - U * 34)], fill=rgb255(col('#140e12')) + (255,), width=int(U * 1.2))
    d.polygon([(wx + U * 26, wy - U * 30), (wx + U * 8, wy - U * 9), (wx + U * 22, wy - U * 12), (wx + U * 18, wy - U * 18)],
              fill=rgb255(col('#2a1e22')) + (255,))
    d.line([(wx + U * 30, wy - U * 34), (wx + U * 26, wy - U * 13)], fill=(20, 14, 18, 255), width=int(U * 0.3))
    c.comp(lay)
    lay, d = c.layer()
    draw_palm(d, 222 * U, 214 * U, U * 120, -U * 26, seed + 30, frond_col=col('#141c1c'), trunk_col=col('#1c1a1e'))
    draw_palm(d, 244 * U, 224 * U, U * 95, -U * 10, seed + 31, frond_col=col('#101818'), trunk_col=col('#18161a'))
    draw_palm(d, -6 * U, 226 * U, U * 70, U * 14, seed + 32, frond_col=col('#121a1a'), trunk_col=col('#18161a'))
    c.comp(lay)
    # rim light on the palm silhouettes from the sunset glow
    # the faint sparkle of the diamond on the volcano's flank
    sparkle(c, 104 * U, 118 * U, U * 7, col('#d8f0ff'), 0.9)
    vignette(c, 0.4, 2.2)
    grade(c, sat=1.05, contrast=1.05)


@scene('intro', full=True)
def bg_intro(c):
    seed = 511
    rng = np.random.default_rng(seed)
    # desk wood around the page
    wood = fbm(c.xs / U * 0.02 + c.ys * 0 , c.ys / U * 0.4 + c.xs * 0, seed, 5)
    c.img[:] = mix(col('#2a1a10'), col('#5a3a22'), wood[..., None])
    # parchment page
    px0, py0, px1, py1 = 14 * U, 10 * U, 226 * U, 214 * U
    pts = []
    for k in range(80):
        t = k / 80
        pts.append((px0 + (px1 - px0) * t, py0 + rng.uniform(-1, 1) * U * 0.8))
    for k in range(80):
        t = k / 80
        pts.append((px1 + rng.uniform(-1, 1) * U * 0.8, py0 + (py1 - py0) * t))
    for k in range(80):
        t = k / 80
        pts.append((px1 - (px1 - px0) * t, py1 + rng.uniform(-1, 1) * U * 0.8))
    for k in range(80):
        t = k / 80
        pts.append((px0 + rng.uniform(-1, 1) * U * 0.8, py1 - (py1 - py0) * t))
    shadow, box = mask_crop(c, polys=[[(x + U * 3, y + U * 4) for x, y in pts]], blur=U * 3)
    over(c.img, shadow * 0.6, col('#000000'), box)
    a, box = mask_crop(c, polys=[pts], pad=2, blur=1)
    x0, y0, x1, y1 = box
    h, w = a.shape
    n = snoise(h, w, U * 20, seed, 5)
    fine = snoise(h, w, U * 0.8, seed + 1, 3)
    stains = snoise(h, w, U * 12, seed + 2, 4)
    xx = np.linspace(-1, 1, w, dtype=F)[None, :]
    yy = np.linspace(-1, 1, h, dtype=F)[:, None]
    edge = clamp01(np.maximum(np.abs(xx), np.abs(yy)) ** 6 * 1.2 + (n - 0.5) * 0.3)
    paper = mix(col('#f0dfb0'), col('#d8b878'), clamp01(n * 1.2 - 0.2)[..., None])
    paper = paper * (0.94 + 0.12 * fine)[..., None]
    paper = mix(paper, col('#a87a40'), (clamp01((stains - 0.62) * 4) * 0.35)[..., None])
    paper = mix(paper, col('#5a3418'), edge[..., None] * 0.75)
    # fold creases
    crease = np.exp(-(xx / 0.006) ** 2) * 0.12 + np.exp(-(yy / 0.006) ** 2) * 0.1
    paper = paper * (1 - crease)[..., None]
    over(c.img, a, paper, box)
    # the map, in brown ink
    ink = (70, 42, 20)
    lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = 118 * U, 112 * U
    coast = []
    for k in range(200):
        ang = k / 200 * 2 * math.pi
        r_ = 1 + 0.16 * math.sin(ang * 3 + 0.5) + 0.09 * math.sin(ang * 7 + 1.3) + 0.05 * math.sin(ang * 13)
        coast.append((cx + math.cos(ang) * 74 * U * r_, cy + math.sin(ang) * 54 * U * r_))
    coast.append(coast[0])
    d.line(coast, fill=ink + (230,), width=int(U * 0.7))
    # hatching of the sea along the coast
    for ring in (1.07, 1.14, 1.22):
        pts_ = [(cx + (x - cx) * ring, cy + (y - cy) * ring) for x, y in coast]
        for k in range(0, 200, 2):
            d.line([pts_[k], pts_[k + 1]], fill=ink + (int(140 / ring),), width=int(U * 0.35))
    # volcano symbol
    vx, vy = 112 * U, 92 * U
    d.polygon([(vx - 18 * U, vy + 14 * U), (vx - 4 * U, vy - 12 * U), (vx + 4 * U, vy - 12 * U), (vx + 18 * U, vy + 14 * U)],
              outline=ink + (255,))
    for k in range(9):
        xk = vx - 14 * U + k * 3.2 * U
        d.line([(xk, vy + 13 * U), (xk + 4 * U, vy - 4 * U)], fill=ink + (150,), width=int(U * 0.3))
    for k in range(4):
        d.arc((vx - 4 * U + k * 3 * U, vy - 24 * U - k * 4 * U, vx + 4 * U + k * 3 * U, vy - 14 * U - k * 4 * U), 120, 360,
              fill=ink + (200,), width=int(U * 0.5))
    # palms, hut, tower, marsh tufts
    for k in range(14):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.62, 0.85)
        x = cx + math.cos(ang) * 74 * U * rr
        y = cy + math.sin(ang) * 54 * U * rr
        if abs(x - vx) < 26 * U and abs(y - vy) < 22 * U:
            continue
        d.line([(x, y), (x + U * 0.5, y - U * 5)], fill=ink + (230,), width=int(U * 0.4))
        for a2 in (-2.6, -2.0, -1.2, -0.6):
            d.arc((x + U * 0.5 - U * 3, y - U * 7, x + U * 0.5 + U * 3, y - U * 3), math.degrees(a2) - 30, math.degrees(a2) + 30,
                  fill=ink + (230,), width=int(U * 0.4))
    hx, hy_ = 150 * U, 128 * U
    d.polygon([(hx - 4 * U, hy_), (hx + 4 * U, hy_), (hx + 4 * U, hy_ - 5 * U), (hx, hy_ - 9 * U), (hx - 4 * U, hy_ - 5 * U)],
              outline=ink + (255,))
    tx, ty = 78 * U, 124 * U
    d.rectangle((tx - 3 * U, ty - 10 * U, tx + 3 * U, ty), outline=ink + (255,))
    for k in range(3):
        d.rectangle((tx - 3 * U + k * 2.2 * U, ty - 12 * U, tx - 2 * U + k * 2.2 * U, ty - 10 * U), fill=ink + (255,))
    for k in range(8):
        mx_ = 140 * U + rng.uniform(-8, 8) * U
        my_ = 92 * U + rng.uniform(-5, 5) * U
        for j in (-1, 0, 1):
            d.line([(mx_, my_), (mx_ + j * U, my_ - 2.5 * U)], fill=ink + (200,), width=int(U * 0.3))
    # dotted path from the wreck on the shore to an X
    path = [(60 * U, 150 * U), (72 * U, 140 * U), (78 * U, 128 * U), (95 * U, 118 * U), (112 * U, 112 * U), (128 * U, 120 * U),
            (148 * U, 126 * U)]
    for (a0, a1) in zip(path, path[1:]):
        for t in np.linspace(0, 1, 6, endpoint=False):
            x = a0[0] + (a1[0] - a0[0]) * t
            y = a0[1] + (a1[1] - a0[1]) * t
            d.ellipse((x - U * 0.6, y - U * 0.6, x + U * 0.6, y + U * 0.6), fill=ink + (220,))
    ex, ey = 104 * U, 104 * U
    for s_ in (-1, 1):
        d.line([(ex - 3.5 * U, ey - 3.5 * U * s_), (ex + 3.5 * U, ey + 3.5 * U * s_)], fill=(140, 30, 20, 240), width=int(U * 1.0))
    # the wreck symbol
    d.arc((52 * U, 146 * U, 66 * U, 156 * U), 0, 180, fill=ink + (255,), width=int(U * 0.6))
    d.line([(59 * U, 151 * U), (62 * U, 141 * U)], fill=ink + (255,), width=int(U * 0.5))
    # compass rose
    rx, ry = 196 * U, 44 * U
    for k in range(8):
        ang = k / 8 * 2 * math.pi - math.pi / 2
        ln = 13 * U if k % 2 == 0 else 7 * U
        tipx, tipy = rx + math.cos(ang) * ln, ry + math.sin(ang) * ln
        nx, ny = -math.sin(ang) * 2 * U, math.cos(ang) * 2 * U
        d.polygon([(rx + nx, ry + ny), (tipx, tipy), (rx - nx, ry - ny)], outline=ink + (255,),
                  fill=ink + (200,) if k % 2 == 0 and k < 4 else None)
    d.ellipse((rx - 5 * U, ry - 5 * U, rx + 5 * U, ry + 5 * U), outline=ink + (255,), width=int(U * 0.4))
    d.ellipse((rx - 15 * U, ry - 15 * U, rx + 15 * U, ry + 15 * U), outline=ink + (150,), width=int(U * 0.3))
    # scribbled notes (illegible): wavy lines like handwriting
    def scribble(x0, y0, width, lines, seed_):
        rr = np.random.default_rng(seed_)
        for li in range(lines):
            x = x0
            y = y0 + li * 6 * U
            lw = width * rr.uniform(0.6, 1.0)
            while x < x0 + lw:
                wl = rr.uniform(4, 14) * U
                pts_ = []
                for k in range(int(wl / (U * 0.5))):
                    pts_.append((x + k * U * 0.5, y + math.sin(k * 1.9 + rr.uniform(0, 1)) * U * rr.uniform(0.6, 1.6)
                                 - (U * 1.5 if rr.random() < 0.08 else 0)))
                if len(pts_) > 1:
                    d.line(pts_, fill=ink + (200,), width=int(U * 0.35))
                x += wl + rr.uniform(1.5, 3.5) * U

    scribble(26 * U, 24 * U, 120 * U, 5, seed + 1)
    scribble(30 * U, 182 * U, 150 * U, 4, seed + 2)
    scribble(150 * U, 150 * U, 60 * U, 3, seed + 3)
    # ink blots
    for k in range(3):
        bx, by = rng.uniform(30, 210) * U, rng.uniform(30, 200) * U
        d.ellipse((bx - U * 1.5, by - U, bx + U * 1.5, by + U), fill=ink + (200,))
    c.comp(lay.filter(ImageFilter.GaussianBlur(1.2)))
    vignette(c, 0.45, 2.0)
    grain(c, 0.015, seed)


@scene('escape', full=True)
def bg_escape(c):
    seed = 521
    hy_v = 70
    sky(c, hy_v + 1, stops=[(0.0, col('#2a3a7a')), (0.4, col('#7a5a9a')), (0.75, col('#f08a6a')), (0.92, col('#ffb060')),
                            (1.0, col('#ffe0a0'))], sun=(190, 66), sun_col=col('#ffd080'), sun_r=40, sun_str=0.7)
    glow(c, 190 * U, 67 * U, U * 6, col('#fff0c0'), 1.5, power=3)
    wisps(c, 20, 66, seed, color=col('#ffb8a0'), amount=0.55)
    wisps(c, 30, 60, seed + 1, color=col('#7a5a8a'), amount=0.35)
    cam = Cam(c, hy_v, h=900.0, fov=80)
    X, Z, y0 = cam.ground()
    land, hgt, rr = island_terrain(X, Z, seed, cx=-500, cz=2600, R=1700)
    # sea: dark blue with the sun's path of light
    n = fbm(X * 0.004, Z * 0.012, seed + 1, 5)
    sea = mix(col('#1a2a5a'), col('#3a4a8a'), n[..., None])
    xs = (c.xs - 190 * U) / U
    path = np.exp(-(xs / (4 + 1500.0 / np.sqrt(Z))) ** 2)
    path = path * (0.4 + 0.6 * clamp01((fbm(X * 0.02, Z * 0.08, seed + 2, 3) - 0.4) * 3))
    sea = sea + path[..., None] * col('#ffc070') * 0.9
    sea = mix(sea, col('#c08a8a'), smooth(4000, 40000, Z)[..., None] * 0.6)
    jung = mix(col('#1e3a24'), col('#4a6a34'), fbm(X * 0.006, Z * 0.006, seed + 3, 5)[..., None])
    jung = jung * (0.7 + 0.5 * fbm(X * 0.03, Z * 0.03, seed + 4, 3))[..., None]
    jung = jung * (0.75 + 0.4 * clamp01(X / 2000 + 0.5))[..., None]
    beach = smooth(0.93, 0.985, rr) * land
    rgb = mix(sea, jung, land[..., None])
    rgb = mix(rgb, col('#e0b080'), beach[..., None])
    surf = smooth(0.99, 1.0, rr) * (1 - smooth(1.0, 1.025, rr))
    rgb = mix(rgb, col('#ffe8d8'), (surf * 0.7)[..., None])
    rgb = mix(rgb, col('#d09080'), smooth(3000, 30000, Z)[..., None] * 0.35)
    c.img[y0:] = rgb
    # the volcano on the island
    vx, vy = cam.proj(-500, 0, 2600)
    volcano_cone(c, vx / U, vy / U + 4, vy / U - 30, 60, 6, seed, haze=col('#a07080'), haze_amt=0.3, green=False,
                 glow_top=True, fade_base=True)
    smoke_plume(c, vx / U, vy / U - 30, seed + 5, 35, 6, drift=1.0, dark=col('#4a3a4a'), lit=col('#e0a090'), alpha=0.75)
    vignette(c, 0.4, 2.2)
    grade(c, sat=1.08)


@scene('part2', full=True)
def bg_part2(c):
    seed = 531
    eye = 1.6
    hy_v = 96
    r = Ray(c, hy_v, 70.0, eye)
    hw = 1.25
    z0 = 2.0
    run, rise = 0.34, 0.22
    tl = r.plane('x', -hw)
    tr = r.plane('x', hw)
    # sloping ceiling following the stairs down
    s_ = rise / run
    ceil0 = 1.1
    with np.errstate(divide='ignore', invalid='ignore'):
        tc = np.where(r.dy + s_ > 1e-4, (ceil0 + z0 * s_) / (r.dy + s_), INF)
    tc = np.where(tc * r.dy > ceil0 - (tc - z0) * s_ - 0.01, tc, INF)
    tc = np.where(tc > 0, tc, INF)
    tland = r.plane('y', -eye)
    tland = np.where(tland < z0, tland, INF)
    best = np.minimum(np.minimum(tl, tr), np.minimum(tc, tland))
    idx = np.where(best == tl, 2, np.where(best == tr, 3, np.where(best == tc, 1, 0)))
    for i in range(40):
        zi = z0 + i * run
        yi = -eye - (i + 1) * rise
        tt = np.where(r.dy < 0, yi / np.minimum(r.dy, -1e-6), INF)
        ok = (tt >= zi) & (tt <= zi + run) & (tt < best)
        best = np.where(ok, tt, best)
        idx = np.where(ok, 5, idx)
        # riser
        tz = np.full(best.shape, zi, F)
        yv = r.dy * zi
        ok = (yv <= yi + rise) & (yv >= yi) & (tz < best)
        best = np.where(ok, tz, best)
        idx = np.where(ok, 6, idx)
    t = best
    P = r.pos(t)
    v = P[..., 1]
    walls_u = P[..., 2]
    rgb_w, _, mw = masonry(walls_u, v, 0.6, 0.3, seed, col('#8a7a66'), mortar=0.08, var=0.35)
    step_c = concrete_rgb(P[..., 0] * 2, P[..., 2] * 2, seed + 1, col('#8a8070'))
    alb = np.where(((idx == 2) | (idx == 3))[..., None], rgb_w, np.where((idx == 1)[..., None], rgb_w * 0.8, step_c))
    alb = np.where((idx == 6)[..., None], alb * 0.7, alb)
    t = t - np.where((idx == 2) | (idx == 3), mw * 0.03, 0) + (fbm3(P, 5, seed + 2, 3) - 0.5) * 0.03
    P = r.pos(t)
    N = normals(P, r.dx, r.dy)
    torch_pos = (1.1, 0.2, 2.6)
    lights = [(torch_pos, TORCH, 14.0, 1.4)]
    rgb = tonemap(alb * light_up(P, N, lights, col('#030203')), 1.1)
    c.img = rgb.astype(F)
    # arch at the bottom of the stairs with an iron grille swung open
    za = z0 + 12 * run
    ya = -eye - 12 * rise
    a0 = r.project(-hw, ya + 2.2, za)
    a1 = r.project(hw, ya, za)
    X0, Y0, X1, Y1 = int(a0[0]), int(a0[1] - U * 2), int(a1[0]), int(a1[1])
    uu = np.arange(X0, X1, dtype=F)[None, :] / U
    vv = np.arange(Y0, Y1, dtype=F)[:, None] / U
    frgb, bev, _ = masonry(np.broadcast_to(uu, (Y1 - Y0, X1 - X0)), np.broadcast_to(-vv, (Y1 - Y0, X1 - X0)), 6.0, 3.0,
                           seed + 7, col('#8a7a66'), mortar=0.08, var=0.35)
    dist = math.sqrt((torch_pos[0]) ** 2 + (ya - torch_pos[1]) ** 2 + (za - torch_pos[2]) ** 2)
    att = 14.0 / (1 + (dist / 1.4) ** 2)
    c.img[Y0:Y1, X0:X1] = tonemap(frgb * (1 + bev[..., None] * 0.5) * TORCH * att * 0.6, 1.1)
    lay, d = c.layer()
    ix0 = r.project(-hw * 0.75, ya + 1.9, za)
    ix1 = r.project(hw * 0.75, ya, za)
    rr_ = (ix1[0] - ix0[0]) / 2
    d.rectangle((ix0[0], ix0[1] + rr_, ix1[0], ix1[1]), fill=(6, 4, 3, 255))
    d.pieslice((ix0[0], ix0[1], ix1[0], ix0[1] + 2 * rr_), 180, 360, fill=(6, 4, 3, 255))
    # voussoirs
    for k in range(9):
        ang0 = math.pi + k / 9 * math.pi
        ang1 = math.pi + (k + 1) / 9 * math.pi
        ccx, ccy = (ix0[0] + ix1[0]) / 2, ix0[1] + rr_
        R0, R1 = rr_, rr_ + U * 4
        pts = [(ccx + math.cos(ang0) * R0, ccy + math.sin(ang0) * R0), (ccx + math.cos(ang0) * R1, ccy + math.sin(ang0) * R1),
               (ccx + math.cos(ang1) * R1, ccy + math.sin(ang1) * R1), (ccx + math.cos(ang1) * R0, ccy + math.sin(ang1) * R0)]
        d.polygon(pts, fill=rgb255(col('#6a5844') * (0.8 + 0.05 * (k % 3))) + (255,))
    # the grille, swung open towards us on the left
    gx0 = ix0[0]
    gy0, gy1 = ix0[1] + rr_ * 0.4, ix1[1]
    gw = (ix1[0] - ix0[0]) * 0.55
    for k in range(9):
        f = k / 8
        x = gx0 - gw * f
        yt = gy0 - (gy1 - gy0) * 0.08 * f
        yb = gy1 + (gy1 - gy0) * 0.12 * f
        d.line([(x, yt), (x, yb)], fill=(30, 26, 24, 255), width=int(U * (0.9 + 0.4 * f)))
    for fy in (0.05, 0.5, 0.95):
        d.line([(gx0, gy0 + (gy1 - gy0) * fy), (gx0 - gw, gy0 - (gy1 - gy0) * 0.08 + (gy1 - gy0) * 1.2 * fy)],
               fill=(36, 30, 26, 255), width=int(U * 1.3))
    c.comp(lay)
    # shade the arch by distance from the torch
    # wall torch on the right with flame and glow
    tx, ty = r.project(torch_pos[0] + 0.05, torch_pos[1] - 0.3, torch_pos[2])
    lay, d = c.layer()
    sc = r.f / torch_pos[2]
    d.polygon([(tx - sc * 0.03, ty), (tx + sc * 0.03, ty), (tx + sc * 0.06, ty - sc * 0.35), (tx - sc * 0.01, ty - sc * 0.35)],
              fill=rgb255(col('#3a2a1a')) + (255,))
    d.rectangle((tx - sc * 0.02, ty - sc * 0.05, tx + sc * 0.12, ty + sc * 0.02), fill=rgb255(col('#2a2420')) + (255,))
    fx, fy = tx + sc * 0.025, ty - sc * 0.38
    d.polygon([(fx - sc * 0.08, fy), (fx, fy - sc * 0.3), (fx + sc * 0.07, fy - sc * 0.02), (fx + sc * 0.02, fy + sc * 0.04)],
              fill=(255, 150, 40, 255))
    d.polygon([(fx - sc * 0.04, fy), (fx, fy - sc * 0.17), (fx + sc * 0.04, fy)], fill=(255, 235, 150, 255))
    c.comp(lay)
    glow(c, fx, fy - sc * 0.08, sc * 0.25, col('#ffa040'), 1.2)
    glow(c, fx, fy - sc * 0.08, sc * 0.9, col('#ff7a20'), 0.35)
    finish_underground(c, amount=0.6, seed=seed)


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------

def main(argv):
    names = argv[1:] or list(SCENES)
    for name in names:
        fn, full = SCENES[name]
        t = time.time()
        c = Canvas(240, 224 if full else 136)
        fn(c)
        path = c.save('bg_' + name)
        print('%-18s %5.1fs  %4d KB' % (name, time.time() - t, os.path.getsize(path) // 1024))


if __name__ == '__main__':
    main(sys.argv)
