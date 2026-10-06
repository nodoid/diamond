# The Diamond of Cursed Island (Le Diamant de l'Île Maudite)

An illustrated MonoGame remake of **Le Diamant de l'Île Maudite**, the 1984 Oric adventure by
Bertrand d'Armagnac and Frédéric Baille (Loriciels), for Android, iOS, macOS and Windows, in
**English and French**.

A storm throws your boat onto the reefs of a cursed Pacific island. Steven Smith's 1934 journal
tells of a priceless diamond hidden by a vanished civilisation. Part one is the island's surface
(the beach, the jungle, a ruined tower, an explorer's hut, a swamp, the volcano and an old military
hangar); part two is the underground (a temple with a stone Buddha, a haunted gallery, a well, a
gorilla, a sage and a dragon). Survive hunger, thirst, fatigue, fever, injuries and venom, take the
diamond and escape by helicopter.

An unofficial remake by PFJ, with respect to the original authors. Released under the
[DILLIGAF License](LICENSE).

## How it plays

- **The island:** 49 places, each seen in four directions (196 first-person views). You act by
  giving orders: about 90 words of vocabulary in each language (`Engine/Vocabulary.cs`), parsed by
  `Engine/Parser.cs` and carried out by `Engine/Adventure.cs`; the map and the objects are in
  `World/Island.cs`.
- **Survival:** hunger, thirst, fatigue, fever, injuries and the tarantula's and scorpions' venom
  add up as in the original's BASIC (`Engine/Health.cs`); the FITNESS bar shows what is left, and
  time passes even when you don't act.
- **Saving:** the game is saved after every order, and the start of part two is a checkpoint (the
  original required saving between the parts). The Hall of Fame ranks scores out of 100, then the
  fewest moves.
- **Pictures:** painted backgrounds (`tools/make_backgrounds.py`) and sprites
  (`tools/make_sprites.py`), all generated in Python and embedded in `Diamond.Core/Art`; see
  [`art/ART_SPEC.md`](art/ART_SPEC.md). Text uses the Oric ROM font with added French accents.
- **Sound:** square waves and noise in the style of the Oric's AY-3-8912 (`Audio/Synth.cs`); the
  title plays Bach's Toccata in D minor, as the original did.

## Parser modes

A player setting (menu: *Commands*), saved with the other settings:

| | Short form (default, as in 1984) | Long form |
|---|---|---|
| Words | Recognised and completed from their first 3-4 letters (`THR CLU` → `THROW CLUB`) | Whole words, other verb forms (`PRENDRE`, `PRENEZ`), synonyms and filler words (`PLEASE`, `JE VEUX`) |
| Unknown words | Erased with a beep as you type | Reported after Enter |
| Chaining | Up to 40 orders separated by `/` | `/`, commas, `AND`, `THEN`, `ET`, `PUIS` |
| Example | `LANCE MASS` / `THROW CLUB` | "throw the club at the spider", "take the rope and the bucket then go forward" |

## Languages

All screen text is in `Diamond.Core/Localization/Strings.cs`; the adventure's own messages are in
`Adventure.cs` and `Island.cs`, French first, as in the original. The first run follows the device
language; the menu switches at any time, and the choice is saved. The home-screen name is
localised too: "Cursed Island" / "L'Île Maudite" (iOS `InfoPlist.strings`, Android `values-fr`,
Windows manifest).

## Projects

| Project | Target |
|---|---|
| `Diamond.Core` | The whole game (net10.0): island, parser, rules, renderer, scenes, input, audio, capture mode |
| `Diamond.Android` | Android 6+ (API 23), targets API 32 |
| `Diamond.iOS` | iOS 15+ (iPhone and iPad, landscape) |
| `Diamond.DesktopGL` | macOS 12+ (also runs on Linux and Windows) |
| `Diamond.WindowsDX` | Windows (DirectX), packaged as MSIX for the Microsoft Store |
| `Diamond.Tests` | xUnit tests: parser, vocabulary, island, sessions, art, and a full walkthrough proving the game can be won with 100/100 |

Identifiers:
- Bundle ID (iOS and macOS) and Android package: `uk.co.allthejohnsons.diamond`
- Windows identity: `49556nodoid.DiamondoftheCursedIsland`, publisher display name `all-the-johnsons`
- Profiles (read from `~/Downloads`, never committed): iOS `relcursed.mobileprovision` /
  `develcursed.mobileprovision` (profiles `rel-cursed` / `devel-cursed`), macOS
  `relcursedmac.provisionprofile` / `develcursedmac.provisionprofile`
- Android upload key: `~/keys/diamond-upload.jks` (alias `diamond`), created once by
  `tools/make_keystore.sh`, with its password in the Keychain ("Diamond Android upload keystore")

## Controls

| | Desktop | Phone / tablet |
|---|---|---|
| Give an order | Type it, then `Enter` | `WORDS`, then a verb, then a noun (or type on a keyboard) |
| Forward / turn | With an empty line: `↑`, `←` `→`, `↓` (turn round) | The arrow buttons |
| Previous order | `↑` while typing | |
| Scroll the text | `Page Up` / `Page Down`, mouse wheel | Swipe the text |
| Menu | `Esc` | `MENU` / Back |
| Full screen | `F11` or `Alt`+`Enter` | Always |

The mouse can also use the on-screen buttons and the `WORDS` list.

## Build and run

```sh
dotnet test Diamond.Tests                    # unit tests
dotnet run --project Diamond.DesktopGL       # play on the Mac
python3 tools/make_backgrounds.py            # repaint the backgrounds
python3 tools/make_sprites.py                # redraw the sprites (and the icon masters)
python3 art/make_icons.py                    # regenerate every platform icon
```

Release builds go to `release/` (git-ignored):

```sh
tools/build_desktop.sh           # macOS universal .app + App Store .pkg   (tools/build_desktop.sh dev: development build)
tools/build_release.sh           # Android .aab/.apk (needs ~/keys/diamond-upload.jks) and the iOS .ipa
tools/build_release.sh ios       # only iOS          (tools/build_release.sh android: only Android)
tools/build_windows.sh           # Windows x64 + arm64 .msix/.zip, built and tested in the Parallels "Windows 11" VM
```

## Store assets

The listing copy for every store, in English and French, with the age rating, privacy and review
answers, is in [`docs/LISTING.md`](docs/LISTING.md) (`python3 tools/check_listing.py` checks the
limits); the privacy policy is [`docs/PRIVACY.md`](docs/PRIVACY.md); the support page (English, with
the privacy policy) is `docs/Diamond-Support.html` (`python3 tools/make_support_page.py [capture-dir]`
rebuilds it and copies it to `~/Downloads`). `python3 tools/make_upload_copy.py` writes a
paste-ready `UPLOAD.txt` for each store and language into `store/`. Screenshots and graphics are
generated into `store/en` and `store/fr` (git-ignored):

```sh
tools/build_windows.sh capture   # Microsoft Store stills from the Windows build (both languages)
tools/capture_all.sh [dir]       # every other capture, the store images, the support page and the upload sheets
```

Capture mode (`dotnet <bin>/Diamond.dll --capture <dir> [--mobile] [--lang fr|en] [--scale n]`)
plays the walkthrough on autopilot, saves 20 stills (`01-title` to `20-instructions`, 2400 x 2240
at the default `--scale 10`) into `<dir>/stills`, and quits. `--mobile` shows the touch layout.
`tools/make_store_assets.py` fits them to every store's sizes over a blurred copy of themselves
and paints the text-free Microsoft Store hero art from the title backdrop and the diamond. There are
no app preview videos.

## Licence

The Diamond of Cursed Island code, artwork, tools and documentation are released under the
**[DILLIGAF License](LICENSE)**. The licence can't cover what isn't ours: the original
*Le Diamant de l'Île Maudite* game, its name, story and puzzles (by Bertrand d'Armagnac and
Frédéric Baille, published by Loriciels), the Oric ROM font, and third-party packages such as
MonoGame, which keep their own licences. Bach's Toccata is in the public domain.
