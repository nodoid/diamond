using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Diamond.Core.Audio;
using Diamond.Core.Localization;
using Diamond.Core.World;

namespace Diamond.Core.Engine;

/// <summary>How a game ended.</summary>
public enum Ending
{
    None,
    Dead,
    Escaped,
    EscapedWithDiamond,
}

/// <summary>
/// One game of The Diamond of Cursed Island: where the explorer is and faces, what they carry,
/// their health, the state of the island, and the rules that run every command.
/// </summary>
public sealed class Adventure
{
    /// <summary>The most things the explorer can hold (worn boots and helmet don't count).</summary>
    public const int HandsCapacity = 8;

    public const int GourdSips = 3;
    public const int SerumDoses = 2;

    private readonly ISoundPlayer _sound;
    private readonly Dictionary<Noun, ThingState> _things = new();
    private readonly HashSet<string> _flags = new();
    private readonly HashSet<string> _visited = new();
    private readonly HashSet<string> _milestones = new();
    private readonly HashSet<Noun> _seen = new();
    private readonly List<Loc> _out = new();
    private int _takeCounter;

    public Adventure(ISoundPlayer sound = null)
    {
        _sound = sound ?? SilentSoundPlayer.Instance;
        foreach (var def in Island.Things.Values)
            _things[def.Noun] = new ThingState(def);
        foreach (var (noun, location, facing, place, hidden) in Island.StartPositions())
        {
            var t = _things[noun];
            t.Location = location;
            t.Facing = facing;
            t.Place = place;
            t.Hidden = hidden;
        }
        LocationId = Island.Start;
        Facing = Island.StartFacing;
        _visited.Add(LocationId);
        Gourd = 1;
        Serum = SerumDoses;
    }

    // ------------------------------------------------------------------ state

    public string LocationId { get; private set; }
    public Location Location => Island.Locations[LocationId];
    public Dir Facing { get; private set; }
    public Part Part => Location.Part;
    public int Moves { get; private set; }
    public int Score { get; private set; }
    public Health Health { get; private set; } = new();
    public Ending Ending { get; private set; }
    public bool Ended => Ending != Ending.None;
    public bool Won => Ending is Ending.Escaped or Ending.EscapedWithDiamond;
    public Loc EndMessage { get; private set; }

    /// <summary>Sips left in the gourd.</summary>
    public int Gourd { get; private set; }

    /// <summary>Doses left in the serum vial.</summary>
    public int Serum { get; private set; }

    /// <summary>Set when the explorer passes into part 2 (the game saves a checkpoint and shows the interlude).</summary>
    public bool EnteredPart2 { get; set; }

    /// <summary>Turns spent in the dragon's lair while it lives.</summary>
    private int DragonTurns { get; set; }

    public bool UpPalm => Has("up_palm");
    public bool Aboard => Has("aboard");
    public bool TorchLit => Has("torch_lit");
    public bool SecretOpen => Has("secret_open");
    public bool HangarOpen => Has("hangar_open");
    public bool Fuelled => Has("fuelled");
    public bool BucketTied => Has("bucket_tied");
    public bool BucketDown => Has("bucket_down");
    public bool BucketFull => Has("bucket_full");
    public bool DoorOpen => Has("door_open");
    public bool GrilleOpen => Has("grille_open");
    public bool RustyBroken => Has("rusty_broken");
    public bool TrapOpen => Has("trap_open");
    public bool DrawerOpen => Has("drawer_open");
    public bool SageAsked => Has("sage_asked");
    public bool HasFlag(string flag) => _flags.Contains(flag);
    private bool Has(string flag) => _flags.Contains(flag);
    private void Set(string flag) => _flags.Add(flag);
    private void Clear(string flag) => _flags.Remove(flag);

    public bool Alive(Noun creature) => !_things[creature].Gone && !Has(creature + "_dead");

    public IReadOnlyCollection<ThingState> AllThings => _things.Values;
    public ThingState Thing(Noun noun) => _things[noun];
    public IEnumerable<string> Milestones => _milestones;

    public IEnumerable<ThingState> Carried => _things.Values.Where(t => t.Carried && !t.Gone).OrderBy(t => t.TakenAt);
    public bool Holds(Noun noun) => _things.TryGetValue(noun, out var t) && t.Carried && !t.Gone;
    public bool Wears(Noun noun) => Holds(noun) && _things[noun].Worn;
    private int HandsUsed => _things.Values.Count(t => t.Carried && !t.Gone && !t.Worn);

    /// <summary>The view in front of the explorer.</summary>
    public View CurrentView
    {
        get
        {
            if (UpPalm)
                return new View("palm_top");
            var view = Location.Views[Facing];
            if (LocationId == "buddha" && Facing == Dir.North && SecretOpen)
                return new View("temple_opening");
            if (LocationId == "hangar_in" && Facing == Dir.East)
                return new View(HangarOpen ? "hangar_in_open" : "hangar_in_doors");
            return view;
        }
    }

    /// <summary>True when there is light to see by.</summary>
    public bool CanSee
    {
        get
        {
            if (!Location.Dark)
                return true;
            if (TorchLit && Holds(Noun.Torch))
                return true;
            var torch = _things[Noun.Torch];
            return TorchLit && !torch.Carried && torch.Location == LocationId;
        }
    }

    /// <summary>Things drawn in the current view (and so the ones that can be handled).</summary>
    public IEnumerable<ThingState> Visible()
    {
        if (!CanSee)
            return [];
        string loc = UpPalm ? Island.PalmTop : LocationId;
        return _things.Values.Where(t => !t.Gone && !t.Carried && !t.Hidden && t.Location == loc &&
                                         (UpPalm || t.Facing == Facing));
    }

    public bool InView(Noun noun) => Visible().Any(t => t.Noun == noun);

    /// <summary>The sprite to draw for a thing in its present state.</summary>
    public string SpriteFor(ThingState t) => t.Noun switch
    {
        Noun.Drawer => DrawerOpen ? "table_open" : "table",
        Noun.Torch => TorchLit ? "torch_lit" : "torch",
        Noun.Plant => Alive(Noun.Plant) ? "plant" : "plant_cut",
        Noun.Palm => _things[Noun.Coconut].Location == Island.PalmTop && !_things[Noun.Coconut].Gone ? "palm" : "palm_bare",
        Noun.Trapdoor => TrapOpen ? "trapdoor_open" : "trapdoor",
        Noun.Spider => Alive(Noun.Spider) ? "spider" : "spider_dead",
        Noun.Cobra => Alive(Noun.Cobra) ? "cobra" : "cobra_dead",
        Noun.Grille => GrilleOpen ? "grille_open" : "grille",
        Noun.Buddha => SecretOpen ? "buddha_moved" : "buddha",
        Noun.RustyGrille => RustyBroken ? "rusty_broken" : "rusty_grille",
        Noun.Well => BucketTied ? "well_rope" : "well",
        Noun.Bucket => BucketFull ? "bucket_full" : "bucket",
        Noun.Door => DoorOpen ? "door_open" : "door",
        Noun.Dragon => Alive(Noun.Dragon) ? "dragon" : "dragon_dead",
        _ => t.Def.Sprite,
    };

    /// <summary>Nouns the explorer has come across (offered by the touch word list).</summary>
    public IReadOnlyCollection<Noun> Seen => _seen;

    private void NoteSeen()
    {
        foreach (var t in Visible())
            _seen.Add(t.Noun);
        foreach (var t in Carried)
            _seen.Add(t.Noun);
        if (_seen.Contains(Noun.Buddha) || _seen.Contains(Noun.Idol) || _seen.Contains(Noun.Bottle))
            _seen.Add(Noun.Eye);
        if (_seen.Contains(Noun.Bottle))
            _seen.Add(Noun.Message);
        if (_seen.Contains(Noun.Gourd) || _seen.Contains(Noun.Well) || LocationId == "volcano_foot")
            _seen.Add(Noun.Water);
        if (LocationId == "volcano_foot")
            _seen.Add(Noun.Spring);
        if (LocationId == "crater")
            _seen.Add(Noun.Lava);
        if (_seen.Contains(Noun.Helicopter))
            _seen.Add(Noun.Fuel);
        if (Location.Scorpions)
            _seen.Add(Noun.Scorpion);
        if (LocationId is "hangar_yard" or "hangar_in")
            _seen.Add(Noun.Hangar);
    }

    // ------------------------------------------------------------------ output helpers

    private static Loc T(string fr, string en) => new(fr, en);

    private static Loc F(string fr, string en, params Loc[] args) =>
        new(string.Format(fr, args.Select(a => (object)a.Fr).ToArray()),
            string.Format(en, args.Select(a => (object)a.En).ToArray()));

    private void Say(Loc text) => _out.Add(text);
    private void Say(string fr, string en) => _out.Add(new Loc(fr, en));
    private void Play(Sfx sfx) => _sound.Play(sfx);

    private static Loc Name(ThingState t) => t.Def.Name;

    /// <summary>The name without its article ("massue", "club").</summary>
    private static Loc Bare(ThingState t)
    {
        static string Strip(string s, params string[] articles)
        {
            foreach (var a in articles)
                if (s.StartsWith(a, StringComparison.Ordinal))
                    return s[a.Length..];
            return s;
        }
        return new Loc(Strip(t.Def.Name.Fr, "une ", "un ", "des ", "le ", "la ", "l'"),
            Strip(t.Def.Name.En, "an ", "a ", "some ", "the "));
    }

    private static Loc List(IEnumerable<ThingState> things)
    {
        var list = things.ToList();
        static string Join(IReadOnlyList<string> items, string and) =>
            items.Count <= 1 ? string.Concat(items) : string.Join(", ", items.Take(items.Count - 1)) + and + items[^1];
        return new Loc(Join(list.Select(t => t.Def.Name.Fr).ToList(), " et "),
            Join(list.Select(t => t.Def.Name.En).ToList(), " and "));
    }

    // ------------------------------------------------------------------ commands

    /// <summary>The opening text of a new game.</summary>
    public IReadOnlyList<Loc> Begin()
    {
        _out.Clear();
        Describe(true);
        NoteSeen();
        return _out.ToArray();
    }

    /// <summary>Runs one command; returns what the game says.</summary>
    public IReadOnlyList<Loc> Execute(Command c)
    {
        _out.Clear();
        if (Ended)
            return _out.ToArray();

        bool timePasses = Run(c);
        if (!Ended && timePasses)
            PassTime(c);
        NoteSeen();
        return _out.ToArray();
    }

    /// <summary>Real time passing while the explorer stands still (as in the original, which ran in real time).</summary>
    public IReadOnlyList<Loc> Wait()
    {
        _out.Clear();
        if (!Ended)
            PassTime(new Command(Verb.None));
        return _out.ToArray();
    }

    private void PassTime(Command c)
    {
        if (c.Verb != Verb.None)
            Moves++;
        foreach (var w in Health.Pass(Location.Hot && !UpPalm))
        {
            Say(w);
            Play(Sfx.Warning);
        }

        if (LocationId == "dragon" && Alive(Noun.Dragon) && c.Verb != Verb.Forward)
        {
            DragonTurns++;
            if (DragonTurns == 1)
                Say("Le dragon gronde. Des volutes de fumée sortent de ses naseaux...",
                    "The dragon growls. Wisps of smoke curl from its nostrils...");
            else if (DragonTurns >= 3)
            {
                Die(T("Le dragon ouvre la gueule et vous réduit en cendres !",
                    "The dragon opens its jaws and burns you to ashes!"));
                return;
            }
        }

        if (Health.Dead)
            Die(DeathByTroubles());
    }

    private Loc DeathByTroubles()
    {
        var h = Health;
        int worst = new[] { h.Thirst, h.Hunger, h.Fatigue, h.Fever, h.Injury, h.SpiderVenom + h.ScorpionVenom }.Max();
        if (worst == h.SpiderVenom + h.ScorpionVenom)
            return T("Le venin a eu raison de vous. Vous vous effondrez...", "The venom has got the better of you. You collapse...");
        if (worst == h.Thirst)
            return T("Déshydraté, vous vous effondrez...", "Dehydrated, you collapse...");
        if (worst == h.Hunger)
            return T("Mort de faim, vous vous effondrez...", "Starving, you collapse...");
        if (worst == h.Fever)
            return T("La fièvre vous emporte...", "The fever carries you off...");
        if (worst == h.Injury)
            return T("Vos blessures sont trop graves. Vous vous effondrez...", "Your wounds are too grave. You collapse...");
        return T("Épuisé, vous vous effondrez pour ne plus vous relever...", "Exhausted, you collapse, never to rise again...");
    }

    private void Die(Loc why)
    {
        Say(why);
        EndMessage = why;
        Ending = Ending.Dead;
        Play(Sfx.Death);
    }

    private void Award(string milestone, int points)
    {
        if (_milestones.Add(milestone))
            Score += points;
    }

    /// <summary>Runs a command; returns false when no time passes (looking, the inventory, help...).</summary>
    private bool Run(Command c)
    {
        switch (c.Verb)
        {
            case Verb.Forward:
                Forward();
                return true;
            case Verb.Left:
            case Verb.Right:
            case Verb.Back:
                Turn(c.Verb);
                return true;
            case Verb.Look:
                Describe(true);
                return false;
            case Verb.Inventory:
                Inventory();
                return false;
            case Verb.Status:
                foreach (var line in Health.Report())
                    Say(line);
                if (Serum > 0 && Holds(Noun.Serum))
                    Say($"Sérum : {Serum} dose(s).", $"Serum: {Serum} dose(s).");
                if (Holds(Noun.Gourd))
                    Say($"Gourde : {Gourd} gorgée(s).", $"Gourd: {Gourd} sip(s).");
                Say($"Score : {Score}/100  -  coups : {Moves}", $"Score: {Score}/100  -  moves: {Moves}");
                return false;
            case Verb.Help:
                Help();
                return false;
        }

        if (UpPalm && c.Verb is not (Verb.Descend or Verb.Take or Verb.Eat or Verb.Drop or Verb.Climb or Verb.Examine))
        {
            Say("Pas facile, perché en haut d'un cocotier !", "Not easy, perched at the top of a coconut palm!");
            return true;
        }

        switch (c.Verb)
        {
            case Verb.Take: Take(c.Noun); break;
            case Verb.Drop: Drop(c.Noun); break;
            case Verb.Open: Open(c.Noun); break;
            case Verb.Throw: Throw(c.Noun, c.Target); break;
            case Verb.Wear: Wear(c.Noun); break;
            case Verb.Remove: Remove(c.Noun); break;
            case Verb.Drink: Drink(c.Noun); break;
            case Verb.Fill: Fill(c.Noun); break;
            case Verb.Eat: Eat(c.Noun); break;
            case Verb.Swallow: Swallow(c.Noun); break;
            case Verb.Inject: Inject(c.Noun); break;
            case Verb.Cut: Cut(c.Noun); break;
            case Verb.Climb: Climb(c.Noun); break;
            case Verb.Descend: Descend(c.Noun); break;
            case Verb.Raise: Raise(c.Noun); break;
            case Verb.Dig: Dig(); break;
            case Verb.Light: Light(c.Noun); break;
            case Verb.Press: Press(c.Noun); break;
            case Verb.Break: Break(c.Noun); break;
            case Verb.Tie: Tie(c.Noun); break;
            case Verb.Ask: Ask(c.Noun); break;
            case Verb.Behead: Behead(c.Noun); break;
            case Verb.Kill: Kill(c.Noun); break;
            case Verb.Fly: Fly(); break;
            case Verb.Read: Read(c.Noun); break;
            case Verb.Fire: Fire(c.Noun); break;
            case Verb.Examine: Examine(c.Noun); break;
            case Verb.Rest: Rest(); break;
            default:
                Say("Je ne comprends pas.", "I don't understand.");
                return false;
        }
        return true;
    }

    // ------------------------------------------------------------------ looking

    private void Describe(bool full)
    {
        if (UpPalm)
        {
            Say("Du haut du cocotier, vous dominez la plage et le lagon.",
                "From the top of the palm you look out over the beach and the lagoon.");
            if (_things[Noun.Coconut].Location == Island.PalmTop && !_things[Noun.Coconut].Gone)
                Say("Des noix de coco pendent à portée de main.", "Coconuts hang within reach.");
            return;
        }
        if (!CanSee)
        {
            Say("Il fait noir comme dans un four.", "It is pitch dark.");
            return;
        }
        if (full)
        {
            Say(Location.Description);
            if (LocationId == "hangar_corner" && _things[Noun.Earth].Gone)
                Say("La terre a été dégagée.", "The earth has been cleared away.");
        }
        SeeThings();
    }

    private void SeeThings()
    {
        if (!CanSee)
            return;
        var visible = Visible().Where(t => t.Noun != Noun.Inscription || LocationId == "fallen").ToList();
        if (visible.Count > 0)
            Say(F("Vous voyez {0}.", "You see {0}.", List(visible)));
        var ahead = Location.Exits.ContainsKey(Facing);
        if (LocationId == "hangar_corner" && TrapOpen && Facing == Dir.North)
            Say("La trappe ouverte donne sur une échelle.", "The open trapdoor leads to a ladder.");
        if (!ahead && visible.Count == 0 && Location.Part == Part.Underground && Location.Dark)
            Say("Devant vous : la roche.", "Ahead of you: solid rock.");
    }

    private void Inventory()
    {
        var carried = Carried.ToList();
        if (carried.Count == 0)
        {
            Say("Vous n'avez rien.", "You have nothing.");
            return;
        }
        var worn = carried.Where(t => t.Worn).ToList();
        var held = carried.Where(t => !t.Worn).ToList();
        if (held.Count > 0)
            Say(F("Vous avez {0}.", "You have {0}.", List(held)));
        if (worn.Count > 0)
            Say(F("Vous portez {0}.", "You are wearing {0}.", List(worn)));
        if (Holds(Noun.Torch) && TorchLit)
            Say("Votre torche est allumée.", "Your torch is lit.");
    }

    private void Help()
    {
        Say("Tapez un verbe et un nom : PRENDS MASSUE, OUVRE TIROIR... Pour vous déplacer : AVANCE, GAUCHE, " +
            "DROITE, DEMI-TOUR. Aussi : INVENTAIRE, BILAN, REGARDE. Plusieurs ordres : séparez-les par /.",
            "Type a verb and a noun: TAKE CLUB, OPEN DRAWER... To move: FORWARD, LEFT, RIGHT, BACK. " +
            "Also: INVENTORY, STATUS, LOOK. Several orders: separate them with /.");
    }

    private void Examine(Noun noun)
    {
        if (noun == Noun.None)
        {
            Describe(true);
            return;
        }
        var t = Find(noun, alsoCarried: true);
        if (t == null)
        {
            NotHere();
            return;
        }
        Say(noun switch
        {
            Noun.Gourd => Gourd > 0
                ? T($"Une gourde en calebasse. Il reste {Gourd} gorgée(s).", $"A calabash gourd. There are {Gourd} sip(s) left.")
                : T("Une gourde en calebasse. Elle est vide.", "A calabash gourd. It is empty."),
            Noun.Drawer => DrawerOpen ? T("Le tiroir est ouvert.", "The drawer is open.") : T("Le tiroir est fermé.", "The drawer is closed."),
            Noun.Cigarettes => T("Un vieux paquet de cigarettes. Il a l'air bien lourd...", "An old packet of cigarettes. It feels rather heavy..."),
            Noun.Skeleton => T("Les restes d'un explorateur. Il portait de bonnes bottes.", "The remains of an explorer. He wore good boots."),
            Noun.Kit => T("Une trousse de survie. La toile est pourrie.", "A survival kit. The canvas is rotten."),
            Noun.Bottle => T("Il y a un message dans la bouteille.", "There is a message in the bottle."),
            Noun.Torch => TorchLit ? T("La torche brûle bien.", "The torch burns brightly.") : T("Une torche éteinte. Il lui faut du feu.", "An unlit torch. It needs fire."),
            Noun.Gun => T("Une vieille mitraillette rouillée. Elle a l'air piégée.", "A rusty old machine gun. It looks booby-trapped."),
            Noun.Earth => T("Un amas de terre contre le mur. On dirait qu'il cache quelque chose.", "A heap of earth against the wall. It seems to be hiding something."),
            Noun.Trapdoor => TrapOpen ? T("La trappe est ouverte.", "The trapdoor is open.") : T("Une trappe fermée par un cadenas.", "A trapdoor closed with a padlock."),
            Noun.Buddha => T("Un Bouddha souriant. L'un de ses yeux est un gros cristal.", "A smiling Buddha. One of its eyes is a large crystal."),
            Noun.Idol => T("Une idole grimaçante. Son oeil unique semble vous suivre...", "A grimacing idol. Its single eye seems to follow you..."),
            Noun.Well => T("Le puits est profond. On entend l'eau tout au fond.", "The well is deep. You can hear water far below."),
            Noun.RustyGrille => RustyBroken ? T("La grille est brisée.", "The grille is broken.") : T("Une grille rouillée, coincée.", "A rusty grille, stuck fast."),
            Noun.Sage => T("Il a l'air d'attendre qu'on l'interroge.", "He seems to be waiting to be asked something."),
            Noun.Dragon => Alive(Noun.Dragon) ? T("Ses écailles sont dures comme l'acier, mais son cou...", "Its scales are as hard as steel, but its neck...") : T("Le dragon est mort.", "The dragon is dead."),
            Noun.Diamond => T("Un diamant gros comme un oeuf de pigeon. Il vaut une fortune !", "A diamond as big as a pigeon's egg. It is worth a fortune!"),
            Noun.Helicopter => Fuelled ? T("Le réservoir est plein.", "The tank is full.") : T("Le réservoir est vide.", "The tank is empty."),
            Noun.Jerrican => T("Un jerricane plein d'essence.", "A jerrycan full of petrol."),
            Noun.Inscription => T("Une inscription gravée. On pourrait la lire.", "A carved inscription. You could read it."),
            _ => T("Vous ne remarquez rien de particulier.", "You notice nothing special."),
        });
    }

    private void Read(Noun noun)
    {
        if (noun is Noun.Bottle or Noun.Message && (Holds(Noun.Bottle) || InView(Noun.Bottle)))
        {
            Say("Le message dit : « APPUIE OEIL ». Il est signé Steven Smith.",
                "The message says: \"PRESS EYE\". It is signed Steven Smith.");
            return;
        }
        if (noun is Noun.Inscription && InView(Noun.Inscription))
        {
            Say("« Seul le sabre des anciens tranche le cou du dragon. Méfie-toi de l'idole au regard unique. " +
                "Le sage ouvre la porte à qui l'interroge. »",
                "\"Only the sabre of the ancients cuts the dragon's neck. Beware the idol with a single eye. " +
                "The sage opens the door to whoever questions him.\"");
            return;
        }
        if (noun == Noun.Cigarettes && (Holds(Noun.Cigarettes) || InView(Noun.Cigarettes)))
        {
            Say("Des « Gitanes ». Fumer tue.", "French cigarettes. Smoking kills.");
            return;
        }
        Say("Il n'y a rien à lire.", "There is nothing to read.");
    }

    private void NotHere() =>
        Say(CanSee ? T("Je ne vois pas ça ici.", "I can't see that here.") : T("Il fait trop noir pour voir quoi que ce soit.", "It is too dark to see anything."));

    private void NoNoun() => Say("Précisez avec quoi... ou quoi.", "Say what you mean... or with what.");

    /// <summary>A thing in view (or carried) answering to a noun. "STATUE" and "EYE" mean whichever statue is in view.</summary>
    private ThingState Find(Noun noun, bool alsoCarried)
    {
        if (noun == Noun.None)
            return null;
        if (noun is Noun.Buddha or Noun.Eye or Noun.Idol)
        {
            if (noun != Noun.Idol && InView(Noun.Buddha))
                return _things[Noun.Buddha];
            if (InView(Noun.Idol))
                return _things[Noun.Idol];
            return null;
        }
        if (noun == Noun.Grille && LocationId != "cellar")
            noun = Noun.RustyGrille;
        if (noun == Noun.Message)
            noun = Noun.Bottle;
        if (!_things.TryGetValue(noun, out var t))
            return null;
        if (alsoCarried && Holds(noun))
            return t;
        return InView(noun) ? t : null;
    }

    // ------------------------------------------------------------------ moving

    private void Turn(Verb verb)
    {
        if (UpPalm)
        {
            Say("Accroché au tronc, vous regardez autour de vous.", "Clinging to the trunk, you look around.");
            return;
        }
        if (Aboard)
            Clear("aboard");
        Facing = verb switch
        {
            Verb.Left => Facing.Left(),
            Verb.Right => Facing.Right(),
            _ => Facing.Back(),
        };
        Play(Sfx.Step);
        SeeThings();
    }

    private void Forward()
    {
        if (UpPalm)
        {
            Say("Descendez d'abord du cocotier !", "Climb down from the palm first!");
            return;
        }
        if (Aboard)
        {
            Say("Vous êtes dans l'hélicoptère.", "You are in the helicopter.");
            return;
        }
        if (!Location.Exits.TryGetValue(Facing, out var next))
        {
            Say(Location.Part == Part.Underground ? T("La roche vous barre le passage.", "Solid rock bars your way.")
                : T("Vous ne pouvez pas aller par là.", "You can't go that way."));
            Play(Sfx.Bump);
            return;
        }

        // Guardians and closed ways.
        switch (LocationId)
        {
            case "narrow" when Facing == Dir.North && Alive(Noun.Cobra):
                Play(Sfx.Hiss);
                Die(T("Le cobra crache ! Une giclée d'acide dans les yeux : vous voici aveugle... Perdu dans la jungle, " +
                      "vous ne retrouverez jamais votre chemin.",
                    "The cobra spits! A jet of acid in your eyes: you are blind... Lost in the jungle, you will never " +
                    "find your way again."));
                return;
            case "cellar" when Facing == Dir.North && !GrilleOpen:
                Say("Une grille vous barre le passage.", "A grille bars your way.");
                return;
            case "buddha" when Facing == Dir.North && !SecretOpen:
                Say("La statue vous barre le passage.", "The statue bars your way.");
                return;
            case "store" when Facing == Dir.North && !RustyBroken:
                Say("Une grille rouillée vous barre le passage.", "A rusty grille bars your way.");
                return;
            case "gorilla" when Facing == Dir.North && Alive(Noun.Gorilla):
                Health.Injury += 12;
                Play(Sfx.Roar);
                Say("Le gorille vous saisit et vous projette contre la paroi !",
                    "The gorilla grabs you and hurls you against the wall!");
                return;
            case "sage" when Facing == Dir.East && !DoorOpen:
                Say("La porte est fermée.", "The door is shut.");
                return;
            case "dragon" when Facing == Dir.East && Alive(Noun.Dragon):
                Play(Sfx.Roar);
                Die(T("Vous tentez de passer. Le dragon vous happe d'un coup de dents !",
                    "You try to slip past. The dragon snaps you up in one bite!"));
                return;
        }

        bool intoPart2 = LocationId == "cellar";
        LocationId = next;
        Play(Sfx.Step);
        bool first = _visited.Add(next);

        if (intoPart2)
        {
            Clear("grille_open");
            EnteredPart2 = true;
            Award("part2", 8);
            Play(Sfx.Door);
            Say("La grille se referme derrière vous avec un bruit sinistre. Impossible de revenir en arrière !",
                "The grille slams shut behind you with a sinister clang. There is no way back!");
        }

        Describe(first);
        Arrive();
    }

    /// <summary>What happens on arriving somewhere.</summary>
    private void Arrive()
    {
        var loc = Location;
        if (loc.Scorpions && !Wears(Noun.Boots))
        {
            Health.ScorpionStung = true;
            Health.ScorpionVenom += 3;
            Play(Sfx.Hurt);
            Say("Aïe ! Un scorpion vous pique la cheville !", "Ouch! A scorpion stings your ankle!");
        }
        if (loc.Mosquitoes && !Has("mosquitoes"))
        {
            Set("mosquitoes");
            Health.Feverish = true;
            Say("Les moustiques vous dévorent...", "The mosquitoes eat you alive...");
        }
        if (LocationId == "stalactites" && !Wears(Noun.Helmet))
        {
            Health.Injury += 18;
            Play(Sfx.Hurt);
            Say("Une stalactite se détache et vous frappe le crâne !", "A stalactite breaks off and strikes your skull!");
        }
        if (LocationId == "tower_in" && Alive(Noun.Spider))
            Say("Sur le mur, une mygale énorme vous observe...", "On the wall, an enormous tarantula watches you...");
        if (LocationId == "narrow" && Alive(Noun.Cobra))
        {
            Play(Sfx.Hiss);
            Say("Un cobra se dresse devant vous en sifflant !", "A cobra rears up in front of you, hissing!");
        }
        if (LocationId == "haunted" && !_things[Noun.Ghost].Gone)
            Haunt();
        if (LocationId == "dragon" && Alive(Noun.Dragon))
        {
            DragonTurns = 0;
            Play(Sfx.Roar);
            Say("Un dragon gigantesque se dresse devant vous !", "A gigantic dragon rears up before you!");
        }
        if (LocationId == "gorilla" && Alive(Noun.Gorilla))
        {
            Play(Sfx.Roar);
            Say("Un gorille énorme se frappe la poitrine en grognant !", "A huge gorilla beats its chest and growls!");
        }
    }

    /// <summary>The ghost steals the thing you have carried longest (never the torch: it fears the flame).</summary>
    private void Haunt()
    {
        var ghost = _things[Noun.Ghost];
        Play(Sfx.Ghost);
        var victim = Carried.FirstOrDefault(t => !t.Worn && t.Noun != Noun.Torch);
        if (victim == null)
        {
            Say("Un fantôme vous traverse en gémissant, déçu de n'avoir rien à voler.",
                "A ghost passes through you, moaning, disappointed to find nothing to steal.");
            return;
        }
        victim.Carried = false;
        PlaceIn(victim, "lit", Dir.North);
        ghost.Gone = true;
        Say(F("Un fantôme surgit, vous arrache {0} et s'enfuit vers la lueur verte en ricanant !",
            "A ghost looms up, snatches {0} from you and flees cackling towards the green glow!", Name(victim)));
    }

    private void Climb(Noun noun)
    {
        if (UpPalm)
        {
            Say("Vous êtes déjà tout en haut !", "You are already at the top!");
            return;
        }
        if (noun is Noun.Palm or Noun.Coconut or Noun.None && InView(Noun.Palm))
        {
            Set("up_palm");
            Health.FatigueClock += 4;
            Play(Sfx.Climb);
            Say("Vous grimpez péniblement en haut du cocotier.", "You climb laboriously to the top of the coconut palm.");
            Describe(true);
            return;
        }
        if (noun is Noun.Helicopter or Noun.None && LocationId == "hangar_in")
        {
            if (Aboard)
            {
                Say("Vous êtes déjà aux commandes.", "You are already at the controls.");
                return;
            }
            Set("aboard");
            Play(Sfx.Door);
            Say("Vous vous installez aux commandes de l'hélicoptère.", "You settle in at the helicopter's controls.");
            return;
        }
        if (noun == Noun.None && LocationId == "cellar")
        {
            ClimbOut();
            return;
        }
        if (noun == Noun.None)
            NoNoun();
        else
            Say("Impossible d'y grimper.", "You can't climb that.");
    }

    private void ClimbOut()
    {
        LocationId = "hangar_corner";
        Facing = Dir.North;
        Play(Sfx.Climb);
        Say("Vous remontez l'échelle.", "You climb back up the ladder.");
        Describe(false);
    }

    private void Descend(Noun noun)
    {
        if (noun == Noun.Bucket)
        {
            if (!BucketTied || LocationId != "well")
            {
                Say("Il faudrait d'abord l'attacher au puits.", "You would have to tie it to the well first.");
                return;
            }
            if (BucketDown)
            {
                Say("Le seau est déjà au fond.", "The bucket is already at the bottom.");
                return;
            }
            Set("bucket_down");
            Clear("bucket_full");
            Play(Sfx.Splash);
            Say("Le seau descend... et plonge dans l'eau avec un « plouf » lointain.",
                "The bucket goes down... and drops into the water with a distant splash.");
            return;
        }
        if (UpPalm)
        {
            Clear("up_palm");
            Play(Sfx.Climb);
            Say("Vous redescendez du cocotier.", "You climb down from the palm.");
            SeeThings();
            return;
        }
        if (Aboard)
        {
            Clear("aboard");
            Say("Vous descendez de l'hélicoptère.", "You climb out of the helicopter.");
            return;
        }
        if (LocationId == "hangar_corner")
        {
            if (!TrapOpen)
            {
                Say(_things[Noun.Trapdoor].Hidden ? T("Descendre où ?", "Go down where?") : T("La trappe est fermée.", "The trapdoor is shut."));
                return;
            }
            if (!(Holds(Noun.Torch) && TorchLit))
            {
                Say("Il fait noir là-dessous. Il vous faut de la lumière.", "It's dark down there. You need a light.");
                return;
            }
            LocationId = "cellar";
            Facing = Dir.South;
            Play(Sfx.Climb);
            _visited.Add("cellar");
            Say("Vous descendez l'échelle.", "You climb down the ladder.");
            Describe(true);
            return;
        }
        Say("Descendre où ?", "Go down where?");
    }

    private void Raise(Noun noun)
    {
        if (noun == Noun.Bucket || (noun == Noun.None && BucketDown && LocationId == "well"))
        {
            if (LocationId != "well" || !BucketDown)
            {
                Say("Il n'y a rien à remonter.", "There is nothing to pull up.");
                return;
            }
            Clear("bucket_down");
            Set("bucket_full");
            Award("water", 5);
            Play(Sfx.Splash);
            Say("Vous remontez le seau, plein d'une eau fraîche et claire.", "You haul up the bucket, full of cool, clear water.");
            return;
        }
        if (LocationId == "cellar" && noun == Noun.None)
        {
            ClimbOut();
            return;
        }
        Say("Remonter quoi ?", "Pull up what?");
    }

    // ------------------------------------------------------------------ objects

    private static readonly Placement[] Slots =
    [
        new(120, 129, 0), new(84, 129, 0), new(156, 129, 0), new(64, 131, 0), new(176, 131, 0),
        new(102, 132, 0), new(138, 132, 0), new(46, 133, 0), new(194, 133, 0),
    ];

    private void PlaceIn(ThingState t, string location, Dir facing)
    {
        var used = _things.Values.Where(o => o != t && !o.Gone && !o.Carried && o.Location == location && o.Facing == facing)
            .Select(o => o.Place.X).ToList();
        var slot = Slots.FirstOrDefault(s => used.All(x => Math.Abs(x - s.X) > 14), Slots[0]);
        t.Location = location;
        t.Facing = facing;
        t.Place = slot;
        t.Hidden = false;
        t.Carried = false;
        t.Worn = false;
    }

    private void Give(ThingState t)
    {
        t.Carried = true;
        t.Hidden = false;
        t.Location = null;
        t.TakenAt = ++_takeCounter;
    }

    private void Take(Noun noun)
    {
        if (noun == Noun.None)
        {
            NoNoun();
            return;
        }
        if (noun is Noun.Water or Noun.Spring)
        {
            Say("Dans le creux de vos mains ? Buvez plutôt !", "In your cupped hands? Just drink!");
            return;
        }
        if (noun == Noun.Fuel)
        {
            Say("Il faudrait un récipient.", "You would need a container.");
            return;
        }
        if (BucketTied && LocationId == "well" && Facing == Dir.North && noun is Noun.Bucket or Noun.Rope)
        {
            if (BucketDown)
            {
                Say("Remontez d'abord le seau.", "Pull the bucket up first.");
                return;
            }
            if (HandsUsed + 2 > HandsCapacity)
            {
                Say("Vous avez les mains pleines.", "Your hands are full.");
                return;
            }
            Clear("bucket_tied");
            Give(_things[Noun.Rope]);
            Give(_things[Noun.Bucket]);
            Play(Sfx.Take);
            Say("Vous détachez le seau et reprenez la corde.", "You untie the bucket and take back the rope.");
            return;
        }
        if (Holds(noun))
        {
            Say("Vous l'avez déjà.", "You already have it.");
            return;
        }
        var t = Find(noun, false);
        if (t == null)
        {
            NotHere();
            return;
        }
        if (!t.Def.Portable)
        {
            Say(t.Noun is Noun.Spider or Noun.Cobra or Noun.Gorilla or Noun.Dragon or Noun.Ghost or Noun.Sage
                ? T("Vous plaisantez ?", "You must be joking!")
                : T("C'est impossible à prendre.", "You can't take that."));
            return;
        }
        if (LocationId == "tower_in" && Alive(Noun.Spider) && !UpPalm)
        {
            Health.SpiderBitten = true;
            Health.SpiderVenom += 4;
            Play(Sfx.Hurt);
            Say("La mygale bondit et vous mord la main ! Vous lâchez tout.",
                "The tarantula leaps and bites your hand! You let go.");
            return;
        }
        if (t.Noun == Noun.Kit && Alive(Noun.Plant))
        {
            Health.Injury += 12;
            Play(Sfx.Hurt);
            Say("La plante carnivore se referme sur votre bras ! Vous vous dégagez à grand-peine.",
                "The carnivorous plant snaps shut on your arm! You only just tear yourself free.");
            return;
        }
        if (t.Noun != Noun.Kit && HandsUsed >= HandsCapacity)
        {
            Say("Vous avez les mains pleines.", "Your hands are full.");
            return;
        }

        if (t.Noun == Noun.Kit)
        {
            t.Gone = true;
            Play(Sfx.Drop);
            Say("La toile pourrie se déchire : le contenu de la trousse se répand à vos pieds !",
                "The rotten canvas tears: the contents of the kit spill at your feet!");
            foreach (var n in new[] { Noun.Tonic, Noun.Serum, Noun.Aspirin, Noun.Bandage })
            {
                var item = _things[n];
                item.Location = LocationId;
                item.Facing = Facing;
                item.Hidden = false;
            }
            SeeThings();
            return;
        }

        Give(t);
        Play(Sfx.Take);
        Say(F("Vous prenez {0}.", "You take {0}.", Name(t)));
        if (t.Noun == Noun.Diamond)
        {
            Award("diamond", 15);
            Play(Sfx.Treasure);
            Say("Le diamant scintille de mille feux. La fortune est à vous... si vous sortez d'ici !",
                "The diamond blazes with a thousand fires. A fortune is yours... if you get out of here!");
        }
        if (t.Noun == Noun.Coconut)
            Say("Vous cueillez une belle noix de coco.", "You pick a fine coconut.");
    }

    private void Drop(Noun noun)
    {
        if (noun == Noun.None)
        {
            NoNoun();
            return;
        }
        if (!Holds(noun))
        {
            Say("Vous ne l'avez pas.", "You don't have it.");
            return;
        }
        var t = _things[noun];
        if (UpPalm)
        {
            PlaceIn(t, "palm", Dir.South);
            Say(F("Vous lâchez {0}, qui tombe au pied du cocotier.", "You let go of {0}; it falls to the foot of the palm.", Name(t)));
            return;
        }
        if (Aboard)
            Clear("aboard");
        PlaceIn(t, LocationId, Facing);
        Play(Sfx.Drop);
        Say(F("Vous posez {0}.", "You put down {0}.", Name(t)));
        if (t.Noun == Noun.Torch && TorchLit && Location.Dark)
            Say("La torche éclaire la salle depuis le sol.", "The torch lights the room from the floor.");
    }

    private void Wear(Noun noun)
    {
        if (noun == Noun.Bandage)
        {
            if (!Holds(Noun.Bandage))
            {
                Say("Vous ne l'avez pas.", "You don't have it.");
                return;
            }
            _things[Noun.Bandage].Gone = true;
            Health.Injury = Math.Max(0, Health.Injury - 20);
            Say("Vous pansez vos blessures. Ça va mieux.", "You dress your wounds. That's better.");
            return;
        }
        if (noun == Noun.None)
        {
            NoNoun();
            return;
        }
        if (!Holds(noun))
        {
            Say(InView(noun) ? T("Prenez-le d'abord.", "Pick it up first.") : T("Vous ne l'avez pas.", "You don't have it."));
            return;
        }
        var t = _things[noun];
        if (!t.Def.Wearable)
        {
            Say("Ça ne se porte pas.", "You can't wear that.");
            return;
        }
        if (t.Worn)
        {
            Say("C'est déjà fait.", "You already are.");
            return;
        }
        t.Worn = true;
        Play(Sfx.Take);
        Say(noun == Noun.Boots ? T("Vous enfilez les bottes. Elles sont à votre taille !", "You pull on the boots. They fit you!")
            : T("Vous coiffez le casque.", "You put on the helmet."));
    }

    private void Remove(Noun noun)
    {
        if (noun != Noun.None && Wears(noun))
        {
            _things[noun].Worn = false;
            Say("C'est fait.", "Done.");
            return;
        }
        Say("Vous ne le portez pas.", "You aren't wearing that.");
    }

    // ------------------------------------------------------------------ food, drink and medicine

    private void Drink(Noun noun)
    {
        bool fromBucket = BucketFull && (Holds(Noun.Bucket) || (LocationId == "well" && BucketTied));
        if (noun is Noun.Gourd || (noun is Noun.Water or Noun.None && Holds(Noun.Gourd) && Gourd > 0 &&
                                   LocationId != "volcano_foot" && !fromBucket))
        {
            if (!Holds(Noun.Gourd))
            {
                Say("Vous n'avez pas de gourde.", "You have no gourd.");
                return;
            }
            if (Gourd == 0)
            {
                Say("La gourde est vide.", "The gourd is empty.");
                return;
            }
            Gourd--;
            Quench();
            return;
        }
        if (noun is Noun.Water or Noun.Spring or Noun.None && LocationId == "volcano_foot")
        {
            Quench();
            Say("L'eau de la source est délicieusement fraîche.", "The spring water is deliciously cool.");
            return;
        }
        if (noun is Noun.Water or Noun.Bucket or Noun.Well or Noun.None && fromBucket)
        {
            Clear("bucket_full");
            Quench();
            return;
        }
        if (noun is Noun.Well && LocationId == "well")
        {
            Say("Le puits est bien trop profond. Il faudrait un seau...", "The well is far too deep. You'd need a bucket...");
            return;
        }
        if (noun == Noun.Lava)
        {
            Say("Une idée brûlante, mais non.", "A burning idea, but no.");
            return;
        }
        Say("Il n'y a rien à boire ici.", "There is nothing to drink here.");
    }

    private void Quench()
    {
        Health.Thirst = 0;
        Health.ThirstClock = 0;
        Play(Sfx.Drink);
        Say("Vous buvez à longs traits. Quel bonheur !", "You drink deeply. Bliss!");
    }

    private void Fill(Noun noun)
    {
        if (noun is Noun.Fuel or Noun.Helicopter or Noun.Jerrican || (noun == Noun.None && LocationId == "hangar_in"))
        {
            if (LocationId != "hangar_in")
            {
                Say("Il n'y a rien à remplir ici.", "There is nothing to fill here.");
                return;
            }
            if (!Holds(Noun.Jerrican))
            {
                Say("Avec quoi ? Il vous faut de l'essence.", "With what? You need petrol.");
                return;
            }
            if (Fuelled)
            {
                Say("Le réservoir est déjà plein.", "The tank is already full.");
                return;
            }
            Set("fuelled");
            Play(Sfx.Drink);
            Say("Vous videz le jerricane dans le réservoir de l'hélicoptère. Le plein est fait !",
                "You empty the jerrycan into the helicopter's tank. It is full!");
            return;
        }
        if (noun is Noun.Gourd or Noun.None or Noun.Water)
        {
            if (!Holds(Noun.Gourd))
            {
                Say("Vous n'avez pas de gourde.", "You have no gourd.");
                return;
            }
            bool bucket = BucketFull && (Holds(Noun.Bucket) || (LocationId == "well" && BucketTied));
            if (LocationId == "volcano_foot" || bucket)
            {
                if (bucket && LocationId != "volcano_foot")
                    Clear("bucket_full");
                Gourd = GourdSips;
                Play(Sfx.Drink);
                Say("Vous remplissez la gourde.", "You fill the gourd.");
                return;
            }
            Say("Il n'y a pas d'eau ici.", "There is no water here.");
            return;
        }
        Say("Impossible de remplir ça.", "You can't fill that.");
    }

    private void Eat(Noun noun)
    {
        if (noun is Noun.Coconut or Noun.Bananas)
        {
            if (!Holds(noun))
            {
                Say(InView(noun) ? T("Prenez-la d'abord.", "Pick it up first.") : T("Vous ne l'avez pas.", "You don't have it."));
                return;
            }
            _things[noun].Gone = true;
            Health.Hunger = 0;
            Health.HungerClock = 0;
            Play(Sfx.Eat);
            if (noun == Noun.Coconut)
            {
                Award("coconut", 3);
                Say("Vous fendez la noix sur un rocher et vous vous régalez de lait et de chair.",
                    "You split the nut on a rock and feast on the milk and flesh.");
            }
            else
            {
                Say("Les bananes sont mûres à point. Votre faim s'apaise.", "The bananas are perfectly ripe. Your hunger fades.");
            }
            return;
        }
        if (noun is Noun.Tonic or Noun.Aspirin)
        {
            Swallow(noun);
            return;
        }
        if (noun == Noun.None)
        {
            NoNoun();
            return;
        }
        Say("Ce n'est pas comestible !", "That isn't edible!");
    }

    private void Swallow(Noun noun)
    {
        if (noun is Noun.Coconut or Noun.Bananas)
        {
            Eat(noun);
            return;
        }
        if (noun is not (Noun.Tonic or Noun.Aspirin))
        {
            Say(noun == Noun.Serum ? T("Le sérum s'injecte.", "The serum has to be injected.") : T("Pas question !", "No way!"));
            return;
        }
        if (!Holds(noun))
        {
            Say("Vous ne l'avez pas.", "You don't have it.");
            return;
        }
        _things[noun].Gone = true;
        Play(Sfx.Drink);
        if (noun == Noun.Tonic)
        {
            Health.Fatigue = 0;
            Health.FatigueClock = 0;
            Say("Le fortifiant vous redonne des forces !", "The tonic restores your strength!");
        }
        else
        {
            Health.Fever = 0;
            Health.Feverish = false;
            Health.FeverClock = 0;
            Say("L'aspirine fait tomber la fièvre.", "The aspirin brings down the fever.");
        }
    }

    private void Inject(Noun noun)
    {
        if (noun is not (Noun.Serum or Noun.None))
        {
            Say("Pas question !", "No way!");
            return;
        }
        if (!Holds(Noun.Serum) || Serum == 0)
        {
            Say("Vous n'avez pas de sérum.", "You have no serum.");
            return;
        }
        Serum--;
        if (Serum == 0)
            _things[Noun.Serum].Gone = true;
        Health.SpiderBitten = false;
        Health.ScorpionStung = false;
        Health.SpiderVenom = 0;
        Health.ScorpionVenom = 0;
        Play(Sfx.Drink);
        Say("Vous vous injectez le sérum. Le venin est neutralisé.", "You inject yourself with the serum. The venom is neutralised.");
    }

    private void Rest()
    {
        if (Location.Dark && !CanSee)
        {
            Say("Dormir dans le noir, ici ? Trop dangereux.", "Sleep in the dark, here? Too dangerous.");
            return;
        }
        if (LocationId == "dragon" && Alive(Noun.Dragon))
        {
            Say("Dormir devant un dragon ? Drôle d'idée...", "Sleep in front of a dragon? Strange idea...");
            return;
        }
        Health.Fatigue = Math.Max(0, Health.Fatigue - 8);
        Health.FatigueClock = 0;
        Health.ThirstClock += 4;
        Health.HungerClock += 4;
        Say("Vous vous reposez un moment. Vous vous sentez moins las.", "You rest for a while. You feel less weary.");
    }

    // ------------------------------------------------------------------ puzzles

    private void Open(Noun noun)
    {
        switch (noun)
        {
            case Noun.Drawer when InView(Noun.Drawer):
                if (DrawerOpen)
                {
                    Say("Il est déjà ouvert.", "It is already open.");
                    return;
                }
                Set("drawer_open");
                Play(Sfx.Door);
                var cig = _things[Noun.Cigarettes];
                if (cig.Hidden)
                {
                    cig.Hidden = false;
                    Say("Dans le tiroir, il y a un paquet de cigarettes.", "In the drawer there is a packet of cigarettes.");
                }
                else
                {
                    Say("Le tiroir est vide.", "The drawer is empty.");
                }
                return;
            case Noun.Cigarettes when Holds(Noun.Cigarettes) || InView(Noun.Cigarettes):
                var key = _things[Noun.Key];
                if (key.Hidden && !key.Carried)
                {
                    if (HandsUsed >= HandsCapacity)
                        PlaceIn(key, LocationId, Facing);
                    else
                        Give(key);
                    Play(Sfx.Take);
                    Say("Pas de cigarettes dans le paquet... mais une clef ! Vous la prenez.",
                        "No cigarettes in the packet... but a key! You take it.");
                }
                else
                {
                    Say("Le paquet est vide.", "The packet is empty.");
                }
                return;
            case Noun.Trapdoor when InView(Noun.Trapdoor):
                if (TrapOpen)
                {
                    Say("Elle est déjà ouverte.", "It is already open.");
                    return;
                }
                if (!Holds(Noun.Key))
                {
                    Play(Sfx.Locked);
                    Say("Elle est fermée par un gros cadenas.", "It is fastened with a big padlock.");
                    return;
                }
                Set("trap_open");
                Award("trapdoor", 5);
                Play(Sfx.Door);
                Say("La clef tourne dans le cadenas ! La trappe s'ouvre sur une échelle qui s'enfonce dans le noir.",
                    "The key turns in the padlock! The trapdoor opens onto a ladder going down into the dark.");
                return;
            case Noun.Grille when LocationId == "cellar" && InView(Noun.Grille):
                if (GrilleOpen)
                {
                    Say("Elle est déjà ouverte.", "It is already open.");
                    return;
                }
                Set("grille_open");
                Play(Sfx.Door);
                Say("La grille s'ouvre en grinçant.", "The grille creaks open.");
                return;
            case Noun.Grille or Noun.RustyGrille when InView(Noun.RustyGrille):
                Say(RustyBroken ? T("Elle est déjà brisée.", "It is already broken.")
                    : T("Elle est rouillée et coincée. Il faudrait la briser.", "It is rusted solid. You would have to break it."));
                return;
            case Noun.Door when InView(Noun.Door):
                if (DoorOpen)
                {
                    Say("Elle est déjà ouverte.", "It is already open.");
                    return;
                }
                if (!SageAsked)
                {
                    Play(Sfx.Locked);
                    Say("La porte ne bouge pas d'un pouce. Une force mystérieuse la retient.",
                        "The door won't budge an inch. A mysterious force holds it shut.");
                    return;
                }
                Set("door_open");
                Play(Sfx.Door);
                Say("La porte s'ouvre lentement. Une odeur de soufre et de chair brûlée vous prend à la gorge.",
                    "The door swings slowly open. A smell of sulphur and burnt flesh catches in your throat.");
                return;
            case Noun.Bottle when Holds(Noun.Bottle) || InView(Noun.Bottle):
                Say("Il y a un message dans la bouteille. Lisez-le !", "There is a message in the bottle. Read it!");
                return;
            case Noun.Kit when InView(Noun.Kit):
                Take(Noun.Kit);
                return;
            case Noun.Hangar or Noun.Door when LocationId == "hangar_yard" && Facing == Dir.East:
                Say("Les portes du hangar ne s'ouvrent que de l'intérieur.", "The hangar doors only open from the inside.");
                return;
            case Noun.Hangar when LocationId == "hangar_in":
                Press(Noun.Button);
                return;
            case Noun.None:
                NoNoun();
                return;
        }
        if (Find(noun, true) == null)
            NotHere();
        else
            Say("Ça ne s'ouvre pas.", "That doesn't open.");
    }

    private void Throw(Noun noun, Noun target)
    {
        if (noun == Noun.None)
        {
            NoNoun();
            return;
        }
        if (!Holds(noun))
        {
            Say("Vous ne l'avez pas.", "You don't have it.");
            return;
        }
        var t = _things[noun];
        if (noun == Noun.Club && InView(Noun.Spider) && Alive(Noun.Spider))
        {
            Set(Noun.Spider + "_dead");
            _things[Noun.Spider].Place = new Placement(140, 129, 0);
            _things[Noun.Spider].Facing = Facing;
            PlaceIn(t, LocationId, Facing);
            Award("spider", 5);
            Play(Sfx.Hit);
            Say("En plein dans le mille ! La mygale est écrasée.", "Bull's-eye! The tarantula is crushed.");
            return;
        }
        if (noun == Noun.Knife && InView(Noun.Cobra) && Alive(Noun.Cobra))
        {
            Set(Noun.Cobra + "_dead");
            PlaceIn(t, LocationId, Facing);
            Award("cobra", 5);
            Play(Sfx.Hit);
            Say("Le couteau tranche la tête du cobra !", "The knife slices off the cobra's head!");
            return;
        }
        if (noun == Noun.Sabre && InView(Noun.Gorilla))
        {
            _things[Noun.Gorilla].Gone = true;
            PlaceIn(t, "den", Dir.North);
            Award("gorilla", 5);
            Play(Sfx.Roar);
            Say("Le gorille attrape le sabre au vol, le contemple... et s'enfuit avec vers l'ouest !",
                "The gorilla catches the sabre in mid-air, stares at it... and runs off with it to the west!");
            return;
        }
        if (InView(Noun.Gorilla))
        {
            PlaceIn(t, LocationId, Facing);
            Play(Sfx.Roar);
            Say("Le gorille rattrape l'objet, le flaire et le jette par terre avec mépris.",
                "The gorilla catches it, sniffs it and throws it down in disgust.");
            return;
        }
        if (InView(Noun.Dragon) && Alive(Noun.Dragon))
        {
            PlaceIn(t, LocationId, Facing);
            Say("L'objet rebondit sur les écailles du dragon. Il ricane.", "It bounces off the dragon's scales. The dragon sneers.");
            return;
        }
        if (noun == Noun.Torch && TorchLit && LocationId == "haunted")
        {
            PlaceIn(t, LocationId, Facing);
            Say("La torche roule sur le sol.", "The torch rolls across the floor.");
            return;
        }
        PlaceIn(t, UpPalm ? "palm" : LocationId, UpPalm ? Dir.South : Facing);
        Play(Sfx.Drop);
        Say(F("Vous lancez {0}. Il retombe un peu plus loin.", "You throw {0}. It lands a little way off.", Name(t)));
    }

    private void Cut(Noun noun)
    {
        if (noun == Noun.Plant && InView(Noun.Plant) && Alive(Noun.Plant))
        {
            if (!Holds(Noun.Knife) && !Holds(Noun.Sabre))
            {
                Health.Injury += 6;
                Play(Sfx.Hurt);
                Say("Avec vos ongles ? La plante vous mord les doigts !", "With your fingernails? The plant bites your fingers!");
                return;
            }
            Set(Noun.Plant + "_dead");
            Award("plant", 5);
            Play(Sfx.Hit);
            Say("Vous tranchez la tige de la plante. Elle s'effondre en sifflant.", "You slash through the plant's stem. It collapses, hissing.");
            return;
        }
        if (noun == Noun.Rope)
        {
            Say("Vous pourriez en avoir besoin.", "You might need it.");
            return;
        }
        if (noun == Noun.Dragon || (noun == Noun.None && InView(Noun.Dragon)))
        {
            Behead(Noun.Dragon);
            return;
        }
        if (noun == Noun.None)
            NoNoun();
        else if (Find(noun, true) == null)
            NotHere();
        else
            Say("Ça ne sert à rien.", "That achieves nothing.");
    }

    private void Dig()
    {
        if (!Holds(Noun.Shovel))
        {
            Say("À mains nues ? Il vous faudrait un outil.", "With your bare hands? You need a tool.");
            return;
        }
        var earth = _things[Noun.Earth];
        if (InView(Noun.Earth))
        {
            earth.Gone = true;
            _things[Noun.Trapdoor].Hidden = false;
            Award("dig", 4);
            Play(Sfx.Dig);
            Say("Vous déblayez la terre à grands coups de pelle... Une trappe apparaît dans le sol !",
                "You shovel the earth away... A trapdoor appears in the ground!");
            return;
        }
        Play(Sfx.Dig);
        Say("Vous creusez un trou. Il n'y a rien.", "You dig a hole. There is nothing there.");
    }

    private void Light(Noun noun)
    {
        if (noun is not (Noun.Torch or Noun.None))
        {
            Say("Ça ne s'allume pas.", "That won't light.");
            return;
        }
        if (!Holds(Noun.Torch))
        {
            Say("Vous n'avez rien à allumer.", "You have nothing to light.");
            return;
        }
        if (TorchLit)
        {
            Say("Elle est déjà allumée.", "It is already lit.");
            return;
        }
        if (LocationId != "crater")
        {
            Say("Avec quoi ? Il vous faudrait du feu.", "With what? You need fire.");
            return;
        }
        Set("torch_lit");
        Award("torch", 5);
        Play(Sfx.Fire);
        Say("Vous approchez la torche de la lave : elle s'enflamme aussitôt !",
            "You hold the torch out over the lava: it bursts into flame!");
    }

    private void Press(Noun noun)
    {
        if (noun is Noun.Button || (noun == Noun.None && InView(Noun.Button)))
        {
            if (!InView(Noun.Button))
            {
                NotHere();
                return;
            }
            if (HangarOpen)
            {
                Say("Les portes sont déjà ouvertes.", "The doors are already open.");
                return;
            }
            Set("hangar_open");
            Play(Sfx.Engine);
            Say("Un moteur se met à ronronner. Les grandes portes du hangar s'ouvrent sur le ciel !",
                "A motor starts to hum. The great hangar doors slide open onto the sky!");
            return;
        }
        var statue = Find(noun is Noun.None ? Noun.Eye : noun, false);
        if (statue?.Noun == Noun.Buddha)
        {
            if (SecretOpen)
            {
                Say("Il ne se passe plus rien.", "Nothing more happens.");
                return;
            }
            Set("secret_open");
            Award("secret", 5);
            Play(Sfx.Door);
            Say("Vous appuyez sur l'oeil de cristal... La statue pivote dans un grondement et dévoile un passage !",
                "You press the crystal eye... The statue swivels with a rumble, revealing a passage!");
            return;
        }
        if (statue?.Noun == Noun.Idol)
        {
            Play(Sfx.Explosion);
            Die(T("Vous appuyez sur l'oeil de l'idole... qui vous explose à la figure ! C'était un piège.",
                "You press the idol's eye... and it blows up in your face! It was a trap."));
            return;
        }
        if (noun == Noun.None || statue == null && noun is Noun.Eye or Noun.Buddha)
            Say("Appuyer sur quoi ?", "Press what?");
        else
            Say("Il ne se passe rien.", "Nothing happens.");
    }

    private void Break(Noun noun)
    {
        if (noun is Noun.Grille or Noun.RustyGrille or Noun.None && InView(Noun.RustyGrille))
        {
            if (RustyBroken)
            {
                Say("Elle est déjà brisée.", "It is already broken.");
                return;
            }
            if (!Holds(Noun.Hammer))
            {
                Say("À mains nues ? Il vous faudrait un outil lourd.", "With your bare hands? You need a heavy tool.");
                return;
            }
            Set("rusty_broken");
            Award("grille", 5);
            Play(Sfx.Hit);
            Say("Trois coups de marteau et la grille rouillée vole en éclats !", "Three blows of the hammer and the rusty grille bursts apart!");
            return;
        }
        if (noun is Noun.Eye or Noun.Buddha or Noun.Idol)
        {
            Say("La pierre est trop dure.", "The stone is too hard.");
            return;
        }
        if (noun == Noun.None)
            NoNoun();
        else
            Say("Vous n'y arrivez pas.", "You can't.");
    }

    private void Tie(Noun noun)
    {
        if (noun is not (Noun.Bucket or Noun.Rope or Noun.None))
        {
            Say("Attacher ça ? À quoi bon.", "Tie that? What for.");
            return;
        }
        if (LocationId != "well" || Facing != Dir.North)
        {
            Say("Il n'y a rien où l'attacher ici.", "There is nothing to tie it to here.");
            return;
        }
        if (BucketTied)
        {
            Say("Le seau est déjà attaché.", "The bucket is already tied.");
            return;
        }
        if (!Holds(Noun.Bucket) || !Holds(Noun.Rope))
        {
            Say("Il vous faut un seau et une corde.", "You need a bucket and a rope.");
            return;
        }
        foreach (var n in new[] { Noun.Bucket, Noun.Rope })
        {
            var t = _things[n];
            t.Carried = false;
            t.Location = n == Noun.Bucket ? "well" : null;
            t.Facing = Dir.North;
            t.Place = new Placement(146, 104, 0);
            t.Hidden = n == Noun.Rope;
        }
        Set("bucket_tied");
        Say("Vous attachez le seau à la corde, et la corde à la poulie du puits.",
            "You tie the bucket to the rope, and the rope to the well's pulley.");
    }

    private void Ask(Noun noun)
    {
        if (noun is Noun.Sage or Noun.None && InView(Noun.Sage))
        {
            Set("sage_asked");
            Award("sage", 5);
            Play(Sfx.Magic);
            Say("Le sage ouvre les yeux : « Le diamant dort derrière le dragon. Seul le sabre des anciens peut " +
                "lui trancher le cou. Va, la porte t'est ouverte. »",
                "The sage opens his eyes: \"The diamond sleeps beyond the dragon. Only the sabre of the ancients " +
                "can cut its neck. Go, the door is open to you.\"");
            return;
        }
        if (noun is Noun.Gorilla or Noun.Dragon or Noun.Ghost or Noun.Cobra or Noun.Spider && Find(noun, false) != null)
        {
            Say("Pour toute réponse, vous n'obtenez qu'un grognement.", "All you get in reply is a growl.");
            return;
        }
        Say("Pas de réponse.", "No answer.");
    }

    private void Behead(Noun noun)
    {
        if (noun is not (Noun.Dragon or Noun.None) || !InView(Noun.Dragon))
        {
            if (InView(Noun.Gorilla))
                Say("Le gorille est bien trop fort.", "The gorilla is far too strong.");
            else
                NotHere();
            return;
        }
        if (!Alive(Noun.Dragon))
        {
            Say("Il est déjà mort.", "It is already dead.");
            return;
        }
        if (!Holds(Noun.Sabre))
        {
            Say("Avec quoi ? Vos dents ?", "With what? Your teeth?");
            return;
        }
        Set(Noun.Dragon + "_dead");
        Award("dragon", 10);
        Play(Sfx.Hit);
        Say("D'un grand coup de sabre, vous tranchez le cou du dragon ! La bête s'effondre dans un fracas terrible.",
            "With a great sweep of the sabre you cut through the dragon's neck! The beast crashes to the ground.");
    }

    private void Kill(Noun noun)
    {
        switch (noun)
        {
            case Noun.Dragon:
                Behead(noun);
                return;
            case Noun.Spider when InView(Noun.Spider) && Alive(Noun.Spider):
                Health.SpiderBitten = true;
                Health.SpiderVenom += 4;
                Play(Sfx.Hurt);
                Say("Vous frappez la mygale à mains nues... elle vous mord ! Il faudrait lui lancer quelque chose.",
                    "You hit the tarantula with your bare hands... it bites you! You should throw something at it.");
                return;
            case Noun.Cobra when InView(Noun.Cobra) && Alive(Noun.Cobra):
                Say("Approcher un cobra ? Il faudrait l'atteindre de loin.", "Get close to a cobra? You'd need to reach it from afar.");
                return;
            case Noun.Plant:
                Cut(noun);
                return;
            case Noun.Gorilla when InView(Noun.Gorilla):
                Health.Injury += 12;
                Play(Sfx.Roar);
                Say("Le gorille vous envoie rouler à terre d'une seule gifle !", "The gorilla sends you sprawling with one slap!");
                return;
            case Noun.Ghost when InView(Noun.Ghost):
                Say("Vos coups passent à travers le fantôme.", "Your blows pass straight through the ghost.");
                return;
            case Noun.Sage when InView(Noun.Sage):
                Say("Le sage lève une main et vous voilà paralysé. Mieux vaut l'interroger.",
                    "The sage raises a hand and you are paralysed. Better to question him.");
                return;
            case Noun.Scorpion:
                Say("Ils sont bien trop nombreux. Mieux vaut des bottes.", "There are far too many of them. Boots would be better.");
                return;
        }
        if (noun == Noun.None)
            NoNoun();
        else
            Say("Ça ne sert à rien.", "That achieves nothing.");
    }

    private void Fire(Noun noun)
    {
        if (!Holds(Noun.Gun))
        {
            Say("Vous n'avez pas d'arme.", "You have no weapon.");
            return;
        }
        _things[Noun.Gun].Gone = true;
        Health.Injury += 22;
        Play(Sfx.Explosion);
        Say("La mitraillette s'enraye... et vous explose entre les mains ! Elle était piégée.",
            "The machine gun jams... and blows up in your hands! It was booby-trapped.");
    }

    private void Fly()
    {
        if (LocationId != "hangar_in")
        {
            Say("Vous battez des bras. Sans succès.", "You flap your arms. Without success.");
            return;
        }
        if (!Aboard)
        {
            Say("Montez d'abord dans l'hélicoptère.", "Climb into the helicopter first.");
            return;
        }
        if (!Fuelled)
        {
            Play(Sfx.Engine);
            Say("Le moteur tousse, crachote et s'arrête. Le réservoir est vide !",
                "The engine coughs, splutters and dies. The tank is empty!");
            return;
        }
        if (!HangarOpen)
        {
            Play(Sfx.Explosion);
            Die(T("L'hélicoptère s'élève... et s'écrase contre les portes fermées du hangar !",
                "The helicopter lifts off... and smashes into the closed hangar doors!"));
            return;
        }
        Award("escape", 10);
        Play(Sfx.Victory);
        bool diamond = Holds(Noun.Diamond);
        Ending = diamond ? Ending.EscapedWithDiamond : Ending.Escaped;
        EndMessage = diamond
            ? T("L'hélicoptère s'élève au-dessus de l'île maudite. Le diamant brille sur vos genoux. La gloire vous attend !",
                "The helicopter rises above the cursed island. The diamond gleams in your lap. Glory awaits!")
            : T("L'hélicoptère s'élève au-dessus de l'île maudite. Vous êtes sauf... mais sans le diamant.",
                "The helicopter rises above the cursed island. You are safe... but without the diamond.");
        Say(EndMessage);
    }

    // ------------------------------------------------------------------ saving

    /// <summary>The whole game as text (saved after every command, and as the part 2 checkpoint).</summary>
    public string Save()
    {
        var sb = new StringBuilder();
        sb.Append("v=1\n");
        sb.Append("loc=").Append(LocationId).Append('\n');
        sb.Append("facing=").Append((int)Facing).Append('\n');
        sb.Append("moves=").Append(Moves).Append('\n');
        sb.Append("score=").Append(Score).Append('\n');
        sb.Append("gourd=").Append(Gourd).Append('\n');
        sb.Append("serum=").Append(Serum).Append('\n');
        sb.Append("dragon=").Append(DragonTurns).Append('\n');
        sb.Append("taken=").Append(_takeCounter).Append('\n');
        sb.Append("health=").Append(Health.Serialize()).Append('\n');
        sb.Append("flags=").Append(string.Join(",", _flags.OrderBy(f => f))).Append('\n');
        sb.Append("visited=").Append(string.Join(",", _visited.OrderBy(f => f))).Append('\n');
        sb.Append("milestones=").Append(string.Join(",", _milestones.OrderBy(f => f))).Append('\n');
        sb.Append("seen=").Append(string.Join(",", _seen.OrderBy(n => n))).Append('\n');
        foreach (var t in _things.Values.OrderBy(t => t.Noun))
        {
            sb.Append("thing.").Append(t.Noun).Append('=')
                .Append(t.Location ?? "-").Append('|')
                .Append((int)t.Facing).Append('|')
                .Append(t.Place.X.ToString(CultureInfo.InvariantCulture)).Append('|')
                .Append(t.Place.Y.ToString(CultureInfo.InvariantCulture)).Append('|')
                .Append(t.Hidden ? 1 : 0).Append('|')
                .Append(t.Gone ? 1 : 0).Append('|')
                .Append(t.Carried ? 1 : 0).Append('|')
                .Append(t.Worn ? 1 : 0).Append('|')
                .Append(t.TakenAt).Append('\n');
        }
        return sb.ToString();
    }

    /// <summary>Restores a saved game, or returns null if the text is not a valid save.</summary>
    public static Adventure Load(string text, ISoundPlayer sound = null)
    {
        try
        {
            var a = new Adventure(sound);
            var values = new Dictionary<string, string>();
            foreach (var line in text.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            {
                int eq = line.IndexOf('=');
                if (eq > 0)
                    values[line[..eq]] = line[(eq + 1)..];
            }
            if (!values.TryGetValue("v", out var version) || version != "1")
                return null;
            if (!Island.Locations.ContainsKey(values["loc"]))
                return null;
            a.LocationId = values["loc"];
            a.Facing = (Dir)(int.Parse(values["facing"]) & 3);
            a.Moves = int.Parse(values["moves"]);
            a.Score = int.Parse(values["score"]);
            a.Gourd = int.Parse(values["gourd"]);
            a.Serum = int.Parse(values["serum"]);
            a.DragonTurns = int.Parse(values["dragon"]);
            a._takeCounter = int.Parse(values["taken"]);
            a.Health = Health.Deserialize(values["health"]);
            a._flags.Clear();
            Split(values["flags"], a._flags);
            a._visited.Clear();
            Split(values["visited"], a._visited);
            Split(values["milestones"], a._milestones);
            if (values.TryGetValue("seen", out var seen))
                foreach (var n in seen.Split(',', StringSplitOptions.RemoveEmptyEntries))
                    if (Enum.TryParse<Noun>(n, out var noun))
                        a._seen.Add(noun);
            foreach (var t in a._things.Values)
            {
                if (!values.TryGetValue("thing." + t.Noun, out var s))
                    continue;
                var p = s.Split('|');
                t.Location = p[0] == "-" ? null : p[0];
                t.Facing = (Dir)(int.Parse(p[1]) & 3);
                t.Place = new Placement(float.Parse(p[2], CultureInfo.InvariantCulture),
                    float.Parse(p[3], CultureInfo.InvariantCulture), 0);
                t.Hidden = p[4] == "1";
                t.Gone = p[5] == "1";
                t.Carried = p[6] == "1";
                t.Worn = p[7] == "1";
                t.TakenAt = int.Parse(p[8]);
            }
            return a;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static void Split(string list, HashSet<string> into)
    {
        foreach (var f in list.Split(',', StringSplitOptions.RemoveEmptyEntries))
            into.Add(f);
    }
}
