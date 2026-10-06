#!/usr/bin/env python3
"""Writes paste-ready upload sheets for every store and language from docs/LISTING.md.

    python3 tools/make_upload_copy.py

Creates store/<en|fr>/<store>/UPLOAD.txt: each field in the order the store's console asks for it,
with its character count, followed by the files to upload and the answers to the store's
questions. docs/LISTING.md stays the single source of the copy.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Version and build number of the release builds, from Directory.Build.props.
_PROPS = open(os.path.join(ROOT, 'Directory.Build.props')).read()
VERSION = re.search(r'<Version>([^<]+)</Version>', _PROPS).group(1)
BUILD = re.search(r'<BuildNumber>([^<]+)</BuildNumber>', _PROPS).group(1)
LISTING = os.path.join(ROOT, 'docs', 'LISTING.md')
STORE = os.path.join(ROOT, 'store')
SUPPORT = 'https://<your web site>/Diamond-Support.html  (upload ~/Downloads/Diamond-Support.html)'
PRIVACY = 'https://<your web site>/Diamond-Support.html#privacy'
EMAIL = 'paul@all-the-johnsons.co.uk'
BUNDLE = 'uk.co.allthejohnsons.diamond'
TITLE = {'en': 'The Diamond of Cursed Island', 'fr': "Le Diamant de l'Île Maudite"}
LANG_NAMES = {'en': ('English', 'English (U.K.)', 'en-GB', 'en-gb'), 'fr': ('French', 'French', 'fr-FR', 'fr-fr')}

FIELD = re.compile(r'\*\*([^*]+)\*\* \((\d+) max[^)]*\)\n```\n(.*?)\n```', re.S)


def sections(text):
    """{store heading: {'English'|'Français'|'App Review': [(label, limit, body)]}}"""
    stores = {}
    for block in re.split(r'\n## ', text)[1:]:
        title, _, rest = block.partition('\n')
        langs = {}
        for part in re.split(r'\n### ', '\n' + rest)[1:]:
            lang, _, body = part.partition('\n')
            langs[lang.strip()] = [(m.group(1), int(m.group(2)), m.group(3)) for m in FIELD.finditer(body)]
        stores[title.strip()] = langs
    return stores


def heading(title, ch='='):
    return f'{title}\n{ch * len(title)}\n'


def field(label, limit, body, per_line=False):
    count = f'longest line {max(map(len, body.splitlines()))}/{limit}' if per_line else f'{len(body)}/{limit} characters'
    return f'{heading(f"{label.upper()}  ({count})", "-")}{body}\n\n'


def files(lines):
    return heading('FILES TO UPLOAD', '-') + '\n'.join(f'- {l}' for l in lines) + '\n\n'


def answers(rows, title='ANSWERS IN THE CONSOLE'):
    width = max(len(k) for k, _ in rows)
    return heading(title, '-') + '\n'.join(f'{k.ljust(width)}  {v}' for k, v in rows) + '\n\n'


def write(lang, store, text):
    path = os.path.join(STORE, lang, store, 'UPLOAD.txt')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)
    print(os.path.relpath(path, ROOT))


# Apple's age rating questionnaire (the same for iOS and macOS); see docs/LISTING.md.
APPLE_AGE = [
    ('Parental controls / age assurance', 'No / No'),
    ('Unrestricted web access', 'No'),
    ('User-generated content', 'No'),
    ('Messaging and chat', 'No'),
    ('Advertising', 'No'),
    ('Profanity or crude humour', 'None'),
    ('Horror or fear themes', 'Infrequent/Mild'),
    ('Alcohol, tobacco or drug use or references', 'Infrequent/Mild (a cigarette packet that hides a key)'),
    ('Medical or treatment information', 'None'),
    ('Health or wellness topics', 'No'),
    ('Sexual content or nudity', 'None'),
    ('Cartoon or fantasy violence', 'Infrequent/Mild'),
    ('Realistic violence', 'None'),
    ('Prolonged graphic or sadistic violence', 'None'),
    ('Guns or other weapons', 'Infrequent/Mild'),
    ('Simulated gambling / contests / loot boxes', 'None / No / No'),
    ('Result', '9+'),
]

IARC = [
    ('Category', 'Game'),
    ('Violence', 'Fantasy violence against animals and creatures, described in text; no blood, no gore, none against humans'),
    ('Fear', 'Mild (a ghost, a skeleton, a dragon)'),
    ('Sexuality / nudity / crude language', 'No / No / No'),
    ('Controlled substances', 'Tobacco reference only (a cigarette packet); no use'),
    ('Gambling', 'No'),
    ('Users interact or share content', 'No'),
    ('Shares location / digital purchases', 'No / No'),
    ('Unrestricted internet', 'No'),
]


def main():
    full_text = open(LISTING).read()
    s = sections(full_text)
    ios = s['Apple App Store (iPhone and iPad)']
    mac = s['Mac App Store']
    play = s['Google Play']
    ms = s['Microsoft Store']
    review_notes = ios['App Review'][0][2]
    labels_ios = ['Name', 'Subtitle', 'Promotional text', 'Keywords', 'Description', "What's new"]

    for lang, key in (('en', 'English'), ('fr', 'Français')):
        name, asc_lang, play_lang, ms_lang = LANG_NAMES[lang]
        d = f'store/{lang}'
        app_info = [
            ('Bundle ID', BUNDLE),
            ('SKU', 'diamond'),
            ('Primary language', 'English (U.K.); add French as a localisation'),
            ('Category', 'Games > Adventure (secondary: Games > Puzzle)'),
            ('Price', 'Free (or your choice); no in-app purchases'),
            ('Support URL', SUPPORT),
            ('Privacy Policy URL', PRIVACY),
            ('Copyright', '© 2026 Paul F. Johnson'),
            ('App Privacy', 'Data Not Collected; no tracking'),
            ('Encryption', 'None (ITSAppUsesNonExemptEncryption is already false in Info.plist)'),
            ('Sign-in required', 'No (App Review Information: untick "Sign-in required")'),
            ('Contact', f'Paul F. Johnson, {EMAIL}'),
        ]

        # ---------------- App Store (iOS)
        fields = ios[key]
        t = heading(f'THE DIAMOND OF CURSED ISLAND - APP STORE (IPHONE AND IPAD) - {name.upper()}')
        t += f'App Store Connect > {TITLE["en"]} > iOS App > 1.0 > {asc_lang}\n\n'
        for label, (_, limit, body) in zip(labels_ios, fields):
            t += field(label, limit, body)
        t += files([
            f'iPhone, Dynamic Island medium screenshots (10, required): {d}/app-store/iphone-dynamic-island-medium-2622x1206/',
            f'iPhone, Dynamic Island large screenshots (10): {d}/app-store/iphone-dynamic-island-large-2868x1320/',
            f'iPad 13" screenshots (10): {d}/app-store/ipad-13in-2752x2064/',
            f'App previews: ~/Movies/The Diamond of Cursed Island/Cursed Island - iPhone app preview 1920x886 - {name}.mp4 '
            f'and Cursed Island - iPad app preview 1600x1200 - {name}.mp4',
            'App icon: comes from the build (store/en/app-store/icon-1024.png is the same picture)',
            f'Build: release/ios/Diamond.ipa (upload with Transporter; version {VERSION}, build {BUILD})',
        ])
        if lang == 'en':
            t += answers(app_info)
            t += answers(APPLE_AGE, 'AGE RATING')
            t += field('App Review notes', 4000, review_notes)
        else:
            t += 'App information, pricing, age rating, privacy answers and review notes: see store/en/app-store/UPLOAD.txt (they are set once, for every language).\n'
        write(lang, 'app-store', t)

        # ---------------- Mac App Store
        t = heading(f'THE DIAMOND OF CURSED ISLAND - MAC APP STORE - {name.upper()}')
        t += f'App Store Connect > {TITLE["en"]} > macOS App > 1.0 > {asc_lang}\n'
        t += 'Name, subtitle, promotional text and keywords are the same as on iOS.\n\n'
        for label, (_, limit, body) in zip(labels_ios, fields):
            if label in ('Description', "What's new"):
                continue
            t += field(label, limit, body)
        _, limit, body = mac[key][0]
        t += field('Description', limit, body)
        t += field("What's new", fields[5][1], fields[5][2])
        t += files([
            f'Screenshots (10): {d}/mac-app-store/screenshots-2880x1800/ (or screenshots-1440x900/)',
            f'App preview: ~/Movies/The Diamond of Cursed Island/Cursed Island - Mac app preview 1920x1080 - {name}.mp4',
            f'Build: release/macos/Diamond.pkg (upload with Transporter; version {VERSION}, build {BUILD})',
        ])
        if lang == 'en':
            t += answers(app_info + [('Age rating', 'Same answers as iOS (9+)'),
                                     ('Minimum macOS', '12.0; universal (Apple silicon and Intel)')])
            t += field('App Review notes', 4000, review_notes)
        else:
            t += 'App information, pricing, privacy answers and review notes: see store/en/mac-app-store/UPLOAD.txt.\n'
        write(lang, 'mac-app-store', t)

        # ---------------- Google Play
        t = heading(f'THE DIAMOND OF CURSED ISLAND - GOOGLE PLAY - {name.upper()}')
        t += f'Play Console > {TITLE["en"]} > Grow > Store presence > Main store listing > {play_lang}\n\n'
        for label, (_, limit, body) in zip(['App name', 'Short description', 'Full description'], play[key]):
            t += field(label, limit, body)
        t += files([
            f'App icon: {d}/google-play/icon-512.png',
            f'Feature graphic: {d}/google-play/feature-graphic-1024x500.png',
            f'Phone screenshots (8): {d}/google-play/phone-screenshots-1920x1080/',
            f'10-inch tablet screenshots (8): {d}/google-play/tablet-screenshots-2560x1600/ (also fine for 7-inch)',
            f'App bundle: release/android/{BUNDLE}-Signed.aab (version 1.0.0, code 1; target API 32)',
        ])
        if lang == 'en':
            t += answers([
                ('Package name', BUNDLE),
                ('App or game', 'Game; category Adventure'),
                ('Free or paid', 'Free'),
                ('Default language', 'English (United Kingdom) en-GB; add French (France) fr-FR'),
                ('App signing', 'Let Google manage the app signing key; this upload key: ~/keys/diamond-upload.jks (alias diamond)'),
                ('Privacy policy', PRIVACY),
                ('App access', 'All functionality available without special access'),
                ('Ads', 'No ads'),
                ('Target audience', '13 and over (or include younger ages if you prefer; nothing is collected)'),
                ('Data safety', 'Collects or shares required user data types: No. No data collected; no data shared'),
                ('News / COVID-19 / government / financial / health', 'No'),
                ('Contact email', EMAIL),
                ('Website', SUPPORT),
            ])
            t += answers(IARC, 'CONTENT RATING (IARC)')
        else:
            t += 'App content answers (privacy, ads, rating, data safety): see store/en/google-play/UPLOAD.txt.\n'
        write(lang, 'google-play', t)

        # ---------------- Microsoft Store (Partner Center needs every part below, every time)
        t = heading(f'THE DIAMOND OF CURSED ISLAND - MICROSOFT STORE - {name.upper()}')
        t += f'Partner Center > {TITLE["en"]} > Submission > Store listings > {ms_lang}\n\n'
        ms_labels = ['Product name', 'Short description', 'Description', 'Product features (one per box)',
                     'Search terms (one per box)', "What's new in this version", 'Notes for certification']
        for label, (_, limit, body) in zip(ms_labels, ms[key]):
            per_box = 'one per box' in label
            t += field(label, 200 if label.startswith('Product features') else 30 if per_box else limit, body, per_line=per_box)
        t += field('Short title', 50, 'Cursed Island' if lang == 'en' else "L'Île Maudite")
        t += files([
            f'Screenshots (10): {d}/microsoft-store/screenshots-3840x2160/ (or 1920x1080 / 1366x768)',
            f'16:9 Super hero art (no text): {d}/microsoft-store/super-hero-art-3840x2160.png (also 1920x1080)',
            f'1:1 Box art: {d}/microsoft-store/box-art-2160x2160.png',
            f'2:3 Poster art: {d}/microsoft-store/poster-art-1440x2160.png',
            f'App tile icon: {d}/microsoft-store/store-logo-300x300.png',
            'Packages: release/windows/Diamond-1.0.0-x64.msix and Diamond-1.0.0-arm64.msix',
        ])
        if lang == 'en':
            justification = re.search(r'Paste:\n```\n(.*?)\n```', full_text, re.S).group(1)
            t += heading('RESTRICTED CAPABILITIES', '-')
            t += 'Submission options > "Why does your app need these capabilities?" (runFullTrust is the only one declared):\n\n'
            t += justification + '\n\n'
            t += answers([
                ('Package identity', '49556nodoid.DiamondoftheCursedIsland'),
                ('Publisher display name', 'all-the-johnsons'),
                ('Category', 'Games > Adventure'),
                ('Pricing', 'Free; no in-app purchases'),
                ('Age ratings', 'IARC questionnaire: same answers as Google Play (below)'),
                ('Personal information', 'Not accessed, collected or transmitted'),
                ('Privacy policy URL', PRIVACY),
                ('Website', SUPPORT),
                ('Support contact', EMAIL),
                ('Copyright', '© 2026 Paul F. Johnson'),
                ('Input', 'Keyboard and mouse'),
                ('Display', 'Windowed and full screen; landscape'),
                ('Languages', 'en-gb and fr-fr (as declared in the package manifest)'),
            ])
            t += answers(IARC, 'CONTENT RATING (IARC)')
        else:
            t += 'Restricted capability justification, properties, pricing and age rating answers: see store/en/microsoft-store/UPLOAD.txt.\n'
        write(lang, 'microsoft-store', t)


if __name__ == '__main__':
    main()
