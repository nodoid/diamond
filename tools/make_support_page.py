#!/usr/bin/env python3
"""Builds the support page (with the privacy policy) for the store "Support URL".

    python3 tools/make_support_page.py [capture-root]

Writes docs/Diamond-Support.html (self-contained: the icon and screenshots are embedded) and
copies it to ~/Downloads, ready to upload to the web site. The page is in English (the game itself
and the store listings are also in French).

Screenshots come from <capture-root>/en/desktop/stills (the output of the game's capture mode, see
tools/capture_all.sh) when it is given, otherwise from store/en/mac-app-store/screenshots-1440x900
if tools/make_store_assets.py has been run. Without either, the page is built without pictures.
"""
import base64
import glob
import io
import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs', 'Diamond-Support.html')
ICON = os.path.join(ROOT, 'art', 'icon-1024.png')
EMAIL = 'paul@all-the-johnsons.co.uk'
UPDATED = '6 October 2026'

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from make_store_assets import fit  # noqa: E402


def jpeg(im, width, quality=82):
    im = im.convert('RGB')
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def shot(name, cap):
    """A 16:10 screenshot by capture name (e.g. '15-dragon'), or None."""
    if cap:
        p = os.path.join(cap, 'en', 'desktop', 'stills', name + '.png')
        if os.path.exists(p):
            return fit(Image.open(p), 1440, 900)
    found = glob.glob(os.path.join(ROOT, 'store', 'en', 'mac-app-store', 'screenshots-1440x900', '*-' + name[3:] + '.png'))
    return Image.open(found[0]) if found else None


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else None
    if cap and not os.path.isdir(cap):
        sys.exit(f'no capture folder {cap}')
    icon = jpeg(Image.open(ICON), 160) if os.path.exists(ICON) else ''
    hero = shot('15-dragon', cap) or shot('01-title', cap)
    hero_html = f'<img class="hero" src="{jpeg(hero, 1080)}" alt="The Diamond of Cursed Island: the dragon\'s lair">' if hero else ''
    pics = [p for p in (shot('03-tower', cap), shot('11-buddha', cap), shot('13-gorilla', cap)) if p]
    gallery_html = ('<div class="gallery">' + ''.join(f'<img src="{jpeg(p, 520, 78)}" alt="">' for p in pics) + '</div>') if pics else ''
    icon_link = f'<link rel="icon" href="{icon}">' if icon else ''
    icon_img = f'<img src="{icon}" alt="">' if icon else ''

    sections = [
        ('about', 'The game', '''<p>A storm throws your boat onto the reefs of a cursed island in the Pacific. All you have is the journal of Steven Smith, an explorer who came here in 1934 looking for a priceless diamond hidden by a vanished civilisation, and never left. Find the diamond, and get off the island alive.</p>
<p>The Diamond of Cursed Island is an unofficial, fully illustrated remake of <em>Le Diamant de l'Île Maudite</em>, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille (Loriciels). You see the island through your own eyes, in four directions from each of its 49 places, and you act by giving orders, as in the original. It runs on iPhone, iPad, Android, Mac and Windows, in English and French.</p>'''),
        ('orders', 'Giving orders', '''<p>Orders are a verb and a noun: <kbd>TAKE CLUB</kbd>, <kbd>OPEN DRAWER</kbd>, <kbd>THROW KNIFE</kbd>. <kbd>FORWARD</kbd> walks 50 metres the way you face; <kbd>LEFT</kbd>, <kbd>RIGHT</kbd> and <kbd>BACK</kbd> turn you. <kbd>LOOK</kbd>, <kbd>EXAMINE</kbd>, <kbd>INVENTORY</kbd>, <kbd>STATUS</kbd>, <kbd>REST</kbd> and <kbd>HELP</kbd> are there when you need them. The game knows about 90 words in each language.</p>
<p>Choose how the game reads your orders with <em>Commands</em> in the menu:</p>
<ul>
<li><strong>Short form</strong> (as in 1984, the default): a word is recognised from its first three or four letters and completed as you type, so <kbd>THR CLU</kbd> becomes <kbd>THROW CLUB</kbd>. A word the game doesn't know is erased with a beep. Chain up to 40 orders with <kbd>/</kbd>: <kbd>FORWARD/LEFT/TAKE GOURD</kbd>.</li>
<li><strong>Long form</strong>: whole sentences, with other verb forms and little words, such as <em>"pick up the coconut"</em>, <em>"throw the club at the spider"</em> or <em>"take the rope and the bucket then go forward"</em>. Chain orders with <em>and</em>, <em>then</em>, a comma or <kbd>/</kbd>. The short form's abbreviations still work.</li>
</ul>
<p>On a phone or tablet you don't need to type: tap <strong>WORDS</strong>, then a verb, then a noun, and the order is given. A keyboard works too.</p>'''),
        ('controls', 'Controls', '''<table><thead><tr><th></th><th>Mac and Windows</th><th>iPhone, iPad and Android</th></tr></thead><tbody>
<tr><td>Give an order</td><td>Type it, then <kbd>Return</kbd></td><td>Tap <strong>WORDS</strong>, a verb, then a noun (or type on a keyboard)</td></tr>
<tr><td>Walk forward / turn</td><td>With an empty line: <kbd>&uarr;</kbd>, <kbd>&larr;</kbd> <kbd>&rarr;</kbd>, <kbd>&darr;</kbd> to turn round</td><td>The arrow buttons</td></tr>
<tr><td>Previous order</td><td><kbd>&uarr;</kbd> while typing</td><td>&ndash;</td></tr>
<tr><td>Scroll the text</td><td><kbd>Page Up</kbd> / <kbd>Page Down</kbd> or the mouse wheel</td><td>Swipe the text</td></tr>
<tr><td>Menu</td><td><kbd>Esc</kbd></td><td><strong>MENU</strong> or Back</td></tr>
<tr><td>Full screen</td><td><kbd>F11</kbd> or <kbd>Alt</kbd>+<kbd>Enter</kbd></td><td>Always</td></tr>
</tbody></table>
<p>The mouse can also use the on-screen buttons and the <strong>WORDS</strong> list. The menu has <em>Language</em>, <em>Commands</em> (short or long form), <em>Volume</em>, <em>Instructions</em> and the <em>Hall of Fame</em>.</p>'''),
        ('island', 'The island', '''<ul>
<li><strong>Two parts.</strong> Part one is the island's surface: the beach and the wreck, the jungle, a ruined tower, an explorer's hut, a swamp, the volcano and an old military hangar. Part two is underground: a temple, galleries, a well, and the creatures that live there.</li>
<li><strong>Look everywhere.</strong> You only see what is in front of you, and some things can be seen from one place, facing one way. Turn round in every new place.</li>
<li><strong>You can only take what you see,</strong> and you can't carry more than eight things.</li>
<li><strong>Survival.</strong> Hunger, thirst, fatigue, fever, injuries and venom add up, as in the original. When your <strong>FITNESS</strong> bar reaches zero, you die. <kbd>STATUS</kbd> tells you what is wrong. Time passes even while you think, so don't wait too long.</li>
<li><strong>Saving.</strong> The game is saved after every order; <em>Continue game</em> on the menu picks up where you left off. The start of part two is a checkpoint: if you die underground, choose <em>Restart part two</em>.</li>
<li><strong>Score.</strong> Each step of the quest earns points, up to 100. The Hall of Fame ranks you by score, then by the fewest moves.</li>
</ul>'''),
        ('faq', 'Questions', '''<h3>The game erases my words.</h3><p>In the short form, a word the game doesn't know is erased with a beep, as in 1984. Try another word, or switch to the long form under <em>Commands</em> in the menu. <kbd>HELP</kbd> and the <em>Instructions</em> show the kind of orders the game understands; on a touch screen, <strong>WORDS</strong> lists them all.</p>
<h3>I keep dying.</h3><p>Look after yourself: eat, drink, rest and treat your wounds, and check <kbd>STATUS</kbd> often. Some creatures must be dealt with before you get close, and some places are dangerous without the right equipment. The original was famously hard; the checkpoint at the start of part two is there to help.</p>
<h3>I'm stuck.</h3><p>Turn round in every place: many things are only visible from one direction. <kbd>EXAMINE</kbd> what you find and read what you can. Something that seems useless may hide something else.</p>
<h3>How do I change the language?</h3><p>Choose <em>Language</em> in the menu. The first time, the game follows your device's language.</p>
<h3>Where is my game saved?</h3><p>Only on your device, in the game's own storage. Uninstalling the game deletes it.</p>'''),
        ('privacy', 'Privacy', f'''<p><strong>The Diamond of Cursed Island collects nothing.</strong> It has no accounts, advertising, analytics or tracking, and it never connects to the internet. It doesn't collect, store, share or sell any personal information, from anyone, including children.</p>
<p>The game keeps a few small files in its private storage on your device: your settings (language, command form and volume), your saved game and the part two checkpoint, and the Hall of Fame (the names you enter, with your scores and moves). They never leave your device and are deleted when you uninstall the game.</p>
<p>If this policy changes, the new version will be posted here with a new date. Last updated: {UPDATED}.</p>'''),
        ('contact', 'Contact', f'<p>Found a bug, or have a question this page doesn\'t answer? Email <a href="mailto:{EMAIL}?subject=Diamond%20of%20Cursed%20Island%20support">{EMAIL}</a>.</p>'),
    ]

    nav = ''.join(f'<a href="#{sid}">{title}</a>' for sid, title, _ in sections)
    body = ''.join(f'<section id="{sid}"><h2>{title}</h2>{content}</section>' for sid, title, content in sections)
    body = body.replace('<table>', '<div class="table"><table>').replace('</table>', '</table></div>')
    body = body.replace('</section><section id="orders">', gallery_html + '</section><section id="orders">', 1)

    html = f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cursed Island Support</title>
<meta name="description" content="Help and support for The Diamond of Cursed Island (Le Diamant de l'Île Maudite), the illustrated remake of the 1984 Oric adventure, for iPhone, iPad, Android, Mac and Windows: how to give orders, controls, questions, privacy and contact.">
{icon_link}
<style>
:root {{ --bg: #F2F1EC; --pane: #FFFFFF; --chip: #E3E8E2; --text: #1A1E1C; --muted: #5F6862;
  --accent: #1F6F8B; --accent-2: #A0601A; --border: #D5DBD4; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg: #0B1416; --pane: #13211F; --chip: #1F3330; --text: #ECEFEA;
    --muted: #A3B1AC; --accent: #7FD3EE; --accent-2: #F2A35A; --border: #284240; }}
}}
:root[data-theme="dark"] {{ --bg: #0B1416; --pane: #13211F; --chip: #1F3330; --text: #ECEFEA;
  --muted: #A3B1AC; --accent: #7FD3EE; --accent-2: #F2A35A; --border: #284240; }}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Roboto, "Helvetica Neue", Arial, sans-serif; }}
a {{ color: var(--accent); }}
.wrap {{ max-width: 1000px; margin: 0 auto; padding: 0 16px; }}
header {{ background: var(--pane); border-bottom: 1px solid var(--border); }}
header .wrap {{ padding-top: 32px; padding-bottom: 26px; }}
.brand {{ display: flex; align-items: center; gap: 16px; }}
.brand img {{ width: 72px; height: 72px; border-radius: 16px; flex: none; }}
.eyebrow {{ color: var(--accent-2); font-weight: 600; margin: 0; }}
h1 {{ font-size: clamp(26px, 5vw, 40px); line-height: 1.15; margin: 0; }}
.lead {{ font-size: 18px; color: var(--muted); margin: 16px 0 0; max-width: 48em; }}
.hero {{ width: 100%; border-radius: 14px; margin-top: 22px; display: block; }}
nav.toc {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }}
nav.toc a {{ text-decoration: none; color: var(--text); background: var(--chip); border-radius: 999px; padding: 6px 14px; font-size: 14px; }}
main section {{ background: var(--pane); border: 1px solid var(--border); border-radius: 14px; padding: 8px 24px 16px; margin: 20px 0; }}
h2 {{ font-size: 24px; margin: 16px 0 8px; }}
h3 {{ font-size: 17px; margin: 18px 0 2px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
.table {{ overflow-x: auto; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
kbd {{ font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--chip); border: 1px solid var(--border);
  border-radius: 5px; padding: 1px 5px; white-space: nowrap; }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 14px 0 6px; }}
.gallery img {{ width: 100%; border-radius: 10px; display: block; }}
footer {{ color: var(--muted); font-size: 14px; padding: 8px 0 40px; }}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="brand">{icon_img}
    <div><p class="eyebrow">Support</p><h1>The Diamond of Cursed Island</h1></div></div>
  <p class="lead">The 1984 Oric adventure, remade with pictures for iPhone, iPad, Android, Mac and Windows. In English and French.</p>
  {hero_html}
  <nav class="toc">{nav}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap">An unofficial remake by PFJ, based on the 1984 Loriciels game <em>Le Diamant de l'Île Maudite</em> by Bertrand d'Armagnac and Frédéric Baille. © 2026 Paul F. Johnson.</footer>
</body>
</html>
'''
    with open(OUT, 'w') as f:
        f.write(html)
    dl = os.path.join(os.path.expanduser('~'), 'Downloads', 'Diamond-Support.html')
    try:
        shutil.copy(OUT, dl)
        where = f', copied to {dl}'
    except OSError as e:
        where = f' (not copied to {dl}: {e})'
    pictures = (1 if hero else 0) + len(pics)
    print(f'{os.path.relpath(OUT, ROOT)} ({len(html) // 1024} KB, {pictures} screenshots){where}')


if __name__ == '__main__':
    main()
