#!/usr/bin/env python3
"""Builds the store screenshots and graphics in store/ from game captures.

    python3 tools/make_store_assets.py stills <capture-root>
    python3 tools/make_store_assets.py art                  (only the text-free key art)

<capture-root> holds the output of the game's capture mode (see tools/capture_all.sh):

    <lang>/desktop/stills/NN-name.png   macOS captures with desktop prompts   (2400 x 2240)
    <lang>/mobile/stills/NN-name.png    captures with touch prompts (arrows, WORDS)
    <lang>/windows/stills/NN-name.png   captures made by the Windows build (tools/build_windows.sh capture)

The game screen keeps its proportions; the rest of each image is the same picture enlarged,
blurred and darkened, so nothing is stretched and there are no black bars. The Microsoft Store
super hero art must carry no text, so it is painted from the title backdrop
(Diamond.Core/Art/bg_title.jpg) and the diamond itself, redrawn large by tools/make_sprites.py.
There are no app preview videos for this game.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, 'store')
ART = os.path.join(ROOT, 'Diamond.Core', 'Art')
ICON = os.path.join(ROOT, 'art', 'icon-1024.png')
LANGS = {'en': 'English', 'fr': 'French'}

# The captures (see Diamond.Core/Demo/CaptureDirector.cs):
#   01-title 02-beach 03-tower 04-hut 05-plant 06-palm 07-cobra 08-crater 09-trapdoor 10-part2
#   11-buddha 12-well 13-gorilla 14-sage 15-dragon 16-diamond 17-hangar 18-victory 19-menu
#   20-instructions
# The screens used for every store, in listing order (Google Play takes the first eight): the
# dragon first, then the title, the parser at work (an order being typed at the tarantula), the
# temple, the touch WORDS list at the carnivorous plant, the gorilla, the cobra, the diamond, the
# hangar and the menu with its command form setting.
SHOTS = ['15-dragon', '01-title', '03-tower', '11-buddha', '05-plant', '13-gorilla',
         '07-cobra', '16-diamond', '17-hangar', '19-menu']


def fit(img, w, h):
    """The screen fitted into w x h over a blurred, darkened copy of itself."""
    img = img.convert('RGB')
    cover = max(w / img.width, h / img.height)
    bg = img.resize((int(img.width * cover) + 1, int(img.height * cover) + 1), Image.BILINEAR)
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2, (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.resize((max(1, w // 8), max(1, h // 8)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6)).resize((w, h), Image.BICUBIC)
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    s = min(w / img.width, h / img.height)
    fg = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([(w - fg.width) // 2 - 6, (h - fg.height) // 2 - 6,
                                      (w + fg.width) // 2 + 6, (h + fg.height) // 2 + 6], fill=(0, 0, 0, 170))
    out = Image.alpha_composite(bg.convert('RGBA'), shadow.filter(ImageFilter.GaussianBlur(max(w, h) // 120)))
    out.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return out.convert('RGB')


def screenshots(src, dest, w, h, count=len(SHOTS)):
    if not os.path.isdir(src):
        print(f'skipped {os.path.relpath(dest, ROOT)}: no captures in {src}')
        return
    os.makedirs(dest, exist_ok=True)
    done = 0
    for name in SHOTS:
        if done == count:
            break
        path = os.path.join(src, name + '.png')
        if not os.path.exists(path):
            print(f'  missing {path}')
            continue
        done += 1
        fit(Image.open(path), w, h).save(os.path.join(dest, f'{done:02d}-{name[3:]}.png'))
    print(f'{os.path.relpath(dest, ROOT)}: {done} x {w}x{h}')


def cover(img, w, h, focus_y=0.5):
    """img scaled to cover w x h and cropped (vertically around focus_y)."""
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x = (img.width - w) // 2
    y = int(min(max(0, img.height * focus_y - h / 2), img.height - h))
    return img.crop((x, y, x + w, y + h))


def backdrop():
    """The title backdrop (the cursed island at dusk, no text); the volcano view if it is missing."""
    for name in ('bg_title.jpg', 'bg_volcano.jpg'):
        path = os.path.join(ART, name)
        if os.path.exists(path):
            return Image.open(path).convert('RGB')
    print('  no backdrop in Diamond.Core/Art: using a plain dusk sky')
    img = Image.new('RGB', (1440, 1344))
    d = ImageDraw.Draw(img)
    for y in range(img.height):
        t = y / img.height
        d.line([(0, y), (img.width, y)], fill=(int(40 + 150 * t), int(24 + 50 * t), int(70 + 30 * t)))
    return img


_GEM = {}


def gem(height):
    """The diamond, about `height` pixels tall: redrawn large by tools/make_sprites.py when it can
    be (numpy and scipy), otherwise the game's sprite enlarged."""
    if 'img' not in _GEM:
        img = None
        try:
            sys.path.insert(0, os.path.join(ROOT, 'tools'))
            import make_sprites
            make_sprites.PX = 40
            img = make_sprites.diamond().crop_image(14)
        except Exception as e:  # noqa: BLE001 - any failure falls back to the sprite
            path = os.path.join(ART, 'diamond.png')
            if os.path.exists(path):
                print(f'  diamond redraw failed ({e}); using {path}')
                img = Image.open(path).convert('RGBA')
            else:
                print('  no diamond picture: key art without the diamond')
        _GEM['img'] = img
    img = _GEM['img']
    if img is None:
        return None
    return img.resize((round(img.width * height / img.height), round(height)), Image.LANCZOS)


def key_art(w, h, gem_x=0.72, gem_y=0.42, gem_h=0.36):
    """Text-free key art: the island at dusk, the diamond glowing above it (centre at gem_x, gem_y,
    gem_h of the height tall), the lower left darkened and kept clear for the Store's own title."""
    img = cover(backdrop(), w, h, 0.55).convert('RGBA')
    shade = Image.new('L', (w, h), 0)
    ImageDraw.Draw(shade).ellipse([-w * 0.45, h * 0.45, w * 0.65, h * 1.55], fill=150)
    shade = shade.filter(ImageFilter.GaussianBlur(max(w, h) // 12))
    img = Image.composite(Image.new('RGBA', (w, h), (6, 8, 20, 255)), img, shade)
    g = gem(h * gem_h)
    if g is not None:
        cx, cy = w * gem_x, h * gem_y
        glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        r = g.width * 0.85
        ImageDraw.Draw(glow).ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=(170, 220, 255, 120))
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(r * 0.35)))
        img.alpha_composite(g, (int(cx - g.width / 2), int(cy - g.height / 2)))
    return img.convert('RGB')


def art(ms):
    """Super hero art (16:9, no text) for the Microsoft Store."""
    os.makedirs(ms, exist_ok=True)
    for w, h in [(1920, 1080), (3840, 2160)]:
        key_art(w, h).save(os.path.join(ms, f'super-hero-art-{w}x{h}.png'))
    print(f'{os.path.relpath(ms, ROOT)}: super hero art')


def open_shot(folder, name):
    path = os.path.join(folder, name + '.png')
    return Image.open(path).convert('RGB') if os.path.exists(path) else None


def stills(cap):
    icon = Image.open(ICON).convert('RGB') if os.path.exists(ICON) else None
    if icon is None:
        print(f'no icon at {ICON}: icons skipped')
    for lang in LANGS:
        desktop = os.path.join(cap, lang, 'desktop', 'stills')
        mobile = os.path.join(cap, lang, 'mobile', 'stills')
        windows = os.path.join(cap, lang, 'windows', 'stills')
        out = os.path.join(STORE, lang)

        # Apple App Store (iOS): landscape iPhone 6.9" and 6.5", iPad 13".
        a = os.path.join(out, 'app-store')
        screenshots(mobile, os.path.join(a, 'iphone-6.9in-2868x1320'), 2868, 1320)
        screenshots(mobile, os.path.join(a, 'iphone-6.5in-2688x1242'), 2688, 1242)
        screenshots(mobile, os.path.join(a, 'ipad-13in-2752x2064'), 2752, 2064)
        if icon:
            os.makedirs(a, exist_ok=True)
            icon.resize((1024, 1024), Image.LANCZOS).save(os.path.join(a, 'icon-1024.png'))

        # Mac App Store.
        m = os.path.join(out, 'mac-app-store')
        screenshots(desktop, os.path.join(m, 'screenshots-2880x1800'), 2880, 1800)
        screenshots(desktop, os.path.join(m, 'screenshots-1440x900'), 1440, 900)

        # Google Play: phone and 10" tablet, icon and feature graphic.
        g = os.path.join(out, 'google-play')
        screenshots(mobile, os.path.join(g, 'phone-screenshots-1920x1080'), 1920, 1080, 8)
        screenshots(mobile, os.path.join(g, 'tablet-screenshots-2560x1600'), 2560, 1600, 8)
        os.makedirs(g, exist_ok=True)
        if icon:
            icon.resize((512, 512), Image.LANCZOS).save(os.path.join(g, 'icon-512.png'))
        title = open_shot(desktop, '01-title')
        if title:
            # The top of the title screen (the island at dusk and the name) at 1024:500.
            crop = title.crop((0, 0, title.width, round(title.width * 500 / 1024)))
            fit(crop, 1024, 500).save(os.path.join(g, 'feature-graphic-1024x500.png'))
        else:
            key_art(1024, 500, 0.5, 0.45, 0.6).save(os.path.join(g, 'feature-graphic-1024x500.png'))

        # Microsoft Store: captured by the Windows (DirectX) build when available.
        ms = os.path.join(out, 'microsoft-store')
        src = windows if os.path.isdir(windows) else desktop
        screenshots(src, os.path.join(ms, 'screenshots-3840x2160'), 3840, 2160)
        screenshots(src, os.path.join(ms, 'screenshots-1920x1080'), 1920, 1080)
        screenshots(src, os.path.join(ms, 'screenshots-1366x768'), 1366, 768)
        os.makedirs(ms, exist_ok=True)
        title = open_shot(src, '01-title')
        if title:
            fit(title, 2160, 2160).save(os.path.join(ms, 'box-art-2160x2160.png'))
            fit(title, 1440, 2160).save(os.path.join(ms, 'poster-art-1440x2160.png'))
        else:
            print(f'  no title capture in {src}: box and poster art skipped')
        if icon:
            icon.resize((300, 300), Image.LANCZOS).save(os.path.join(ms, 'store-logo-300x300.png'))
        art(ms)
    print('stills done')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'stills':
        stills(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == 'art':
        for lang in LANGS:
            art(os.path.join(STORE, lang, 'microsoft-store'))
    else:
        sys.exit(__doc__)
