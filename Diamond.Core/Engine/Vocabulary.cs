using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Diamond.Core.Localization;
using Diamond.Core.World;

namespace Diamond.Core.Engine;

/// <summary>Everything the player can do. Movement is relative to the way the player faces.</summary>
public enum Verb
{
    None,
    Forward,
    Left,
    Right,
    Back,
    Take,
    Drop,
    Open,
    Throw,
    Wear,
    Remove,
    Drink,
    Fill,
    Eat,
    Swallow,
    Inject,
    Cut,
    Climb,
    Descend,
    Raise,
    Dig,
    Light,
    Press,
    Break,
    Tie,
    Ask,
    Behead,
    Kill,
    Fly,
    Read,
    Fire,
    Look,
    Examine,
    Inventory,
    Status,
    Rest,
    Help,
}

/// <summary>How commands are typed (a player setting).</summary>
public enum ParserMode
{
    /// <summary>
    /// Short form, as in 1984: the original vocabulary of about ninety words, completed while you type
    /// after three or four letters; unknown words are erased with a beep. Commands chain with "/".
    /// </summary>
    Short,

    /// <summary>
    /// Long form: everything the short form accepts, plus whole sentences with other verb forms
    /// ("PRENDRE", "PRENEZ", "WALKING"), synonyms, filler words ("JE VEUX", "PLEASE") and chaining with
    /// "ET", "PUIS", "AND", "THEN" or commas. Nothing is completed or erased while typing.
    /// </summary>
    Long,
}

/// <summary>A word of the vocabulary: a verb or a noun.</summary>
public readonly record struct Word(string Text, Verb Verb, Noun Noun, bool LongForm = false)
{
    public bool IsVerb => Verb != Verb.None;
}

/// <summary>
/// The game's vocabulary. In the short form (the original's) a word is recognised from its first
/// three or four letters, as soon as no other word starts the same way. The long form adds other
/// verb forms, synonyms and filler words, and accepts inflected words ("BOTTE", "AVANCER", "FORWARDS").
/// </summary>
public static class Vocabulary
{
    /// <summary>Shortest abbreviation accepted (the original completed words after three letters).</summary>
    public const int MinPrefix = 3;

    /// <summary>Long form: a word may carry an ending after a vocabulary word at least this long.</summary>
    public const int MinStem = 4;

    private static readonly Dictionary<Language, Word[]> Short = new()
    {
        [Language.French] = Build(false,
            ("AVANCE", Verb.Forward), ("MARCHE", Verb.Forward),
            ("GAUCHE", Verb.Left), ("DROITE", Verb.Right),
            ("DEMI-TOUR", Verb.Back), ("RECULE", Verb.Back),
            ("PRENDS", Verb.Take), ("RAMASSE", Verb.Take),
            ("POSE", Verb.Drop), ("LAISSE", Verb.Drop), ("LACHE", Verb.Drop),
            ("OUVRE", Verb.Open),
            ("LANCE", Verb.Throw), ("JETTE", Verb.Throw),
            ("METS", Verb.Wear), ("ENFILE", Verb.Wear),
            ("ENLEVE", Verb.Remove), ("RETIRE", Verb.Remove),
            ("BOIS", Verb.Drink),
            ("REMPLIS", Verb.Fill), ("FAIS", Verb.Fill),
            ("MANGE", Verb.Eat),
            ("AVALE", Verb.Swallow),
            ("INJECTE", Verb.Inject),
            ("COUPE", Verb.Cut), ("TRANCHE", Verb.Cut),
            ("MONTE", Verb.Climb), ("GRIMPE", Verb.Climb),
            ("DESCENDS", Verb.Descend),
            ("REMONTE", Verb.Raise),
            ("DEBLAYE", Verb.Dig), ("CREUSE", Verb.Dig),
            ("ALLUME", Verb.Light),
            ("APPUIE", Verb.Press), ("PRESSE", Verb.Press), ("POUSSE", Verb.Press),
            ("BRISE", Verb.Break), ("CASSE", Verb.Break),
            ("ATTACHE", Verb.Tie),
            ("INTERROGE", Verb.Ask), ("PARLE", Verb.Ask),
            ("DECAPITE", Verb.Behead),
            ("TUE", Verb.Kill), ("ATTAQUE", Verb.Kill), ("FRAPPE", Verb.Kill),
            ("DECOLLE", Verb.Fly),
            ("LIS", Verb.Read),
            ("TIRE", Verb.Fire),
            ("REGARDE", Verb.Look),
            ("EXAMINE", Verb.Examine), ("FOUILLE", Verb.Examine),
            ("INVENTAIRE", Verb.Inventory),
            ("BILAN", Verb.Status),
            ("REPOSE", Verb.Rest), ("DORS", Verb.Rest),
            ("AIDE", Verb.Help),
            ("MASSUE", Noun.Club), ("GOURDE", Noun.Gourd), ("COUTEAU", Noun.Knife), ("TIROIR", Noun.Drawer),
            ("PAQUET", Noun.Cigarettes), ("CIGARETTES", Noun.Cigarettes), ("CLEF", Noun.Key), ("CLE", Noun.Key),
            ("TORCHE", Noun.Torch), ("BOTTES", Noun.Boots), ("SQUELETTE", Noun.Skeleton), ("PLANTE", Noun.Plant),
            ("TROUSSE", Noun.Kit), ("FORTIFIANT", Noun.Tonic), ("SERUM", Noun.Serum), ("CACHET", Noun.Aspirin),
            ("ASPIRINE", Noun.Aspirin), ("BANDE", Noun.Bandage), ("BANDAGE", Noun.Bandage), ("NOIX", Noun.Coconut),
            ("COCO", Noun.Coconut), ("COCOTIER", Noun.Palm), ("PALMIER", Noun.Palm), ("BANANES", Noun.Bananas),
            ("PELLE", Noun.Shovel), ("TERRE", Noun.Earth), ("TRAPPE", Noun.Trapdoor), ("BOUTEILLE", Noun.Bottle),
            ("MITRAILLETTE", Noun.Gun), ("MYGALE", Noun.Spider), ("ARAIGNEE", Noun.Spider), ("COBRA", Noun.Cobra),
            ("SERPENT", Noun.Cobra), ("SCORPIONS", Noun.Scorpion), ("SOURCE", Noun.Spring), ("LAVE", Noun.Lava),
            ("GRILLE", Noun.Grille), ("CORDE", Noun.Rope), ("BOUDDHA", Noun.Buddha), ("STATUE", Noun.Buddha),
            ("CASQUE", Noun.Helmet), ("MARTEAU", Noun.Hammer), ("SEAU", Noun.Bucket), ("PUITS", Noun.Well),
            ("IDOLE", Noun.Idol), ("INSCRIPTION", Noun.Inscription), ("FANTOME", Noun.Ghost), ("SABRE", Noun.Sabre),
            ("GORILLE", Noun.Gorilla), ("SAGE", Noun.Sage), ("VIEILLARD", Noun.Sage), ("PORTE", Noun.Door),
            ("DRAGON", Noun.Dragon), ("DIAMANT", Noun.Diamond), ("JERRICANE", Noun.Jerrican), ("BIDON", Noun.Jerrican),
            ("HELICO", Noun.Helicopter), ("HELICOPTERE", Noun.Helicopter), ("BOUTON", Noun.Button), ("OEIL", Noun.Eye),
            ("EAU", Noun.Water), ("PLEIN", Noun.Fuel), ("ESSENCE", Noun.Fuel), ("MESSAGE", Noun.Message),
            ("HANGAR", Noun.Hangar)),

        [Language.English] = Build(false,
            ("FORWARD", Verb.Forward), ("GO", Verb.Forward), ("WALK", Verb.Forward),
            ("LEFT", Verb.Left), ("RIGHT", Verb.Right),
            ("BACK", Verb.Back), ("TURN", Verb.Back),
            ("TAKE", Verb.Take), ("GET", Verb.Take), ("PICK", Verb.Take),
            ("DROP", Verb.Drop), ("LEAVE", Verb.Drop),
            ("OPEN", Verb.Open), ("UNLOCK", Verb.Open),
            ("THROW", Verb.Throw), ("HURL", Verb.Throw),
            ("WEAR", Verb.Wear),
            ("REMOVE", Verb.Remove),
            ("DRINK", Verb.Drink),
            ("FILL", Verb.Fill), ("REFUEL", Verb.Fill),
            ("EAT", Verb.Eat),
            ("SWALLOW", Verb.Swallow),
            ("INJECT", Verb.Inject),
            ("CUT", Verb.Cut), ("CHOP", Verb.Cut),
            ("CLIMB", Verb.Climb), ("BOARD", Verb.Climb),
            ("DESCEND", Verb.Descend), ("DOWN", Verb.Descend), ("LOWER", Verb.Descend),
            ("RAISE", Verb.Raise), ("PULL", Verb.Raise), ("HAUL", Verb.Raise),
            ("DIG", Verb.Dig), ("CLEAR", Verb.Dig),
            ("LIGHT", Verb.Light),
            ("PRESS", Verb.Press), ("PUSH", Verb.Press),
            ("BREAK", Verb.Break), ("SMASH", Verb.Break),
            ("TIE", Verb.Tie),
            ("ASK", Verb.Ask), ("QUESTION", Verb.Ask), ("TALK", Verb.Ask),
            ("BEHEAD", Verb.Behead),
            ("KILL", Verb.Kill), ("ATTACK", Verb.Kill), ("HIT", Verb.Kill),
            ("FLY", Verb.Fly), ("TAKEOFF", Verb.Fly),
            ("READ", Verb.Read),
            ("FIRE", Verb.Fire), ("SHOOT", Verb.Fire),
            ("LOOK", Verb.Look),
            ("EXAMINE", Verb.Examine), ("SEARCH", Verb.Examine),
            ("INVENTORY", Verb.Inventory),
            ("STATUS", Verb.Status),
            ("REST", Verb.Rest), ("SLEEP", Verb.Rest),
            ("HELP", Verb.Help),
            ("CLUB", Noun.Club), ("GOURD", Noun.Gourd), ("FLASK", Noun.Gourd), ("KNIFE", Noun.Knife),
            ("DRAWER", Noun.Drawer), ("PACKET", Noun.Cigarettes), ("CIGARETTES", Noun.Cigarettes), ("KEY", Noun.Key),
            ("TORCH", Noun.Torch), ("BOOTS", Noun.Boots), ("SKELETON", Noun.Skeleton), ("PLANT", Noun.Plant),
            ("KIT", Noun.Kit), ("TONIC", Noun.Tonic), ("SERUM", Noun.Serum), ("ASPIRIN", Noun.Aspirin),
            ("BANDAGE", Noun.Bandage), ("COCONUT", Noun.Coconut), ("PALM", Noun.Palm), ("TREE", Noun.Palm),
            ("BANANAS", Noun.Bananas), ("SHOVEL", Noun.Shovel), ("SPADE", Noun.Shovel), ("EARTH", Noun.Earth),
            ("SOIL", Noun.Earth), ("TRAPDOOR", Noun.Trapdoor), ("BOTTLE", Noun.Bottle), ("GUN", Noun.Gun),
            ("SPIDER", Noun.Spider), ("TARANTULA", Noun.Spider), ("COBRA", Noun.Cobra), ("SNAKE", Noun.Cobra),
            ("SCORPIONS", Noun.Scorpion), ("SPRING", Noun.Spring), ("LAVA", Noun.Lava), ("GRILLE", Noun.Grille),
            ("GATE", Noun.Grille), ("ROPE", Noun.Rope), ("BUDDHA", Noun.Buddha), ("STATUE", Noun.Buddha),
            ("HELMET", Noun.Helmet), ("HAMMER", Noun.Hammer), ("BUCKET", Noun.Bucket), ("WELL", Noun.Well),
            ("IDOL", Noun.Idol), ("INSCRIPTION", Noun.Inscription), ("GHOST", Noun.Ghost), ("SABRE", Noun.Sabre),
            ("SWORD", Noun.Sabre), ("GORILLA", Noun.Gorilla), ("SAGE", Noun.Sage), ("DOOR", Noun.Door),
            ("DRAGON", Noun.Dragon), ("DIAMOND", Noun.Diamond), ("JERRYCAN", Noun.Jerrican), ("HELICOPTER", Noun.Helicopter),
            ("BUTTON", Noun.Button), ("EYE", Noun.Eye), ("WATER", Noun.Water), ("FUEL", Noun.Fuel),
            ("PETROL", Noun.Fuel), ("MESSAGE", Noun.Message), ("HANGAR", Noun.Hangar)),
    };

    private static readonly Dictionary<Language, Word[]> LongForms = new()
    {
        [Language.French] = Build(true,
            ("AVANCER", Verb.Forward), ("AVANCEZ", Verb.Forward), ("ALLER", Verb.Forward), ("VA", Verb.Forward),
            ("ALLEZ", Verb.Forward), ("DROIT", Verb.Forward), ("CONTINUE", Verb.Forward), ("MARCHER", Verb.Forward),
            ("TOURNE", Verb.Back), ("TOURNER", Verb.Back), ("TOURNEZ", Verb.Back), ("RETOURNE", Verb.Back),
            ("PRENDRE", Verb.Take), ("PRENEZ", Verb.Take), ("SAISIS", Verb.Take), ("RAMASSER", Verb.Take),
            ("POSER", Verb.Drop), ("POSEZ", Verb.Drop), ("DEPOSE", Verb.Drop), ("ABANDONNE", Verb.Drop),
            ("OUVRIR", Verb.Open), ("OUVREZ", Verb.Open), ("DEVERROUILLE", Verb.Open),
            ("LANCER", Verb.Throw), ("LANCEZ", Verb.Throw), ("METTRE", Verb.Wear), ("METTEZ", Verb.Wear),
            ("ENLEVER", Verb.Remove), ("BOIRE", Verb.Drink), ("BUVEZ", Verb.Drink), ("REMPLIR", Verb.Fill),
            ("FAIRE", Verb.Fill), ("FAITES", Verb.Fill), ("MANGER", Verb.Eat), ("MANGEZ", Verb.Eat),
            ("AVALER", Verb.Swallow), ("INJECTER", Verb.Inject), ("COUPER", Verb.Cut), ("COUPEZ", Verb.Cut),
            ("MONTER", Verb.Climb), ("MONTEZ", Verb.Climb), ("ESCALADE", Verb.Climb), ("GRIMPER", Verb.Climb),
            ("DESCENDRE", Verb.Descend), ("DESCENDEZ", Verb.Descend), ("REMONTER", Verb.Raise), ("HISSE", Verb.Raise),
            ("DEBLAIE", Verb.Dig), ("DEBLAYER", Verb.Dig), ("CREUSER", Verb.Dig), ("ALLUMER", Verb.Light),
            ("APPUYER", Verb.Press), ("APPUYEZ", Verb.Press), ("ENFONCE", Verb.Press), ("BRISER", Verb.Break),
            ("CASSER", Verb.Break), ("DEFONCE", Verb.Break), ("ATTACHER", Verb.Tie), ("NOUE", Verb.Tie),
            ("INTERROGER", Verb.Ask), ("QUESTIONNE", Verb.Ask), ("DEMANDE", Verb.Ask), ("PARLER", Verb.Ask),
            ("DECAPITER", Verb.Behead), ("TUER", Verb.Kill), ("COMBATS", Verb.Kill), ("DECOLLER", Verb.Fly),
            ("PILOTE", Verb.Fly), ("ENVOLE", Verb.Fly), ("LIRE", Verb.Read), ("LISEZ", Verb.Read), ("TIRER", Verb.Fire),
            ("REGARDER", Verb.Look), ("OBSERVE", Verb.Look), ("DECRIS", Verb.Look), ("EXAMINER", Verb.Examine),
            ("SANTE", Verb.Status), ("ETAT", Verb.Status), ("REPOSER", Verb.Rest), ("DORMIR", Verb.Rest),
            ("SURVIE", Noun.Kit), ("SECOURS", Noun.Kit), ("ARBRE", Noun.Palm), ("FUSIL", Noun.Gun), ("ARME", Noun.Gun),
            ("CARBURANT", Noun.Fuel), ("RESERVOIR", Noun.Fuel), ("GRAVATS", Noun.Earth), ("BOUDHA", Noun.Buddha),
            ("JERRYCAN", Noun.Jerrican), ("JERRICAN", Noun.Jerrican), ("CLEFS", Noun.Key), ("CLES", Noun.Key),
            ("CALEBASSE", Noun.Gourd), ("MACHETTE", Noun.Knife), ("GENIE", Noun.Ghost), ("SPECTRE", Noun.Ghost),
            ("ERMITE", Noun.Sage), ("MOINE", Noun.Sage), ("YEUX", Noun.Eye)),

        [Language.English] = Build(true,
            ("MOVE", Verb.Forward), ("ADVANCE", Verb.Forward), ("PROCEED", Verb.Forward), ("CONTINUE", Verb.Forward),
            ("STRAIGHT", Verb.Forward), ("AHEAD", Verb.Forward), ("GRAB", Verb.Take), ("COLLECT", Verb.Take),
            ("DISCARD", Verb.Drop), ("PUT", Verb.Drop), ("PLACE", Verb.Drop), ("TOSS", Verb.Throw), ("DON", Verb.Wear),
            ("SIP", Verb.Drink), ("CONSUME", Verb.Eat), ("ASCEND", Verb.Climb), ("EXCAVATE", Verb.Dig),
            ("IGNITE", Verb.Light), ("BURN", Verb.Light), ("SHATTER", Verb.Break), ("ATTACH", Verb.Tie),
            ("SPEAK", Verb.Ask), ("CONSULT", Verb.Ask), ("DECAPITATE", Verb.Behead), ("SLAY", Verb.Kill),
            ("FIGHT", Verb.Kill), ("ESCAPE", Verb.Fly), ("PILOT", Verb.Fly), ("INSPECT", Verb.Examine),
            ("DESCRIBE", Verb.Look), ("INV", Verb.Inventory), ("HEALTH", Verb.Status),
            ("SURVIVAL", Noun.Kit), ("MEDICAL", Noun.Kit), ("PILLS", Noun.Aspirin), ("TABLETS", Noun.Aspirin),
            ("ANTIVENOM", Noun.Serum), ("MACHINE-GUN", Noun.Gun), ("RIFLE", Noun.Gun), ("CHOPPER", Noun.Helicopter),
            ("JERRICAN", Noun.Jerrican), ("CAN", Noun.Jerrican), ("TANK", Noun.Fuel), ("GASOLINE", Noun.Fuel),
            ("MOUND", Noun.Earth), ("RUBBLE", Noun.Earth), ("MONK", Noun.Sage), ("HERMIT", Noun.Sage),
            ("HATCH", Noun.Trapdoor), ("CALABASH", Noun.Gourd), ("MACHETE", Noun.Knife), ("SPECTRE", Noun.Ghost),
            ("EYES", Noun.Eye), ("KEYS", Noun.Key)),
    };

    /// <summary>Little words skipped in both forms ("PRENDS LA CLEF", "TAKE THE KEY").</summary>
    private static readonly Dictionary<Language, HashSet<string>> Articles = new()
    {
        [Language.French] = ["LE", "LA", "LES", "L", "UN", "UNE", "DES", "DE", "DU", "D", "AU", "AUX", "A"],
        [Language.English] = ["THE", "A", "AN", "TO", "UP"],
    };

    /// <summary>More filler words skipped by the long form ("JE VEUX", "PLEASE").</summary>
    private static readonly Dictionary<Language, HashSet<string>> Fillers = new()
    {
        [Language.French] = ["AVEC", "SUR", "DANS", "MON", "MA", "MES", "TON", "TA", "TES", "CE", "CET", "CETTE", "SON",
            "SA", "SES", "EN", "JE", "J", "VEUX", "VAIS", "VOUDRAIS", "MOI", "TOI", "TU", "VOUS", "S", "IL", "PLAIT",
            "MAINTENANT", "OK", "BIEN", "TOUT", "TOUTE", "VERS", "POUR", "PAR", "ICI", "Y", "CONTRE", "ENCORE", "VITE"],
        [Language.English] = ["AT", "WITH", "ON", "IN", "INTO", "MY", "THIS", "THAT", "OF", "OFF", "AROUND", "I", "WANT",
            "WILL", "WOULD", "LIKE", "PLEASE", "NOW", "LET", "ME", "YOU", "SHALL", "TRY", "SOME", "IT", "THEM", "HERE",
            "THERE", "FROM", "USING", "TOWARDS", "THROUGH", "OVER", "FOR", "BY", "AGAIN", "ALL", "QUICKLY", "CAREFULLY"],
    };

    /// <summary>Words after which a long-form sentence names a second object ("THROW CLUB AT SPIDER").</summary>
    private static readonly Dictionary<Language, HashSet<string>> Prepositions = new()
    {
        [Language.French] = ["SUR", "AVEC", "CONTRE", "DANS", "VERS", "SOUS"],
        [Language.English] = ["AT", "WITH", "ON", "INTO", "USING", "FROM", "IN", "TO"],
    };

    private static Word[] Build(bool longForm, params (string text, object meaning)[] entries) =>
        entries.Select(e => e.meaning is Verb v
                ? new Word(e.text, v, Noun.None, longForm)
                : new Word(e.text, Verb.None, (Noun)e.meaning, longForm))
            .ToArray();

    /// <summary>The words understood in a parser mode.</summary>
    public static IReadOnlyList<Word> All(Language language, ParserMode mode = ParserMode.Short) =>
        mode == ParserMode.Short ? Short[language] : Short[language].Concat(LongForms[language]).ToArray();

    public static bool IsStopWord(Language language, string token, ParserMode mode = ParserMode.Short)
    {
        token = Normalize(token).Trim();
        return Articles[language].Contains(token) || (mode == ParserMode.Long && Fillers[language].Contains(token));
    }

    public static bool IsPreposition(Language language, string token) => Prepositions[language].Contains(Normalize(token).Trim());

    /// <summary>Upper case, without accents; apostrophes and punctuation become spaces (hyphens and "/" stay).</summary>
    public static string Normalize(string text)
    {
        if (string.IsNullOrEmpty(text))
            return string.Empty;
        var decomposed = text.ToUpperInvariant().Replace("Œ", "OE").Replace("Æ", "AE").Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(decomposed.Length);
        foreach (char c in decomposed)
        {
            var cat = CharUnicodeInfo.GetUnicodeCategory(c);
            if (cat == UnicodeCategory.NonSpacingMark)
                continue;
            if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '/' || c == ',')
                sb.Append(c);
            else
                sb.Append(' ');
        }
        return sb.ToString();
    }

    /// <summary>The vocabulary words that start with <paramref name="token"/> (normalised).</summary>
    public static IEnumerable<Word> Candidates(Language language, string token, ParserMode mode = ParserMode.Short)
    {
        token = Normalize(token).Trim();
        if (token.Length == 0)
            return [];
        return All(language, mode).Where(w => w.Text.StartsWith(token, StringComparison.Ordinal));
    }

    /// <summary>
    /// Recognises a typed word: an exact word, or an abbreviation of at least three letters shared
    /// only by words meaning the same thing. The long form also accepts a word with an ending added
    /// to a vocabulary word ("AVANCER", "BOTTE", "FORWARDS"). Returns null when unknown or ambiguous.
    /// </summary>
    public static Word? Lookup(Language language, string token, ParserMode mode = ParserMode.Short)
    {
        token = Normalize(token).Trim();
        if (token.Length == 0)
            return null;
        var words = All(language, mode);
        foreach (var w in words)
            if (w.Text == token)
                return w;
        if (token.Length < MinPrefix)
            return null;

        var matches = words.Where(w => w.Text.StartsWith(token, StringComparison.Ordinal)).ToList();
        if (matches.Count > 0)
        {
            var first = matches[0];
            if (matches.All(m => m.Verb == first.Verb && m.Noun == first.Noun))
                return matches.OrderBy(m => m.Text.Length).First();
            return null;
        }

        if (mode == ParserMode.Long)
        {
            // An inflected word: the longest vocabulary word it starts with.
            Word? best = null;
            foreach (var w in words)
                if (w.Text.Length >= MinStem && token.StartsWith(w.Text, StringComparison.Ordinal) &&
                    token.Length - w.Text.Length <= 3 && (best == null || w.Text.Length > best.Value.Text.Length))
                    best = w;
            return best;
        }
        return null;
    }

    /// <summary>
    /// What typing a word would complete to: the full word when the abbreviation is unambiguous,
    /// null when unknown or ambiguous. Used for the short form's completion while typing.
    /// </summary>
    public static string Complete(Language language, string token, ParserMode mode = ParserMode.Short) =>
        Lookup(language, token, mode)?.Text;

    /// <summary>True when the token is the start of at least one word (keep typing).</summary>
    public static bool IsPrefix(Language language, string token, ParserMode mode = ParserMode.Short) =>
        Candidates(language, token, mode).Any();

    /// <summary>The words shown on the touch keyboard: one per meaning, verbs then nouns (short form words).</summary>
    public static IReadOnlyList<Word> Primary(Language language)
    {
        var seen = new HashSet<(Verb, Noun)>();
        var list = new List<Word>();
        foreach (var w in Short[language])
            if (seen.Add((w.Verb, w.Noun)))
                list.Add(w);
        return list;
    }
}
