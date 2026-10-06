# Store listing: The Diamond of Cursed Island / Le Diamant de l'Île Maudite

Paste-ready sheets for each store and language are generated from this file into `store/<en|fr>/<store>/UPLOAD.txt` by `tools/make_upload_copy.py`.

Everything to paste into App Store Connect (iOS and Mac), Google Play Console and Microsoft Partner Center, in **English** and **French**. Every field is within its store's limit (checked by `tools/check_listing.py`). The screenshots and graphics are generated into `store/en/` and `store/fr/` by `tools/capture_all.sh`. The app preview videos (iPhone, iPad, Mac; English and French) are made by `tools/make_preview_videos.sh` and saved in `~/Movies/The Diamond of Cursed Island/`.

> **Before you submit:**
> - The game is an unofficial remake of *Le Diamant de l'Île Maudite*, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille, published by Loriciels. The island, the pictures, the sound and the code are all new; the story, the puzzles and the vocabulary follow the original. The title (in both languages) and the credit use the original's name and its authors' names, though. Stores can reject apps that use another party's name or IP without permission, so make sure you have the rights (or permission) to use the title before you publish. If not, rename the title in `Strings.cs`, `Directory.Build.props` and the platform name files.
> - Age rating: no blood and nothing graphic, but the player kills a tarantula, a cobra and a dragon (described in text), can die in many ways (a skeleton lies in a clearing), there is a ghost, and a packet of cigarettes (it hides a key; nobody smokes). The answers below give Apple 9+; the IARC questionnaire should give PEGI 7 to 12 / ESRB Everyone 10+.

---

## Shared details

| Field | Value |
|---|---|
| App name | The Diamond of Cursed Island (French: Le Diamant de l'Île Maudite) |
| Home-screen name | Cursed Island (French: L'Île Maudite) |
| Bundle ID (iOS, macOS) | `uk.co.allthejohnsons.diamond` |
| Package name (Android) | `uk.co.allthejohnsons.diamond` (min API 23, target API 37) |
| Android upload key | `~/keys/diamond-upload.jks`, alias `diamond`, password in Keychain ("Diamond Android upload keystore"), created by `tools/make_keystore.sh` |
| Windows package identity | `49556nodoid.DiamondoftheCursedIsland`, publisher display name `all-the-johnsons` |
| Provisioning profiles | iOS `rel-cursed` (App Store), `devel-cursed`; macOS `relcursedmac.provisionprofile` (App Store), `develcursedmac.provisionprofile` |
| Developer / seller | Paul F. Johnson |
| Copyright | © 2026 Paul F. Johnson |
| Category | Games, then Adventure (secondary: Puzzle) |
| Price | Free (or set your own) |
| Contains ads | No |
| In-app purchases | No |
| Languages | English, French |
| Support email | paul@all-the-johnsons.co.uk |
| Support URL | Host `docs/Diamond-Support.html` (copy in `~/Downloads`) and paste its URL here |
| Privacy policy URL | The support page's `#privacy` section (the policy is also in `docs/PRIVACY.md`) |
| Age rating | Apple 9+; PEGI 7 to 12; ESRB Everyone 10+ (see the questionnaires below) |
| Supported devices | iPhone, iPad, Android phones and tablets, Macs with Apple silicon or Intel (macOS 12 or later), Windows 10/11 PCs (x64 and Arm) |
| Orientation | Landscape only |

---

## Apple App Store (iPhone and iPad)

### English

**Name** (30 max)
```
The Diamond of Cursed Island
```

**Subtitle** (30 max)
```
The 1984 Oric adventure remade
```

**Promotional text** (170 max)
```
Shipwrecked on a cursed Pacific island: survive its jungle, volcano and tunnels, find the lost diamond and get out alive. A classic text adventure, now fully illustrated.
```

**Keywords** (100 max)
```
text,adventure,parser,retro,oric,loriciels,1984,survival,treasure,jungle,volcano,classic,interactive
```

**Description** (4000 max)
```
A storm throws your boat onto the reefs of a cursed island in the Pacific. All you have is the journal of Steven Smith, an explorer who came here in 1934 looking for a priceless diamond hidden by a vanished civilisation, and never left. Find the diamond, and get off the island alive.

A CLASSIC ADVENTURE, REMADE
The Diamond of Cursed Island is a new, fully illustrated remake of Le Diamant de l'Île Maudite, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille, published by Loriciels. You see the island through your own eyes, and you act by typing orders, or by tapping words, as in the original.

TWO PARTS, 49 PLACES
- Part one: the island. A beach, a wreck, the jungle, a ruined tower, an explorer's hut, a feverish swamp, a smoking volcano and an old military hangar.
- Part two: the underground. A temple with a stone Buddha, a haunted gallery, an ancient well, a gorilla, a sage who has meditated for centuries, and a dragon.
- Every place can be seen in four directions: 196 painted views. Some things can only be seen from one place, facing one way.

SURVIVE
Hunger, thirst, fatigue, fever, injuries and the venom of tarantulas and scorpions add up, as in the original. Watch your FITNESS bar, eat, drink, look after yourself, and don't dawdle: time passes even while you think.

YOUR ORDERS, YOUR WAY
- Short form, as in 1984: words are recognised and completed from their first three or four letters, unknown words are erased with a beep, and you can chain up to 40 orders with "/".
- Long form: whole sentences, such as "pick up the coconut", "throw the club at the spider" or "take the rope and the bucket then go forward".
- On touch screens, the arrows move and turn you, and the WORDS list lets you tap a verb and then a noun. A keyboard works too.
- About 90 words in each language.

AND
- The game is saved after every order, with a checkpoint at the start of part two.
- Hall of Fame: score out of 100, then fewest moves.
- Bach's Toccata in D minor on the title screen, as in the original.
- Play in English or French, and switch at any time.

No ads, no tracking and no internet connection needed.

An unofficial remake by PFJ, with respect and gratitude to the original authors, Bertrand d'Armagnac and Frédéric Baille (Loriciels, 1984).
```

**What's new** (4000 max)
```
First release.
```

### Français

**Nom** (30 max)
```
Le Diamant de l'Île Maudite
```

**Sous-titre** (30 max)
```
L'aventure Oric de 1984 revit
```

**Texte promotionnel** (170 max)
```
Naufragé sur une île maudite du Pacifique : survivez à sa jungle, son volcan et ses souterrains, trouvez le diamant et repartez vivant. Le grand classique, illustré.
```

**Mots-clés** (100 max)
```
aventure,texte,rétro,oric,loriciels,1984,survie,trésor,jungle,volcan,naufrage,classique,interactive
```

**Description** (4000 max)
```
Une tempête jette votre bateau sur les récifs d'une île maudite du Pacifique. Pour tout bagage, vous avez le journal de Steven Smith, un explorateur venu ici en 1934 chercher un diamant d'une valeur inestimable, caché par une civilisation disparue. Il n'est jamais reparti. Trouvez le diamant, et quittez l'île vivant.

LE RETOUR D'UN CLASSIQUE
Le Diamant de l'Île Maudite est un remake entièrement illustré du jeu d'aventure Oric de 1984 de Bertrand d'Armagnac et Frédéric Baille, édité par Loriciels. Vous voyez l'île par vos propres yeux et vous agissez en tapant vos ordres, ou en touchant des mots, comme dans l'original.

DEUX PARTIES, 49 LIEUX
- Première partie : l'île. Une plage, une épave, la jungle, une tour en ruine, la cabane d'un explorateur, un marais fiévreux, un volcan qui fume et un vieux hangar militaire.
- Deuxième partie : les souterrains. Un temple et son Bouddha de pierre, une galerie hantée, un puits très ancien, un gorille, un sage qui médite depuis des siècles, et un dragon.
- Chaque lieu se voit dans quatre directions : 196 vues peintes. Certains objets ne se voient que d'un seul endroit, dans une seule direction.

SURVIVEZ
La faim, la soif, la fatigue, la fièvre, les blessures et le venin des mygales et des scorpions s'additionnent, comme dans l'original. Surveillez votre FORME, mangez, buvez, soignez-vous, et ne traînez pas : le temps passe, même quand vous réfléchissez.

VOS ORDRES, À VOTRE FAÇON
- Forme courte, comme en 1984 : les mots sont reconnus et complétés dès leurs trois ou quatre premières lettres, un mot inconnu est effacé avec un bip, et vous pouvez enchaîner jusqu'à 40 ordres avec « / ».
- Forme longue : des phrases entières, comme « prends la noix de coco », « lance la massue sur la mygale » ou « prends la corde et le seau puis avance ».
- Sur écran tactile, les flèches vous font avancer et tourner, et la liste des MOTS vous permet de toucher un verbe puis un nom. Un clavier fonctionne aussi.
- Environ 90 mots dans chaque langue.

ET AUSSI
- La partie est sauvegardée à chaque ordre, avec un point de reprise au début de la deuxième partie.
- Tableau d'honneur : score sur 100, puis le moins de coups.
- La Toccata en ré mineur de Bach sur l'écran titre, comme dans l'original.
- Jouez en français ou en anglais, et changez quand vous voulez.

Sans publicité, sans pistage et sans connexion Internet.

Un remake non officiel par PFJ, avec tout le respect et la reconnaissance dus aux auteurs de l'original, Bertrand d'Armagnac et Frédéric Baille (Loriciels, 1984).
```

**Nouveautés** (4000 max)
```
Première version.
```

### App Review

Entered once, in English, under *App Review Information* for both the iOS and the Mac app.

**Notes** (4000 max)
```
The Diamond of Cursed Island is an offline, single-player text adventure with pictures: an unofficial remake of the 1984 Oric game Le Diamant de l'Île Maudite (Loriciels). No account, sign-in, network connection or purchase is needed; all content is available immediately. The game collects no data.

HOW TO PLAY
Tap the title, choose NEW GAME, and read the two pages of the explorer's journal. You see the island in front of you and act by giving orders. On iPhone and iPad, the arrow buttons move forward and turn; WORDS opens a list of verbs, then nouns: tap a verb, then a noun, and the order is given. A hardware keyboard also works: type an order and press Return. On the Mac, type orders and press Return; with an empty line the arrow keys move and turn. Esc opens the menu, F11 toggles full screen.

PARSER SETTING (menu: COMMANDS)
- SHORT FORM (default, as in 1984): words are recognised from their first 3 or 4 letters and completed as you type ("THR CLU" becomes "THROW CLUB"); unknown words are erased with a beep; up to 40 orders can be chained with "/".
- LONG FORM: whole sentences, e.g. "pick up the coconut", "throw the club at the spider", "take the rope and the bucket then go forward".
The menu also has LANGUAGE (English/French), VOLUME, INSTRUCTIONS and HALL OF FAME.

SURVIVAL
Hunger, thirst, fatigue, fever, injuries and venom add up; the FITNESS bar shows what is left and STATUS explains it. Time passes even if you do nothing. The game is saved after every order; the start of part two is a checkpoint (menu: RESTART PART TWO).

SOLUTION IN BRIEF
Part 1 (the island): take the club on the beach. In the tower, THROW CLUB at the tarantula and take the torch. In the hut, OPEN DRAWER, take and OPEN the CIGARETTES packet (a key is inside), take the knife and the gourd. Take the bananas in the grove. Through the swamp to the clearing: CUT PLANT, take the kit, tonic, serum and aspirin, SWALLOW ASPIRIN. CLIMB the PALM, take and EAT the COCONUT. On the narrow path THROW KNIFE at the cobra and take the knife back. By the skeleton take and WEAR BOOTS. DRINK at the spring and FILL GOURD. LIGHT TORCH at the crater. Cross the rocks to the hangar: take the shovel, DIG at the corner, OPEN TRAPDOOR, DESCEND, OPEN GRILLE (with the key).
Part 2 (the underground): take the rope; PRESS EYE of the Buddha, take and WEAR the HELMET in the secret chamber; take the hammer and the bucket; at the well TIE BUCKET, LOWER BUCKET, RAISE BUCKET, DRINK WATER. BREAK the rusty GRILLE, go past the ghost, take the sabre and THROW SABRE at the gorilla, then fetch it from its den. ASK SAGE, OPEN DOOR, BEHEAD DRAGON, take the DIAMOND, take the jerrycan on the ramp, and in the hangar PRESS BUTTON, FILL FUEL, CLIMB HELICOPTER, FLY. That scores 100/100.
```

**Screenshots:** `store/<en|fr>/app-store/iphone-6.9in-2868x1320/` (also `iphone-6.5in-2688x1242/`) and `ipad-13in-2752x2064/`, 10 each, landscape.
**App previews:** none.
**Icon:** `store/en/app-store/icon-1024.png`.

---

## Mac App Store

Use the same name, subtitle, promotional text and keywords as iOS, in each language.

### English

**Description** (4000 max)
```
A storm throws your boat onto the reefs of a cursed island in the Pacific. All you have is the journal of Steven Smith, an explorer who came here in 1934 looking for a priceless diamond hidden by a vanished civilisation, and never left. Find the diamond, and get off the island alive.

A CLASSIC ADVENTURE, REMADE
The Diamond of Cursed Island is a new, fully illustrated remake of Le Diamant de l'Île Maudite, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille, published by Loriciels. You see the island through your own eyes, and you act by typing orders, as in the original.

TWO PARTS, 49 PLACES
- Part one: the island, with its beach, jungle, ruined tower, explorer's hut, swamp, volcano and old military hangar.
- Part two: the underground, with its temple and stone Buddha, haunted gallery, ancient well, gorilla, sage and dragon.
- Every place can be seen in four directions: 196 painted views.

SURVIVE
Hunger, thirst, fatigue, fever, injuries and venom add up, as in the original. Watch your FITNESS bar, and don't dawdle: time passes even while you think.

TYPE YOUR ORDERS
- Short form, as in 1984: words are recognised and completed from their first three or four letters, unknown words are erased with a beep, and up to 40 orders can be chained with "/".
- Long form: whole sentences, such as "throw the club at the spider" or "take the rope and the bucket then go forward".
- About 90 words in each language. The mouse can also pick words from the WORDS list.

CONTROLS
Type an order and press Return. With an empty line, the arrow keys move you forward and turn you. Up arrow while typing recalls the previous order; Page Up / Page Down or the mouse wheel scroll the text. Esc opens the menu, F11 toggles full screen, in a resizable window or full screen.

AND
Saved after every order, with a checkpoint at the start of part two. Hall of Fame. Bach's Toccata in D minor on the title screen, as in the original. In English and French.

No ads, no tracking and no internet connection needed.

An unofficial remake by PFJ, with respect and gratitude to the original authors, Bertrand d'Armagnac and Frédéric Baille (Loriciels, 1984).
```

### Français

**Description** (4000 max)
```
Une tempête jette votre bateau sur les récifs d'une île maudite du Pacifique. Pour tout bagage, vous avez le journal de Steven Smith, un explorateur venu ici en 1934 chercher un diamant d'une valeur inestimable, caché par une civilisation disparue. Il n'est jamais reparti. Trouvez le diamant, et quittez l'île vivant.

LE RETOUR D'UN CLASSIQUE
Le Diamant de l'Île Maudite est un remake entièrement illustré du jeu d'aventure Oric de 1984 de Bertrand d'Armagnac et Frédéric Baille, édité par Loriciels. Vous voyez l'île par vos propres yeux et vous agissez en tapant vos ordres, comme dans l'original.

DEUX PARTIES, 49 LIEUX
- Première partie : l'île, avec sa plage, sa jungle, sa tour en ruine, la cabane d'un explorateur, son marais, son volcan et un vieux hangar militaire.
- Deuxième partie : les souterrains, avec leur temple et son Bouddha de pierre, une galerie hantée, un puits très ancien, un gorille, un sage et un dragon.
- Chaque lieu se voit dans quatre directions : 196 vues peintes.

SURVIVEZ
La faim, la soif, la fatigue, la fièvre, les blessures et le venin s'additionnent, comme dans l'original. Surveillez votre FORME, et ne traînez pas : le temps passe, même quand vous réfléchissez.

TAPEZ VOS ORDRES
- Forme courte, comme en 1984 : les mots sont reconnus et complétés dès leurs trois ou quatre premières lettres, un mot inconnu est effacé avec un bip, et vous pouvez enchaîner jusqu'à 40 ordres avec « / ».
- Forme longue : des phrases entières, comme « lance la massue sur la mygale » ou « prends la corde et le seau puis avance ».
- Environ 90 mots dans chaque langue. La souris peut aussi choisir des mots dans la liste des MOTS.

COMMANDES
Tapez un ordre puis Entrée. Avec une ligne vide, les flèches vous font avancer et tourner. Flèche haut pendant la frappe : l'ordre précédent ; Page haut / Page bas ou la molette font défiler le texte. Échap ouvre le menu, F11 bascule le plein écran, en fenêtre redimensionnable ou en plein écran.

ET AUSSI
Sauvegarde à chaque ordre, avec un point de reprise au début de la deuxième partie. Tableau d'honneur. La Toccata en ré mineur de Bach sur l'écran titre, comme dans l'original. En français et en anglais.

Sans publicité, sans pistage et sans connexion Internet.

Un remake non officiel par PFJ, avec tout le respect et la reconnaissance dus aux auteurs de l'original, Bertrand d'Armagnac et Frédéric Baille (Loriciels, 1984).
```

**Screenshots:** `store/<en|fr>/mac-app-store/screenshots-2880x1800/` (or `screenshots-1440x900/`), 10.
**App preview:** none.
**Review notes:** the same as iOS (see *App Review* above).

---

## Google Play

### English

**App name** (30 max)
```
The Diamond of Cursed Island
```

**Short description** (80 max)
```
Shipwrecked on a cursed island: survive, find the lost diamond and escape alive.
```

**Full description** (4000 max)
```
A storm throws your boat onto the reefs of a cursed island in the Pacific. All you have is the journal of Steven Smith, an explorer who came here in 1934 looking for a priceless diamond hidden by a vanished civilisation, and never left. Find the diamond, and get off the island alive.

The Diamond of Cursed Island is a new, fully illustrated remake of Le Diamant de l'Île Maudite, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille, published by Loriciels. You see the island through your own eyes, and you act by giving orders, as in the original.

EXPLORE
• Part one: the island, with its beach, jungle, ruined tower, explorer's hut, swamp, volcano and old military hangar
• Part two: the underground, with a temple and its stone Buddha, a haunted gallery, an ancient well, a gorilla, a sage and a dragon
• 49 places, each seen in four directions: 196 painted views

SURVIVE
• Hunger, thirst, fatigue, fever, injuries and venom add up, as in the original
• Watch your FITNESS bar: time passes even while you think

GIVE YOUR ORDERS
• Tap the arrows to move and turn, and the WORDS list to pick a verb and then a noun
• Or type: short form as in 1984 (words completed from their first letters, up to 40 orders chained with "/"), or long form with whole sentences such as "throw the club at the spider"
• About 90 words in each language

AND
• Saved after every order, with a checkpoint at the start of part two
• Hall of Fame
• Bach's Toccata in D minor on the title screen, as in the original
• English and French, switchable at any time

No ads, no tracking and no internet connection needed.

An unofficial remake by PFJ, with respect and gratitude to the original authors, Bertrand d'Armagnac and Frédéric Baille (Loriciels, 1984).
```

### Français

**Nom de l'application** (30 max)
```
Le Diamant de l'Île Maudite
```

**Description courte** (80 max)
```
Naufragé sur une île maudite : survivez, trouvez le diamant et repartez vivant.
```

**Description complète** (4000 max)
```
Une tempête jette votre bateau sur les récifs d'une île maudite du Pacifique. Pour tout bagage, vous avez le journal de Steven Smith, un explorateur venu ici en 1934 chercher un diamant d'une valeur inestimable, caché par une civilisation disparue. Il n'est jamais reparti. Trouvez le diamant, et quittez l'île vivant.

Le Diamant de l'Île Maudite est un remake entièrement illustré du jeu d'aventure Oric de 1984 de Bertrand d'Armagnac et Frédéric Baille, édité par Loriciels. Vous voyez l'île par vos propres yeux et vous agissez en donnant des ordres, comme dans l'original.

EXPLOREZ
• Première partie : l'île, avec sa plage, sa jungle, sa tour en ruine, la cabane d'un explorateur, son marais, son volcan et un vieux hangar militaire
• Deuxième partie : les souterrains, avec un temple et son Bouddha de pierre, une galerie hantée, un puits très ancien, un gorille, un sage et un dragon
• 49 lieux, chacun vu dans quatre directions : 196 vues peintes

SURVIVEZ
• La faim, la soif, la fatigue, la fièvre, les blessures et le venin s'additionnent, comme dans l'original
• Surveillez votre FORME : le temps passe, même quand vous réfléchissez

DONNEZ VOS ORDRES
• Touchez les flèches pour avancer et tourner, et la liste des MOTS pour choisir un verbe puis un nom
• Ou tapez : forme courte comme en 1984 (mots complétés dès leurs premières lettres, jusqu'à 40 ordres enchaînés avec « / »), ou forme longue avec des phrases entières comme « lance la massue sur la mygale »
• Environ 90 mots dans chaque langue

ET AUSSI
• Sauvegarde à chaque ordre, avec un point de reprise au début de la deuxième partie
• Tableau d'honneur
• La Toccata en ré mineur de Bach sur l'écran titre, comme dans l'original
• Français et anglais, à changer quand vous voulez

Sans publicité, sans pistage et sans connexion Internet.

Un remake non officiel par PFJ, avec tout le respect et la reconnaissance dus aux auteurs de l'original, Bertrand d'Armagnac et Frédéric Baille (Loriciels, 1984).
```

**Screenshots:** `store/<en|fr>/google-play/phone-screenshots-1920x1080/` and `tablet-screenshots-2560x1600/`, 8 each.
**Graphics:** `store/<en|fr>/google-play/icon-512.png`, `feature-graphic-1024x500.png`.
**Data safety:** no data collected or shared (see the questionnaires below).
**App access:** all functionality is available without special access.

---

## Microsoft Store

Partner Center asks for more than the other stores. Everything below is needed for every submission.

### English

**Product name** (256 max)
```
The Diamond of Cursed Island
```

**Short description** (1000 max)
```
An illustrated remake of Le Diamant de l'Île Maudite, the 1984 Oric adventure. Shipwrecked on a cursed Pacific island, you must survive its jungle, volcano and tunnels, find the diamond hidden by a vanished civilisation, and escape alive. Type your orders as in 1984, or in whole sentences. In English and French.
```

**Description** (10000 max)
```
A storm throws your boat onto the reefs of a cursed island in the Pacific. All you have is the journal of Steven Smith, an explorer who came here in 1934 looking for a priceless diamond hidden by a vanished civilisation, and never left. Find the diamond, and get off the island alive.

The Diamond of Cursed Island is a new, fully illustrated remake of Le Diamant de l'Île Maudite, the 1984 Oric adventure by Bertrand d'Armagnac and Frédéric Baille, published by Loriciels. You see the island through your own eyes, and you act by typing orders, as in the original.

Part one is the island: a beach, the jungle, a ruined tower, an explorer's hut, a feverish swamp, a smoking volcano and an old military hangar. Part two is the underground: a temple with a stone Buddha, a haunted gallery, an ancient well, a gorilla, a sage and a dragon. There are 49 places, each seen in four directions: 196 painted views.

Hunger, thirst, fatigue, fever, injuries and venom add up, as in the original. Watch your FITNESS bar, and don't dawdle: time passes even while you think.

Choose how you give orders. In the short form, as in 1984, words are recognised and completed from their first three or four letters, unknown words are erased with a beep, and up to 40 orders can be chained with "/". In the long form you type whole sentences, such as "throw the club at the spider" or "take the rope and the bucket then go forward". About 90 words in each language.

Type an order and press Enter. With an empty line, the arrow keys move you forward and turn you. Esc opens the menu, F11 toggles full screen. The mouse can pick words from the WORDS list.

The game is saved after every order, with a checkpoint at the start of part two. Hall of Fame. Bach's Toccata in D minor on the title screen, as in the original.

In English and French. No ads, no tracking and no internet connection needed.

An unofficial remake by PFJ, with respect and gratitude to the original authors, Bertrand d'Armagnac and Frédéric Baille (Loriciels, 1984).
```

**Product features** (20 max, 200 characters each)
```
An illustrated remake of the 1984 Oric adventure Le Diamant de l'Île Maudite
49 places on the island and beneath it, each seen in four directions: 196 painted views
Survive hunger, thirst, fatigue, fever, injuries and venom
Short form orders as in 1984, or whole sentences in the long form
About 90 words in each language; up to 40 orders chained with "/"
Saved after every order, with a checkpoint at the start of part two
Hall of Fame: score out of 100, then fewest moves
High-resolution pictures in a window or full screen
English and French
```

**Search terms** (7 max, 30 characters each)
```
text adventure
retro
oric
treasure island
survival
loriciels
diamant île maudite
```

**What's new in this version** (1500 max)
```
First release.
```

**Notes for certification** (2000 max)
```
Offline single-player text adventure with pictures; no account, sign-in, network or purchase needed. Press SPACE on the title, choose NEW GAME, read the journal. Type orders and press Enter; with an empty line the arrow keys move and turn; Esc: menu; F11: full screen. Menu COMMANDS switches SHORT FORM (1984: words completed from 3-4 letters, unknown words erased with a beep, orders chained with "/") and LONG FORM (sentences: "throw the club at the spider"). Saved after every order; checkpoint at part two.
Solution: take club; in tower THROW CLUB, take torch; in hut OPEN DRAWER, take and OPEN CIGARETTES (key), take knife and gourd; take bananas; in clearing CUT PLANT, take kit, tonic, serum, aspirin, SWALLOW ASPIRIN; CLIMB PALM, take and EAT COCONUT; THROW KNIFE at cobra, take it back; take and WEAR BOOTS; DRINK, FILL GOURD at the spring; LIGHT TORCH at crater; at hangar take shovel, DIG, OPEN TRAPDOOR, DESCEND, OPEN GRILLE. Part 2: take rope; PRESS EYE of Buddha, take and WEAR HELMET; take hammer, bucket; at well TIE BUCKET, LOWER BUCKET, RAISE BUCKET, DRINK; BREAK GRILLE; take sabre, THROW SABRE at gorilla, fetch it from the den; ASK SAGE, OPEN DOOR, BEHEAD DRAGON, take DIAMOND and jerrycan; in hangar PRESS BUTTON, FILL FUEL, CLIMB HELICOPTER, FLY.
```

### Français

**Nom du produit** (256 max)
```
Le Diamant de l'Île Maudite
```

**Description courte** (1000 max)
```
Un remake illustré du Diamant de l'Île Maudite, l'aventure Oric de 1984. Naufragé sur une île maudite du Pacifique, survivez à sa jungle, son volcan et ses souterrains, trouvez le diamant caché par une civilisation disparue et repartez vivant. Tapez vos ordres comme en 1984, ou en phrases entières. En français et en anglais.
```

**Description** (10000 max)
```
Une tempête jette votre bateau sur les récifs d'une île maudite du Pacifique. Pour tout bagage, vous avez le journal de Steven Smith, un explorateur venu ici en 1934 chercher un diamant d'une valeur inestimable, caché par une civilisation disparue. Il n'est jamais reparti. Trouvez le diamant, et quittez l'île vivant.

Le Diamant de l'Île Maudite est un remake entièrement illustré du jeu d'aventure Oric de 1984 de Bertrand d'Armagnac et Frédéric Baille, édité par Loriciels. Vous voyez l'île par vos propres yeux et vous agissez en tapant vos ordres, comme dans l'original.

La première partie se passe sur l'île : une plage, la jungle, une tour en ruine, la cabane d'un explorateur, un marais fiévreux, un volcan qui fume et un vieux hangar militaire. La deuxième, dans les souterrains : un temple et son Bouddha de pierre, une galerie hantée, un puits très ancien, un gorille, un sage et un dragon. 49 lieux, chacun vu dans quatre directions : 196 vues peintes.

La faim, la soif, la fatigue, la fièvre, les blessures et le venin s'additionnent, comme dans l'original. Surveillez votre FORME, et ne traînez pas : le temps passe, même quand vous réfléchissez.

Choisissez votre façon de donner les ordres. En forme courte, comme en 1984, les mots sont reconnus et complétés dès leurs trois ou quatre premières lettres, un mot inconnu est effacé avec un bip, et vous pouvez enchaîner jusqu'à 40 ordres avec « / ». En forme longue, vous tapez des phrases entières, comme « lance la massue sur la mygale » ou « prends la corde et le seau puis avance ». Environ 90 mots dans chaque langue.

Tapez un ordre puis Entrée. Avec une ligne vide, les flèches vous font avancer et tourner. Échap ouvre le menu, F11 bascule le plein écran. La souris peut choisir des mots dans la liste des MOTS.

La partie est sauvegardée à chaque ordre, avec un point de reprise au début de la deuxième partie. Tableau d'honneur. La Toccata en ré mineur de Bach sur l'écran titre, comme dans l'original.

En français et en anglais. Sans publicité, sans pistage et sans connexion Internet.

Un remake non officiel par PFJ, avec tout le respect et la reconnaissance dus aux auteurs de l'original, Bertrand d'Armagnac et Frédéric Baille (Loriciels, 1984).
```

**Fonctionnalités** (20 max, 200 characters each)
```
Un remake illustré du jeu d'aventure Oric de 1984 Le Diamant de l'Île Maudite
49 lieux sur l'île et sous la terre, chacun vu dans quatre directions : 196 vues peintes
Survivez à la faim, la soif, la fatigue, la fièvre, les blessures et le venin
Ordres en forme courte comme en 1984, ou en phrases entières en forme longue
Environ 90 mots dans chaque langue ; jusqu'à 40 ordres enchaînés avec « / »
Sauvegarde à chaque ordre, avec un point de reprise au début de la deuxième partie
Tableau d'honneur : score sur 100, puis le moins de coups
Images haute résolution, en fenêtre ou en plein écran
Français et anglais
```

**Termes de recherche** (7 max, 30 characters each)
```
aventure textuelle
rétro
oric
île au trésor
survie
loriciels
diamant île maudite
```

**Nouveautés de cette version** (1500 max)
```
Première version.
```

**Remarques pour la certification** (2000 max)
```
Aventure textuelle illustrée, hors ligne, pour un joueur ; aucun compte, connexion, réseau ou achat nécessaire. ESPACE sur le titre, NOUVELLE PARTIE, puis lisez le journal. Tapez les ordres puis Entrée ; ligne vide : les flèches font avancer et tourner ; Échap : menu ; F11 : plein écran. Le menu COMMANDES choisit la FORME COURTE (1984 : mots complétés dès 3-4 lettres, mot inconnu effacé avec un bip, ordres enchaînés avec « / ») ou la FORME LONGUE (phrases : « lance la massue sur la mygale »). Sauvegarde à chaque ordre ; point de reprise en 2e partie.
Solution : PRENDS MASSUE ; dans la tour LANCE MASSUE, PRENDS TORCHE ; dans la cabane OUVRE TIROIR, PRENDS et OUVRE PAQUET (clef), PRENDS COUTEAU et GOURDE ; PRENDS BANANES ; dans la clairière COUPE PLANTE, PRENDS TROUSSE, FORTIFIANT, SERUM, CACHET, AVALE CACHET ; MONTE COCOTIER, PRENDS et MANGE NOIX ; LANCE COUTEAU sur le cobra, reprends-le ; PRENDS et METS BOTTES ; BOIS, REMPLIS GOURDE à la source ; ALLUME TORCHE au cratère ; au hangar PRENDS PELLE, CREUSE, OUVRE TRAPPE, DESCENDS, OUVRE GRILLE. 2e partie : PRENDS CORDE ; APPUIE OEIL du Bouddha, PRENDS et METS CASQUE ; PRENDS MARTEAU, SEAU ; au puits ATTACHE SEAU, DESCENDS SEAU, REMONTE SEAU, BOIS ; BRISE GRILLE ; PRENDS SABRE, LANCE SABRE sur le gorille, reprends-le dans sa tanière ; INTERROGE SAGE, OUVRE PORTE, DECAPITE DRAGON, PRENDS DIAMANT et BIDON ; au hangar APPUIE BOUTON, FAIS PLEIN, MONTE HELICO, DECOLLE.
```

**Screenshots:** captured by the Windows (DirectX) build running in Parallels: `store/<en|fr>/microsoft-store/screenshots-3840x2160/` (4K), `screenshots-1920x1080/` and `screenshots-1366x768/`, 10 each.

**Store art** (in `store/<en|fr>/microsoft-store/`)

| Partner Center slot | File | Notes |
|---|---|---|
| 16:9 Super hero art | `super-hero-art-3840x2160.png` (also `-1920x1080`) | No title text, as the Store overlays its own; the island at dusk with the diamond, the lower left kept clear |
| 1:1 Box art | `box-art-2160x2160.png` | The title screen |
| 2:3 Poster art | `poster-art-1440x2160.png` | The title screen |
| App tile icon | `store-logo-300x300.png` | |

All of them are built from the game's own artwork by `tools/make_store_assets.py`.

**Packages:** `release/windows/Diamond-1.0.0-x64.msix` and `Diamond-1.0.0-arm64.msix` (built by `tools/build_windows.sh`; the Store signs them).

**Restricted capabilities** (Partner Center › Submission options › *Why does your app need these capabilities?*)

The package declares one restricted capability, `runFullTrust` (in `Diamond.WindowsDX/Windows/AppxManifest.xml`). No other restricted or general capabilities are declared: not `internetClient`, file system access, webcam, microphone or location. Paste:
```
runFullTrust: The Diamond of Cursed Island is a packaged desktop (Win32) game, built with .NET 10 and MonoGame and rendered with DirectX 11. Every packaged Win32 desktop app needs runFullTrust to start its executable (Windows.FullTrustApplication entry point). The game uses it only to run its own process. It does not use the internet, other apps or processes, the user's documents or system settings. It reads the keyboard and mouse, draws with DirectX, plays sound with XAudio, and saves its settings, saved game and Hall of Fame in its own app data folder.
```

**Other Partner Center answers**

| Field | Answer |
|---|---|
| Category | Games › Adventure (subcategory: Puzzle & trivia, if asked) |
| Pricing | Free |
| Age ratings | IARC questionnaire: same answers as Google Play (see below) |
| Input | Keyboard and mouse (touch works on touch screens) |
| Display modes | Windowed and full screen; landscape |
| Privacy policy URL | The support page's `#privacy` section |
| Support contact | paul@all-the-johnsons.co.uk |
| Languages | English (United Kingdom) en-gb and French (France) fr-fr, as in the package manifest |

---

## Age rating questionnaires

What the game contains: text descriptions, with still pictures, of throwing a club at a giant tarantula ("the tarantula is crushed"), throwing a knife at a cobra ("slices off the cobra's head"), and beheading a dragon with a sabre ("the beast crashes to the ground"). No blood is shown. The player can die (eaten by the dragon, blinded by the cobra, a booby-trapped idol, exhaustion, venom, fever); a skeleton lies in a clearing and a ghost haunts a gallery. A packet of French cigarettes is found in a hut ("Smoking kills"): it is opened to find a key, and nobody smokes. Medicines (aspirin, a tonic, an anti-venom serum, a bandage) are fictional game items. No sexual content, profanity, alcohol, drugs, gambling, user-generated content, chat, ads, purchases or web access.

**Apple (App Store Connect › Age Rating)**

| Question | Answer |
|---|---|
| Parental controls / age assurance | No / No |
| Unrestricted web access | No |
| User-generated content | No |
| Messaging and chat | No |
| Advertising | No |
| Profanity or crude humour | None |
| Horror or fear themes | Infrequent/Mild |
| Alcohol, tobacco or drug use or references | Infrequent/Mild (a cigarette packet) |
| Medical or treatment information | None |
| Health or wellness topics | No |
| Sexual content or nudity / graphic sexual content | None / None |
| Cartoon or fantasy violence | Infrequent/Mild |
| Realistic violence | None |
| Prolonged graphic or sadistic realistic violence | None |
| Guns or other weapons | Infrequent/Mild (a club, a knife and a sabre are thrown or used; a rusty machine gun is a trap and is never fired at anyone) |
| Simulated gambling / contests / loot boxes | None / No / No |
| Result | 9+ |

**IARC (Google Play and Microsoft Store)**

| Question | Answer |
|---|---|
| Category | Game |
| Violence | Yes: fantasy violence against animals and creatures, described in text; no blood, no gore, no violence against humans |
| Fear | Yes: mild (a ghost, a skeleton, a dragon) |
| Sexuality, nudity | No |
| Language (crude or profane) | No |
| Controlled substances | Tobacco reference only (a cigarette packet); no use |
| Gambling (real or simulated) | No |
| Users interact or share content | No |
| Shares the user's location | No |
| Digital purchases | No |
| Unrestricted internet | No |

## Privacy and data safety answers

The game has no network code: no ads, analytics, crash reporting, accounts or tracking. It keeps four small files in its private app storage on the device: the settings (language, command form, volume), the saved game, the part two checkpoint and the Hall of Fame (names typed by the player, scores and moves). Nothing leaves the device.

| Store | Question | Answer |
|---|---|---|
| Apple | App Privacy › Data collection | Data Not Collected |
| Apple | Tracking | No |
| Apple | Export compliance | No encryption (`ITSAppUsesNonExemptEncryption` is false in Info.plist) |
| Google Play | Does your app collect or share any of the required user data types? | No |
| Google Play | Data safety summary | No data collected; no data shared |
| Google Play | Ads | No ads |
| Google Play | Target audience | 13 and over (or include younger ages if you prefer; nothing is collected) |
| Google Play | News app / COVID-19 / government / financial / health app | No |
| Microsoft | Does the product access, collect or transmit personal information? | No |
| All | Privacy policy URL | The support page's `#privacy` section |
