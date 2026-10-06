using System;
using System.Collections.Generic;
using Diamond.Core.Localization;

namespace Diamond.Core.World;

/// <summary>
/// The cursed island and the tunnels beneath it: every place, its four views and its exits, and
/// where every object, creature and feature starts. Part 1 is the island's surface; part 2 is the
/// underground, reached through the trapdoor buried at the corner of the hangar.
/// </summary>
public static class Island
{
    public const string Start = "wreck";
    public const Dir StartFacing = Dir.North;

    /// <summary>Where part 2 begins (past the grille under the trapdoor).</summary>
    public const string Part2Start = "entry";
    public const Dir Part2Facing = Dir.North;

    /// <summary>Pseudo-location of things up the coconut palm.</summary>
    public const string PalmTop = "palm_top";

    public static IReadOnlyDictionary<string, Location> Locations { get; } = BuildLocations();
    public static IReadOnlyDictionary<Noun, ThingDef> Things { get; } = BuildThings();

    private static Loc T(string fr, string en) => new(fr, en);

    private static Dictionary<string, Location> BuildLocations()
    {
        var map = new Dictionary<string, Location>();

        void Add(string id, Part part, Loc name, Loc description, string exits, string views, bool dark = false,
            bool scorpions = false, bool mosquitoes = false, bool hot = false)
        {
            var loc = new Location(id, part, name, description)
            {
                Dark = dark,
                Scorpions = scorpions,
                Mosquitoes = mosquitoes,
                Hot = hot,
            };
            foreach (var e in exits.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                loc.Exits[DirExtensions.Parse(e[0])] = e[2..];
            foreach (var v in views.Split(' ', StringSplitOptions.RemoveEmptyEntries))
            {
                bool mirror = v.EndsWith('~');
                loc.Views[DirExtensions.Parse(v[0])] = new View(v[2..].TrimEnd('~'), mirror);
            }
            if (loc.Views.Count != 4)
                throw new InvalidOperationException(id + " needs four views");
            map.Add(id, loc);
        }

        const Part I = Part.Island, U = Part.Underground;

        // ------------------------------------------------------------------ part 1: the island
        Add("beach_w", I, T("Pointe ouest", "West point"),
            T("La plage se termine en pointe face au large. Au nord se dresse une vieille tour.",
              "The beach narrows to a point facing the open sea. To the north stands an old tower."),
            "E:wreck N:tower_foot", "N:beach_land E:beach_along S:beach_sea W:beach_sea");
        Add("wreck", I, T("Plage du naufrage", "Shipwreck beach"),
            T("Votre bateau s'est fracassé sur les récifs. Vous êtes seul sur une plage de sable blanc.",
              "Your boat has broken up on the reef. You are alone on a beach of white sand."),
            "N:jungle_edge E:beach_s W:beach_w", "N:beach_land E:beach_along S:beach_wreck W:beach_along~");
        Add("beach_s", I, T("Grande plage", "Long beach"),
            T("Une longue plage brûlante. Des crabes fuient à votre approche.",
              "A long, scorching beach. Crabs scuttle away as you approach."),
            "W:wreck E:beach_e N:hut_out", "N:beach_land E:beach_along S:beach_sea W:beach_along~");
        Add("beach_e", I, T("Petite anse", "Little cove"),
            T("Une petite anse abritée. Un sentier s'enfonce dans la jungle.",
              "A sheltered little cove. A path leads into the jungle."),
            "W:beach_s E:palm N:path_fork", "N:beach_land E:beach_along S:beach_sea W:beach_along~");
        Add("palm", I, T("Le cocotier", "The coconut palm"),
            T("Un grand cocotier penche au-dessus du sable, chargé de noix.",
              "A tall coconut palm leans out over the sand, heavy with nuts."),
            "W:beach_e N:jungle_e", "N:beach_land E:beach_end S:beach_sea W:beach_along~");
        Add("tower_foot", I, T("Au pied de la tour", "Foot of the tower"),
            T("Une tour en ruine, bâtie par une civilisation disparue, domine la jungle.",
              "A ruined tower, built by a vanished civilisation, looms over the jungle."),
            "S:beach_w E:jungle_edge N:tower_in", "N:tower_out E:jungle_path S:jungle_beach W:jungle_wall");
        Add("jungle_edge", I, T("Lisière de la jungle", "Edge of the jungle"),
            T("Les cris des oiseaux résonnent sous les arbres géants.",
              "Bird calls echo under the giant trees."),
            "S:wreck W:tower_foot E:hut_out N:jungle_n", "N:jungle_path E:jungle_path S:jungle_beach W:jungle_path~");
        Add("hut_out", I, T("Devant la cabane", "Outside the hut"),
            T("Une cabane de bambou, abandonnée depuis longtemps.",
              "A bamboo hut, long abandoned."),
            "S:beach_s W:jungle_edge E:path_fork N:hut_in", "N:hut_out E:jungle_path S:jungle_beach W:jungle_path~");
        Add("path_fork", I, T("Croisée des sentiers", "Crossing paths"),
            T("Plusieurs sentiers se croisent ici. Celui du nord est très étroit.",
              "Several paths cross here. The one to the north is very narrow."),
            "S:beach_e W:hut_out E:jungle_e N:narrow", "N:jungle_path E:jungle_path S:jungle_beach W:jungle_path~");
        Add("jungle_e", I, T("Jungle", "Jungle"),
            T("Une chaleur moite monte du sol. Vers le nord, ça sent le marécage.",
              "A muggy heat rises from the ground. To the north there is a smell of swamp."),
            "S:palm W:path_fork N:marsh", "N:jungle_path E:jungle_wall S:jungle_beach W:jungle_path~");
        Add("tower_in", I, T("Dans la tour", "Inside the tower"),
            T("L'intérieur de la tour est sombre et humide. Quelque chose bouge sur le mur...",
              "Inside, the tower is dark and damp. Something moves on the wall..."),
            "S:tower_foot", "N:tower_in E:tower_in S:tower_in_door W:tower_in~");
        Add("jungle_n", I, T("Jungle épaisse", "Thick jungle"),
            T("Des lianes pendent de partout. On ne voit plus le ciel.",
              "Lianas hang everywhere. You can no longer see the sky."),
            "S:jungle_edge N:banana", "N:jungle_path E:jungle_wall S:jungle_path~ W:jungle_wall~");
        Add("hut_in", I, T("Dans la cabane", "Inside the hut"),
            T("Une odeur de tabac froid. Un explorateur a vécu ici.",
              "A smell of stale tobacco. An explorer once lived here."),
            "S:hut_out", "N:hut_in E:hut_in S:hut_in_door W:hut_in~");
        Add("narrow", I, T("Sentier étroit", "Narrow path"),
            T("Le sentier serpente entre des rochers couverts de mousse.",
              "The path winds between moss-covered rocks."),
            "S:path_fork N:skeleton", "N:jungle_path E:jungle_wall S:jungle_path~ W:jungle_wall~");
        Add("marsh", I, T("Marais", "Swamp"),
            T("Une eau croupie, des nuées de moustiques... L'air est fiévreux.",
              "Stagnant water and clouds of mosquitoes... The air is feverish."),
            "S:jungle_e E:clearing", "N:marsh_wall E:marsh S:jungle_path W:marsh_wall~", mosquitoes: true);
        Add("clearing", I, T("Clairière fleurie", "Flowery clearing"),
            T("Des fleurs énormes aux couleurs vives. Leur parfum est entêtant.",
              "Huge, brightly coloured flowers. Their scent is heady."),
            "W:marsh", "N:clearing E:clearing S:clearing~ W:marsh");
        Add("banana", I, T("Bananeraie", "Banana grove"),
            T("Des bananiers sauvages poussent dans cette trouée.",
              "Wild banana trees grow in this gap in the forest."),
            "S:jungle_n", "N:clearing E:jungle_wall S:jungle_path W:jungle_wall~");
        Add("skeleton", I, T("Clairière du squelette", "Skeleton clearing"),
            T("Un explorateur n'est jamais reparti d'ici... Steven Smith ?",
              "An explorer never left this place... Steven Smith?"),
            "S:narrow E:scree N:volcano_foot", "N:volcano E:rocks_path S:jungle_path W:jungle_wall");
        Add("scree", I, T("Éboulis", "Scree"),
            T("Des pierres noires roulent sous vos pieds. Des scorpions s'y cachent.",
              "Black stones roll underfoot. Scorpions hide among them."),
            "W:skeleton E:rocks N:lava_field", "N:rocks_path E:rocks_path S:rocks_wall W:jungle_path", scorpions: true);
        Add("rocks", I, T("Rochers brûlants", "Scorching rocks"),
            T("Le soleil fait cuire ces rochers. Au loin, un toit de tôle rouillée.",
              "The sun bakes these rocks. In the distance, a roof of rusty iron."),
            "W:scree E:hangar_yard", "N:rocks_wall E:rocks_path S:rocks_wall~ W:rocks_path~", scorpions: true, hot: true);
        Add("hangar_yard", I, T("Devant le hangar", "In front of the hangar"),
            T("Un immense hangar de tôle, vestige d'une ancienne base militaire. Ses portes sont closes.",
              "A huge iron hangar, the remains of an old military base. Its doors are shut."),
            "W:rocks N:hangar_corner", "N:hangar_side E:hangar_out S:rocks_wall W:rocks_path~");
        Add("hangar_corner", I, T("Angle du hangar", "Corner of the hangar"),
            T("Le coin du bâtiment est enfoui sous un amas de terre.",
              "The corner of the building is buried under a heap of earth."),
            "S:hangar_yard", "N:hangar_corner E:hangar_side S:rocks_path W:rocks_wall");
        Add("volcano_foot", I, T("Pied du volcan", "Foot of the volcano"),
            T("Le volcan gronde sourdement. Une source jaillit entre les rochers.",
              "The volcano rumbles. A spring bubbles up between the rocks."),
            "S:skeleton E:lava_field N:slope", "N:volcano E:lava_field S:jungle_path W:spring");
        Add("lava_field", I, T("Coulée de lave", "Lava flow"),
            T("Une coulée de lave refroidie, encore fumante par endroits.",
              "A cooled lava flow, still smoking in places."),
            "W:volcano_foot S:scree", "N:lava_field E:rocks_wall S:rocks_path W:rocks_path~", scorpions: true, hot: true);
        Add("slope", I, T("Flanc du volcan", "Side of the volcano"),
            T("La pente est raide et la cendre brûlante. Vous soufflez comme un phoque.",
              "The slope is steep and the ash is hot. You are out of breath."),
            "S:volcano_foot N:crater", "N:slope_up E:slope_down S:slope_down~ W:slope_down", hot: true);
        Add("crater", I, T("Bord du cratère", "Rim of the crater"),
            T("Tout au fond, un lac de lave bouillonne. La chaleur est terrible.",
              "Far below, a lake of lava seethes. The heat is terrible."),
            "S:slope", "N:crater E:crater_rim S:crater_rim~ W:crater_rim", hot: true);
        Add("cellar", I, T("Sous la trappe", "Under the trapdoor"),
            T("Une cave de pierre. Une échelle remonte vers la lumière ; au nord, une grille.",
              "A stone cellar. A ladder climbs back up to the light; to the north, a grille."),
            "N:entry", "N:tunnel_path E:cave_wall S:cellar W:cave_wall~");

        // ------------------------------------------------------------------ part 2: the underground
        Add("entry", U, T("Galerie d'entrée", "Entrance gallery"),
            T("Des galeries creusées par les anciens. L'air sent la pierre humide.",
              "Galleries dug by the ancients. The air smells of damp stone."),
            "N:buddha E:corridor", "N:cave_opening E:tunnel_path S:tunnel_wall W:cave_wall", dark: true);
        Add("buddha", U, T("Salle du Bouddha", "Hall of the Buddha"),
            T("Un temple souterrain. Un Bouddha de pierre vous fixe de son oeil de cristal.",
              "An underground temple. A stone Buddha stares at you with its crystal eye."),
            "S:entry N:secret", "N:temple_wall E:temple_wall S:cave_opening W:temple_wall~", dark: true);
        Add("secret", U, T("Chambre secrète", "Secret chamber"),
            T("Une petite pièce cachée derrière la statue. L'air y est confiné.",
              "A small room hidden behind the statue. The air is stale."),
            "S:buddha", "N:cave_wall E:cave_wall S:cave_opening W:cave_wall~", dark: true);
        Add("corridor", U, T("Long couloir", "Long corridor"),
            T("Un couloir taillé dans le roc. Vos pas résonnent.",
              "A corridor cut into the rock. Your footsteps echo."),
            "W:entry E:junction", "N:tunnel_wall E:tunnel_path S:tunnel_wall~ W:tunnel_path", dark: true);
        Add("junction", U, T("Carrefour souterrain", "Underground crossroads"),
            T("Trois galeries se rejoignent. Au nord, de longues pointes pendent du plafond.",
              "Three galleries meet here. To the north, long spikes hang from the ceiling."),
            "W:corridor E:store N:stalactites", "N:stalactites E:tunnel_path S:tunnel_wall W:tunnel_path", dark: true);
        Add("store", U, T("Réserve", "Storeroom"),
            T("Des caisses éventrées et des outils rouillés. Au nord, une vieille grille.",
              "Broken crates and rusty tools. To the north, an old grille."),
            "W:junction E:deadend N:haunted", "N:tunnel_path E:tunnel_path S:cave_wall W:tunnel_path", dark: true);
        Add("deadend", U, T("Cul-de-sac", "Dead end"),
            T("La galerie s'arrête net. Des ossements jonchent le sol.",
              "The gallery stops dead. Bones litter the floor."),
            "W:store", "N:cave_wall E:tunnel_wall S:cave_wall~ W:tunnel_path", dark: true);
        Add("stalactites", U, T("Galerie des stalactites", "Gallery of stalactites"),
            T("Des stalactites acérées pendent au-dessus de votre tête. Certaines tiennent à peine...",
              "Sharp stalactites hang over your head. Some are barely holding on..."),
            "S:junction N:well", "N:stalactites E:cave_wall S:stalactites~ W:cave_wall~", dark: true);
        Add("well", U, T("Salle du puits", "Well room"),
            T("Un puits très ancien. En face, une statue au regard inquiétant.",
              "A very old well. Opposite, a statue with an unsettling stare."),
            "S:stalactites W:fallen", "N:cave_wall E:cave_wall~ S:tunnel_path W:tunnel_path", dark: true);
        Add("fallen", U, T("Galerie effondrée", "Collapsed gallery"),
            T("Le plafond s'est effondré. Une inscription est gravée dans la roche.",
              "The roof has collapsed. An inscription is carved into the rock."),
            "E:well", "N:cave_wall E:tunnel_path S:cave_wall~ W:tunnel_wall", dark: true);
        Add("haunted", U, T("Galerie hantée", "Haunted gallery"),
            T("Un froid glacial vous saisit. Des gémissements montent de l'ombre.",
              "An icy chill grips you. Moans rise from the shadows."),
            "S:store N:crossing", "N:tunnel_path E:cave_wall S:tunnel_path~ W:cave_wall~", dark: true);
        Add("crossing", U, T("Croisement", "Crossroads"),
            T("Des galeries partent de tous côtés. Une lueur verte filtre à l'est.",
              "Galleries lead off on every side. A green glow filters from the east."),
            "S:haunted E:lit N:gorilla", "N:cave_opening E:tunnel_path S:tunnel_path~ W:tunnel_wall", dark: true);
        Add("lit", U, T("Salle éclairée", "Glowing chamber"),
            T("Des cristaux phosphorescents baignent la salle d'une lumière verte.",
              "Phosphorescent crystals bathe the chamber in green light."),
            "W:crossing N:sabre_end", "N:lit_room E:lit_room~ S:lit_room W:lit_room~");
        Add("sabre_end", U, T("Fond de la galerie", "End of the gallery"),
            T("Le fond d'une galerie. Un guerrier a dû mourir ici.",
              "The end of a gallery. A warrior must have died here."),
            "S:lit", "N:tunnel_wall E:cave_wall S:tunnel_path W:cave_wall~", dark: true);
        Add("gorilla", U, T("Grande caverne", "Great cavern"),
            T("Une forte odeur de fauve emplit cette caverne.",
              "A strong smell of wild animal fills this cavern."),
            "S:crossing N:sage W:den", "N:cave_opening E:cave_wall S:tunnel_path W:tunnel_path~", dark: true);
        Add("den", U, T("Tanière", "Den"),
            T("Un lit de feuilles et de branchages. C'est ici que dort le gorille.",
              "A bed of leaves and branches. This is where the gorilla sleeps."),
            "E:gorilla", "N:cave_wall E:tunnel_path S:cave_wall~ W:cave_wall", dark: true);
        Add("sage", U, T("Salle du sage", "Sage's chamber"),
            T("Un vieillard semble méditer ici depuis des siècles.",
              "An old man seems to have been meditating here for centuries."),
            "S:gorilla E:dragon", "N:cave_wall E:cave_wall~ S:cave_opening W:cave_wall", dark: true);
        Add("dragon", U, T("Antre du dragon", "Dragon's lair"),
            T("Une caverne immense. Le sol est couvert d'ossements calcinés.",
              "A vast cavern. The floor is covered with charred bones."),
            "W:sage E:diamond_room", "N:lair E:lair S:lair~ W:cave_opening", dark: true);
        Add("diamond_room", U, T("Chambre du diamant", "Chamber of the diamond"),
            T("Un rayon de lumière tombe du plafond sur un piédestal sculpté.",
              "A ray of light falls from the ceiling onto a carved pedestal."),
            "W:dragon N:tunnel", "N:tunnel_path E:diamond_room S:cave_wall W:cave_opening");
        Add("tunnel", U, T("Tunnel montant", "Rising tunnel"),
            T("Le tunnel monte en pente douce. L'air sent l'huile et l'essence.",
              "The tunnel climbs gently. The air smells of oil and petrol."),
            "S:diamond_room N:ramp", "N:tunnel_path E:tunnel_wall S:tunnel_path~ W:tunnel_wall~", dark: true);
        Add("ramp", U, T("Rampe bétonnée", "Concrete ramp"),
            T("Une rampe de béton remonte vers un grand bâtiment.",
              "A concrete ramp leads up into a large building."),
            "S:tunnel N:hangar_in", "N:tunnel_path E:cave_wall S:tunnel_path~ W:cave_wall~", dark: true);
        Add("hangar_in", U, T("Dans le hangar", "Inside the hangar"),
            T("Un vieil hélicoptère dort sous la poussière. Il a l'air intact !",
              "An old helicopter slumbers under the dust. It looks intact!"),
            "S:ramp", "N:hangar_in E:hangar_in_doors S:hangar_in_ramp W:hangar_in~");

        return map;
    }

    private static Dictionary<Noun, ThingDef> BuildThings()
    {
        var d = new Dictionary<Noun, ThingDef>();

        void Add(Noun noun, Loc name, bool portable, float height, string sprite, bool wearable = false) =>
            d.Add(noun, new ThingDef(noun, name, portable, height, sprite) { Wearable = wearable });

        // Portable objects (name with its article, as used in sentences).
        Add(Noun.Club, T("une massue", "a club"), true, 7, "club");
        Add(Noun.Gourd, T("une gourde", "a gourd"), true, 12, "gourd");
        Add(Noun.Knife, T("un couteau", "a knife"), true, 5, "knife");
        Add(Noun.Cigarettes, T("un paquet de cigarettes", "a packet of cigarettes"), true, 5, "cigarettes");
        Add(Noun.Key, T("une clef", "a key"), true, 5, "key");
        Add(Noun.Torch, T("une torche", "a torch"), true, 6, "torch");
        Add(Noun.Boots, T("des bottes", "some boots"), true, 14, "boots", wearable: true);
        Add(Noun.Kit, T("une trousse de survie", "a survival kit"), true, 11, "kit");
        Add(Noun.Tonic, T("un fortifiant", "a tonic"), true, 9, "tonic");
        Add(Noun.Serum, T("un sérum", "a serum"), true, 8, "serum");
        Add(Noun.Aspirin, T("un cachet d'aspirine", "an aspirin tablet"), true, 4, "aspirin");
        Add(Noun.Bandage, T("une bande", "a bandage"), true, 5, "bandage");
        Add(Noun.Coconut, T("une noix de coco", "a coconut"), true, 9, "coconut");
        Add(Noun.Bananas, T("des bananes", "some bananas"), true, 9, "bananas");
        Add(Noun.Shovel, T("une pelle", "a shovel"), true, 34, "shovel");
        Add(Noun.Bottle, T("une bouteille", "a bottle"), true, 9, "bottle");
        Add(Noun.Gun, T("une mitraillette", "a machine gun"), true, 8, "gun");
        Add(Noun.Rope, T("une corde", "a rope"), true, 9, "rope");
        Add(Noun.Helmet, T("un casque", "a helmet"), true, 9, "helmet", wearable: true);
        Add(Noun.Hammer, T("un marteau", "a hammer"), true, 10, "hammer");
        Add(Noun.Bucket, T("un seau", "a bucket"), true, 13, "bucket");
        Add(Noun.Sabre, T("un sabre", "a sabre"), true, 6, "sabre");
        Add(Noun.Diamond, T("le diamant", "the diamond"), true, 14, "diamond");
        Add(Noun.Jerrican, T("un jerricane", "a jerrycan"), true, 16, "jerrican");

        // Features and creatures.
        Add(Noun.Drawer, T("une table à tiroir", "a table with a drawer"), false, 36, "table");
        Add(Noun.Skeleton, T("un squelette", "a skeleton"), false, 16, "skeleton");
        Add(Noun.Plant, T("une plante carnivore", "a carnivorous plant"), false, 64, "plant");
        Add(Noun.Palm, T("un cocotier", "a coconut palm"), false, 124, "palm");
        Add(Noun.Earth, T("un amas de terre", "a heap of earth"), false, 26, "earth");
        Add(Noun.Trapdoor, T("une trappe", "a trapdoor"), false, 10, "trapdoor");
        Add(Noun.Spider, T("une mygale géante", "a giant tarantula"), false, 26, "spider");
        Add(Noun.Cobra, T("un cobra cracheur", "a spitting cobra"), false, 36, "cobra");
        Add(Noun.Grille, T("une grille", "a grille"), false, 72, "grille");
        Add(Noun.Buddha, T("un Bouddha de pierre", "a stone Buddha"), false, 92, "buddha");
        Add(Noun.RustyGrille, T("une grille rouillée", "a rusty grille"), false, 72, "rusty_grille");
        Add(Noun.Well, T("un puits", "a well"), false, 40, "well");
        Add(Noun.Idol, T("une idole", "an idol"), false, 76, "statue");
        Add(Noun.Inscription, T("une inscription", "an inscription"), false, 30, "");
        Add(Noun.Ghost, T("un fantôme", "a ghost"), false, 64, "ghost");
        Add(Noun.Gorilla, T("un gorille énorme", "a huge gorilla"), false, 84, "gorilla");
        Add(Noun.Sage, T("un vieux sage", "an old sage"), false, 58, "sage");
        Add(Noun.Door, T("une lourde porte", "a heavy door"), false, 78, "door");
        Add(Noun.Dragon, T("un dragon", "a dragon"), false, 112, "dragon");
        Add(Noun.Helicopter, T("un hélicoptère", "a helicopter"), false, 96, "helicopter");
        Add(Noun.Button, T("un gros bouton rouge", "a big red button"), false, 14, "button");
        return d;
    }

    /// <summary>Where each thing starts: location, facing, centre x, ground y, and whether it is hidden.</summary>
    public static IEnumerable<(Noun noun, string location, Dir facing, Placement place, bool hidden)> StartPositions()
    {
        static Placement P(float x, float y = 128, float h = 0) => new(x, y, h);

        // Island.
        yield return (Noun.Club, "wreck", Dir.East, P(150, 126), false);
        yield return (Noun.Bottle, "wreck", Dir.South, P(84, 129), false);
        yield return (Noun.Gourd, "hut_in", Dir.East, P(100, 126), false);
        yield return (Noun.Drawer, "hut_in", Dir.North, P(120, 124), false);
        yield return (Noun.Cigarettes, "hut_in", Dir.North, P(150, 130), true);
        yield return (Noun.Key, null, Dir.North, P(120), true);
        yield return (Noun.Knife, "hut_in", Dir.West, P(124, 128), false);
        yield return (Noun.Spider, "tower_in", Dir.East, P(124, 74), false);
        yield return (Noun.Torch, "tower_in", Dir.North, P(116, 128), false);
        yield return (Noun.Cobra, "narrow", Dir.North, P(120, 124), false);
        yield return (Noun.Skeleton, "skeleton", Dir.West, P(108, 127), false);
        yield return (Noun.Boots, "skeleton", Dir.West, P(160, 129), false);
        yield return (Noun.Plant, "clearing", Dir.East, P(104, 128), false);
        yield return (Noun.Kit, "clearing", Dir.East, P(168, 129), false);
        yield return (Noun.Tonic, null, Dir.East, P(64, 130), true);
        yield return (Noun.Serum, null, Dir.East, P(88, 131), true);
        yield return (Noun.Aspirin, null, Dir.East, P(150, 131), true);
        yield return (Noun.Bandage, null, Dir.East, P(184, 130), true);
        yield return (Noun.Bananas, "banana", Dir.North, P(120, 127), false);
        yield return (Noun.Palm, "palm", Dir.South, P(150, 132), false);
        yield return (Noun.Coconut, PalmTop, Dir.South, P(120, 92), false);
        yield return (Noun.Shovel, "hangar_yard", Dir.North, P(92, 128), false);
        yield return (Noun.Gun, "hangar_yard", Dir.South, P(128, 129), false);
        yield return (Noun.Earth, "hangar_corner", Dir.North, P(120, 128), false);
        yield return (Noun.Trapdoor, "hangar_corner", Dir.North, P(120, 131), true);
        yield return (Noun.Grille, "cellar", Dir.North, P(120, 130), false);

        // Underground.
        yield return (Noun.Rope, "entry", Dir.West, P(120, 127), false);
        yield return (Noun.Buddha, "buddha", Dir.North, P(120, 132), false);
        yield return (Noun.Helmet, "secret", Dir.North, P(120, 127), false);
        yield return (Noun.Hammer, "store", Dir.South, P(110, 127), false);
        yield return (Noun.RustyGrille, "store", Dir.North, P(120, 130), false);
        yield return (Noun.Bucket, "deadend", Dir.North, P(120, 127), false);
        yield return (Noun.Well, "well", Dir.North, P(120, 130), false);
        yield return (Noun.Idol, "well", Dir.East, P(120, 130), false);
        yield return (Noun.Inscription, "fallen", Dir.West, P(120, 92), false);
        yield return (Noun.Ghost, "haunted", Dir.North, P(120, 118), false);
        yield return (Noun.Sabre, "sabre_end", Dir.North, P(120, 127), false);
        yield return (Noun.Gorilla, "gorilla", Dir.North, P(120, 132), false);
        yield return (Noun.Sage, "sage", Dir.North, P(120, 128), false);
        yield return (Noun.Door, "sage", Dir.East, P(120, 131), false);
        yield return (Noun.Dragon, "dragon", Dir.East, P(124, 132), false);
        yield return (Noun.Diamond, "diamond_room", Dir.East, P(120, 97), false);
        yield return (Noun.Jerrican, "ramp", Dir.East, P(120, 127), false);
        yield return (Noun.Helicopter, "hangar_in", Dir.North, P(120, 131), false);
        yield return (Noun.Button, "hangar_in", Dir.West, P(120, 84), false);
    }
}
