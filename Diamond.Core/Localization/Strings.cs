using System;
using System.Collections.Generic;
using System.Text;
using Diamond.Core.Engine;

namespace Diamond.Core.Localization;

public enum Language
{
    English,
    French,
}

/// <summary>A piece of text in both languages. <see cref="ToString"/> gives the current one.</summary>
public readonly record struct Loc(string Fr, string En)
{
    public string Get(Language language) => language == Language.French ? Fr : En;

    public override string ToString() => Get(Strings.Current);
}

/// <summary>
/// The text of the screens around the adventure, in the original French and in English (the
/// adventure's own messages are in <see cref="Adventure"/> and <see cref="World.Island"/>).
/// Accented letters use the extra glyphs in <see cref="Oric.OricFont"/>.
/// </summary>
public static class Strings
{
    public static Language Current { get; set; } = Language.English;

    /// <summary>Picks the language for a first run from the device's two-letter language code.</summary>
    public static Language FromIso(string iso) =>
        string.Equals(iso, "fr", StringComparison.OrdinalIgnoreCase) ? Language.French : Language.English;

    public static string IsoCode(Language language) => language == Language.French ? "fr" : "en";

    private static string L(string fr, string en) => Current == Language.French ? fr : en;

    /// <summary>Splits text into lines of at most <paramref name="width"/> characters, at spaces.</summary>
    public static List<string> Wrap(string text, int width = 40)
    {
        var lines = new List<string>();
        foreach (var paragraph in (text ?? string.Empty).Split('\n'))
        {
            var line = new StringBuilder();
            foreach (var word in paragraph.Split(' ', StringSplitOptions.RemoveEmptyEntries))
            {
                var w = word;
                while (w.Length > width)
                {
                    if (line.Length > 0)
                    {
                        lines.Add(line.ToString());
                        line.Clear();
                    }
                    lines.Add(w[..width]);
                    w = w[width..];
                }
                if (line.Length > 0 && line.Length + 1 + w.Length > width)
                {
                    lines.Add(line.ToString());
                    line.Clear();
                }
                if (line.Length > 0)
                    line.Append(' ');
                line.Append(w);
            }
            lines.Add(line.ToString());
        }
        return lines;
    }

    // ---------------- title and credits ----------------
    public static string Title => L("LE DIAMANT DE L'ÎLE MAUDITE", "THE DIAMOND OF CURSED ISLAND");
    public static string TitleLine1 => L("LE DIAMANT", "THE DIAMOND");
    public static string TitleLine2 => L("DE L'ÎLE MAUDITE", "OF CURSED ISLAND");
    public static string Subtitle => L("THE DIAMOND OF CURSED ISLAND", "LE DIAMANT DE L'ÎLE MAUDITE");
    public static string Credit => L("PAR PFJ", "BY PFJ");
    public static string BasedOn => L("D'APRÈS LE JEU LORICIELS DE 1984", "BASED ON THE 1984 LORICIELS GAME");
    public static string Authors => L("DE B. D'ARMAGNAC ET F. BAILLE", "BY B. D'ARMAGNAC AND F. BAILLE");
    public static string PressToStart(bool mobile) =>
        mobile ? L("TOUCHEZ L'ÉCRAN", "TAP THE SCREEN") : L("APPUYEZ SUR ESPACE", "PRESS SPACE");

    // ---------------- menu ----------------
    public static string NewGame => L("NOUVELLE PARTIE", "NEW GAME");
    public static string Continue => L("CONTINUER LA PARTIE", "CONTINUE GAME");
    public static string RestartPart2 => L("REPRENDRE LA 2E PARTIE", "RESTART PART TWO");
    public static string Instructions => L("INSTRUCTIONS", "INSTRUCTIONS");
    public static string HallOfFame => L("TABLEAU D'HONNEUR", "HALL OF FAME");
    public static string LanguageItem => L("LANGUE : FRANÇAIS", "LANGUAGE: ENGLISH");
    public static string ParserItem(ParserMode mode) => mode == ParserMode.Short
        ? L("COMMANDES : FORME COURTE", "COMMANDS: SHORT FORM")
        : L("COMMANDES : FORME LONGUE", "COMMANDS: LONG FORM");
    public static string ParserHint(ParserMode mode) => mode == ParserMode.Short
        ? L("COMME EN 1984 : PREN MASS", "AS IN 1984: TAKE CLUB")
        : L("PHRASES : PRENDS LA MASSUE", "SENTENCES: PICK UP THE CLUB");
    public static string Volume => L("VOLUME", "VOLUME");
    public static string Quit => L("QUITTER", "QUIT");
    public static string VolumeName(int level) => level switch
    {
        0 => L("COUPÉ", "OFF"),
        1 => L("FAIBLE", "LOW"),
        2 => L("MOYEN", "MEDIUM"),
        _ => L("FORT", "HIGH"),
    };

    // ---------------- game screen ----------------
    public static string Fitness => L("FORME", "FITNESS");
    public static string Words => L("MOTS", "WORDS");
    public static string Menu => L("MENU", "MENU");
    public static string Paused => L("PAUSE", "PAUSED");
    public static string Resume(bool mobile) => mobile ? L("TOUCHEZ", "TAP") : L("ESPACE", "SPACE");
    public static string TypeHere(bool mobile) =>
        mobile ? L("TOUCHEZ MOTS POUR AGIR", "TAP WORDS TO ACT") : L("TAPEZ VOS ORDRES...", "TYPE YOUR ORDERS...");
    public static string UnknownWord(string word) => L($"Je ne connais pas le mot « {word} ».", $"I don't know the word \"{word}\".");
    public static string NoVerb => L("Il manque un verbe : que faut-il faire ?", "There is no verb: what should I do?");
    public static string TooMany => L("Pas plus de 40 ordres à la fois !", "No more than 40 orders at once!");
    public static string TimePasses => L("Le temps passe...", "Time passes...");
    public static string ChooseVerb => L("CHOISISSEZ UN VERBE", "CHOOSE A VERB");
    public static string ChooseNoun(string verb) => L("CHOISISSEZ UN NOM POUR ", "CHOOSE A NOUN FOR ") + verb;
    public static string Alone => L("(SEUL)", "(ALONE)");
    public static string Back => L("RETOUR", "BACK");
    public static string More => L("SUITE", "MORE");
    public static string Saved => L("Partie sauvegardée.", "Game saved.");

    // ---------------- part two ----------------
    public static string PartTwo => L("DEUXIÈME PARTIE", "PART TWO");
    public static string Underground => L("LES SOUTERRAINS", "THE UNDERGROUND");
    public static string PartTwoText => L(
        "Vous voici dans les souterrains de l'île, là où errent d'étranges créatures. Quelque part dans " +
        "ces ténèbres dort le diamant... Votre progression a été sauvegardée : si vous mourez, vous pourrez " +
        "reprendre ici.",
        "You are in the tunnels beneath the island, where strange creatures roam. Somewhere in this " +
        "darkness the diamond sleeps... Your progress has been saved: if you die, you can start again " +
        "from here.");

    // ---------------- end of game ----------------
    public static string YouAreDead => L("VOUS ÊTES MORT", "YOU ARE DEAD");
    public static string Victory => L("VICTOIRE !", "VICTORY!");
    public static string Escaped => L("SAUVÉ... MAIS PAUVRE", "SAFE... BUT POOR");
    public static string ScoreLine(int score) => L($"SCORE : {score}/100", $"SCORE: {score}/100");
    public static string MovesLine(int moves) => L($"COUPS : {moves}", $"MOVES: {moves}");
    public static string Rank(int score) => score switch
    {
        >= 100 => L("DIGNE DE STEVEN SMITH !", "WORTHY OF STEVEN SMITH!"),
        >= 80 => L("BAROUDEUR", "SEASONED ADVENTURER"),
        >= 60 => L("EXPLORATEUR", "EXPLORER"),
        >= 40 => L("AVENTURIER", "ADVENTURER"),
        >= 20 => L("NAUFRAGÉ", "CASTAWAY"),
        _ => L("TOURISTE ÉGARÉ", "LOST TOURIST"),
    };
    public static string RetryPart2(bool mobile) =>
        mobile ? L("REPRENDRE LA 2E PARTIE", "RESTART PART TWO") : L("R : REPRENDRE LA 2E PARTIE", "R: RESTART PART TWO");
    public static string EndContinue(bool mobile) =>
        mobile ? L("TOUCHEZ POUR CONTINUER", "TAP TO CONTINUE") : L("ESPACE POUR CONTINUER", "SPACE TO CONTINUE");

    // ---------------- hall of fame ----------------
    public static string YourScore => L("VOTRE SCORE", "YOUR SCORE");
    public static string EnterName => L("ENTREZ VOTRE NOM", "ENTER YOUR NAME");
    public static string ChangeLetter(bool mobile) =>
        mobile ? L("TOUCHEZ < > POUR CHANGER", "TAP < > TO CHANGE LETTER") : L("FLÈCHES OU CLAVIER", "CURSOR KEYS OR TYPE");
    public static string AcceptLetter(bool mobile) =>
        mobile ? L("TOUCHEZ LA LETTRE POUR VALIDER", "TAP THE LETTER TO ACCEPT") : L("ESPACE POUR VALIDER", "SPACE TO ACCEPT");
    public static string EndMarkHint => L("< TERMINE LE NOM", "< ENDS THE NAME");
    public static string ScoreHeader => L("SCORE", "SCORE");
    public static string MovesHeader => L("COUPS", "MOVES");
    public static string NameHeader => L("NOM", "NAME");
    public static string PlayOrMenu(bool mobile) =>
        mobile ? L("TOUCHEZ POUR CONTINUER", "TAP TO CONTINUE") : L("ESPACE POUR CONTINUER", "SPACE TO CONTINUE");

    // ---------------- story and instructions ----------------
    public static string Page(int page, int pages) => $"{page}/{pages}";
    public static string NextPage(bool mobile) =>
        mobile ? L("TOUCHEZ POUR CONTINUER", "TAP TO CONTINUE") : L("ESPACE POUR CONTINUER", "SPACE TO CONTINUE");

    public static string StoryHeader => L("LE JOURNAL DE STEVEN SMITH", "THE JOURNAL OF STEVEN SMITH");

    public static string Story => L(
        "Ile du Pacifique, le 3 mars 1934.\n\n" +
        "Cette île est maudite. Rien n'y vit, sinon les bêtes les plus venimeuses. Elle fut pourtant " +
        "le berceau d'une civilisation disparue, qui a caché dans ses entrailles un diamant d'une " +
        "valeur inestimable.\n\n" +
        "Bien des explorateurs sont morts en le cherchant. Je suis peut-être le dernier... Celui qui " +
        "trouvera ces lignes saura ce qui l'attend.\n\n" +
        "La gloire ou la mort !",
        "A Pacific island, 3rd March 1934.\n\n" +
        "This island is cursed. Nothing lives here but the most venomous creatures. Yet it was the " +
        "cradle of a vanished civilisation, which hid deep inside it a diamond of priceless value.\n\n" +
        "Many explorers have died looking for it. Perhaps I am the last... Whoever finds these lines " +
        "will know what awaits them.\n\n" +
        "Glory or death!");

    public static string Story2 => L(
        "Cinquante ans plus tard, une tempête jette votre bateau sur les récifs de l'île maudite.\n\n" +
        "Vous voici seul sur la plage, avec pour tout bagage le journal de Steven Smith. Il vous faudra " +
        "survivre à la faim, à la soif, à la fatigue et aux bêtes de l'île, trouver le diamant... et " +
        "repartir vivant.",
        "Fifty years later, a storm throws your boat onto the reefs of the cursed island.\n\n" +
        "You are alone on the beach, with nothing but Steven Smith's journal. You will have to survive " +
        "hunger, thirst, fatigue and the island's creatures, find the diamond... and leave alive.");

    public static string[] InstructionHeaders => Current == Language.French
        ? ["LES ORDRES", "SE DÉPLACER", "SURVIVRE", "LES COMMANDES"]
        : ["GIVING ORDERS", "MOVING AROUND", "SURVIVAL", "THE CONTROLS"];

    public static string[] InstructionPages(bool mobile, ParserMode mode) =>
    [
        mode == ParserMode.Short
            ? L("Donnez vos ordres avec un verbe et un nom : PRENDS MASSUE, OUVRE TIROIR, LANCE COUTEAU...\n\n" +
                "Comme en 1984, le jeu reconnaît un mot dès ses trois ou quatre premières lettres et le complète " +
                "pour vous. Un mot inconnu est effacé avec un bip.\n\n" +
                "Enchaînez plusieurs ordres en les séparant par / : AVANCE/GAUCHE/PRENDS GOURDE.\n\n" +
                "Le menu propose aussi la forme longue, qui comprend des phrases entières.",
                "Give your orders with a verb and a noun: TAKE CLUB, OPEN DRAWER, THROW KNIFE...\n\n" +
                "As in 1984, the game recognises a word from its first three or four letters and completes it " +
                "for you. An unknown word is erased with a beep.\n\n" +
                "Chain several orders by separating them with /: FORWARD/LEFT/TAKE GOURD.\n\n" +
                "The menu also offers the long form, which understands whole sentences.")
            : L("Donnez vos ordres en toutes lettres : « prends la noix de coco », « lance la massue sur la " +
                "mygale », « tourne à gauche puis avance ».\n\n" +
                "Enchaînez les ordres avec ET, PUIS, une virgule ou / : « prends la corde et le seau ».\n\n" +
                "Les abréviations de la forme courte (PREN MASS) marchent toujours. Le menu permet de revenir à " +
                "la forme courte de 1984.",
                "Give your orders in full: \"pick up the coconut\", \"throw the club at the spider\", " +
                "\"turn left then go forward\".\n\n" +
                "Chain orders with AND, THEN, a comma or /: \"take the rope and the bucket\".\n\n" +
                "The short form's abbreviations (TAKE CLU) still work. The menu switches back to the 1984 " +
                "short form."),
        L("Vous voyez devant vous. AVANCE fait 50 mètres dans la direction où vous regardez ; GAUCHE, " +
          "DROITE et DEMI-TOUR vous font tourner.\n\n" +
          "Certains objets ne se voient que d'un seul endroit, dans une seule direction : regardez de tous " +
          "les côtés !\n\n" +
          "On ne prend que ce qu'on voit. Vous ne pouvez pas porter plus de huit objets.",
          "You see what is in front of you. FORWARD takes you 50 metres the way you are facing; LEFT, RIGHT " +
          "and BACK turn you round.\n\n" +
          "Some objects can only be seen from one place, facing one way: look in every direction!\n\n" +
          "You can only take what you can see. You cannot carry more than eight things."),
        L("La faim, la soif, la fatigue, la fièvre, les blessures et le venin s'additionnent. Quand votre " +
          "FORME tombe à zéro, vous mourez. BILAN vous dit ce qui ne va pas.\n\n" +
          "Mangez, buvez, soignez-vous... mais n'attendez pas trop : le temps passe, même quand vous " +
          "réfléchissez !\n\n" +
          "La partie est sauvegardée à chaque ordre, et au début de la deuxième partie.",
          "Hunger, thirst, fatigue, fever, injuries and venom add up. When your FITNESS falls to zero, you " +
          "die. STATUS tells you what is wrong.\n\n" +
          "Eat, drink, look after yourself... but don't wait too long: time passes even while you think!\n\n" +
          "The game is saved after every order, and at the start of part two."),
        mobile
            ? L("Les flèches en bas de l'écran vous font avancer et tourner.\n\n" +
                "MOTS ouvre la liste des verbes puis des noms : touchez un verbe, puis un nom, et l'ordre est " +
                "donné. Avec un clavier, vous pouvez aussi taper.\n\n" +
                "Glissez le doigt sur le texte pour le faire défiler. MENU ou Retour : le menu.",
                "The arrows at the bottom of the screen move and turn you.\n\n" +
                "WORDS opens the list of verbs and then nouns: tap a verb, then a noun, and the order is " +
                "given. With a keyboard you can type as well.\n\n" +
                "Swipe the text to scroll it. MENU or Back: the menu.")
            : L("Tapez vos ordres puis ENTRÉE. Ligne vide : les flèches font avancer (haut), tourner (gauche, " +
                "droite) et faire demi-tour (bas).\n\n" +
                "Flèche haut quand vous tapez : l'ordre précédent. Page haut / bas ou la molette : faire " +
                "défiler le texte.\n\n" +
                "La souris peut aussi utiliser les boutons et la liste de MOTS.\n\n" +
                "ÉCHAP : menu. F11 : plein écran.",
                "Type your orders, then ENTER. With an empty line the arrows move you forward (up), turn you " +
                "(left, right) and turn you round (down).\n\n" +
                "Up arrow while typing: the previous order. Page Up / Down or the mouse wheel: scroll the text.\n\n" +
                "The mouse can also use the buttons and the WORDS list.\n\n" +
                "ESC: menu. F11: full screen."),
    ];
}
