"""Generates every platform icon and splash screen (run from the repo root, after the art scripts).

Sources (drawn by tools/make_sprites.py and tools/make_backgrounds.py):
    art/icon-1024.png              the app icon: the diamond before the cursed island at dusk
    art/icon-foreground-1024.png   the diamond alone (Android adaptive icon foreground)
    Diamond.Core/Art/bg_title.jpg  the title painting (splash screens)
"""
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter

ICON = Image.open('art/icon-1024.png').convert('RGBA')
FOREGROUND = Image.open('art/icon-foreground-1024.png').convert('RGBA')
TITLE = Image.open('Diamond.Core/Art/bg_title.jpg').convert('RGB')
DIAMOND = Image.open('Diamond.Core/Art/diamond.png').convert('RGBA')


def save(im, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    im.save(path)


def icon(size):
    return ICON.resize((size, size), Image.LANCZOS)


def rounded(size):
    """The icon in a circle (Android round launcher icon)."""
    big = ICON.resize((size * 4, size * 4), Image.LANCZOS)
    mask = Image.new('L', big.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big.width - 1, big.height - 1], fill=255)
    out = Image.new('RGBA', big.size, (0, 0, 0, 0))
    out.paste(big, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


def on_canvas(img, w, h, scale, bg=(0, 0, 0, 0)):
    """An image scaled to `scale` of the canvas height, centred."""
    canvas = Image.new('RGBA', (w, h), bg)
    k = min(w, h) * scale / max(img.width, img.height)
    im = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    canvas.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


def splash(w, h):
    """The title painting with the diamond glowing at its heart, framed in black (no text)."""
    pic = TITLE.copy()
    pic.thumbnail((w, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    out.paste(pic, ((w - pic.width) // 2, (h - pic.height) // 2))
    d = DIAMOND.copy()
    k = h * 0.22 / d.height
    d = d.resize((int(d.width * k), int(d.height * k)), Image.LANCZOS)
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    r = int(h * 0.22)
    cx, cy = w // 2, int(h * 0.56)
    ImageDraw.Draw(glow).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 230, 255, 120))
    out = Image.alpha_composite(out, glow.filter(ImageFilter.GaussianBlur(r * 0.5)))
    out.alpha_composite(d, (cx - d.width // 2, cy - d.height // 2))
    return out


# ---------------------------------------------------------------- Android
DENSITIES = [('mdpi', 1), ('hdpi', 1.5), ('xhdpi', 2), ('xxhdpi', 3), ('xxxhdpi', 4)]
for folder, k in DENSITIES:
    save(icon(int(48 * k)), f'Diamond.Android/Resources/mipmap-{folder}/icon.png')
    save(rounded(int(48 * k)), f'Diamond.Android/Resources/mipmap-{folder}/icon_round.png')
    # Adaptive icon foreground: 108 dp, the diamond inside the 72 dp safe zone.
    save(on_canvas(FOREGROUND, int(108 * k), int(108 * k), 1.0), f'Diamond.Android/Resources/mipmap-{folder}/icon_foreground.png')
    # Launch screen before Android 12 (a centred bitmap on black).
    save(splash(int(300 * k), int(280 * k)), f'Diamond.Android/Resources/drawable-{folder}/splash.png')
    # Android 12+ system splash icon: 288 dp, contents within the central 192 dp circle.
    save(on_canvas(FOREGROUND, int(288 * k), int(288 * k), 0.62), f'Diamond.Android/Resources/drawable-{folder}/splash_icon.png')

# ---------------------------------------------------------------- iOS
ios = 'Diamond.iOS/AppIcon.xcassets/AppIcon.appiconset'
for n in [20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024]:
    save(icon(n).convert('RGB'), os.path.join(ios, f'icon_{n}x{n}.png'))
for suffix, k in [('', 1), ('@2x', 2), ('@3x', 3)]:
    save(splash(600 * k, 560 * k).convert('RGB'), f'Diamond.iOS/Resources/LaunchSplash{suffix}.png')

# ---------------------------------------------------------------- Windows
os.makedirs('Diamond.WindowsDX/Windows/Assets', exist_ok=True)
icon(256).save('Diamond.WindowsDX/Icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
shutil.copy('Diamond.WindowsDX/Icon.ico', 'Diamond.DesktopGL/Icon.ico')
for name, size in [('Square44x44Logo', (44, 44)), ('Square150x150Logo', (150, 150)), ('StoreLogo', (50, 50)),
                   ('Square71x71Logo', (71, 71)), ('Square310x310Logo', (310, 310))]:
    save(icon(size[0]), f'Diamond.WindowsDX/Windows/Assets/{name}.png')
save(on_canvas(FOREGROUND, 44, 44, 1.0), 'Diamond.WindowsDX/Windows/Assets/Square44x44Logo.targetsize-44_altform-unplated.png')
wide = splash(310, 150)
save(wide, 'Diamond.WindowsDX/Windows/Assets/Wide310x150Logo.png')
save(splash(620, 300), 'Diamond.WindowsDX/Windows/Assets/SplashScreen.png')

# ---------------------------------------------------------------- macOS
iconset = 'art/Diamond.iconset'
os.makedirs(iconset, exist_ok=True)
for s in [16, 32, 128, 256, 512]:
    icon(s).save(f'{iconset}/icon_{s}x{s}.png')
    icon(s * 2).save(f'{iconset}/icon_{s}x{s}@2x.png')
subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', 'Diamond.DesktopGL/Diamond.icns'], check=True)
shutil.rmtree(iconset)
print('icons and splash screens done')
