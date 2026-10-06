using System;
using System.Collections.Generic;
using Diamond.Core.Localization;

namespace Diamond.Core.World;

/// <summary>The four directions the player can face. Turning right adds one.</summary>
public enum Dir
{
    North,
    East,
    South,
    West,
}

public static class DirExtensions
{
    public static Dir Right(this Dir d) => (Dir)(((int)d + 1) & 3);
    public static Dir Left(this Dir d) => (Dir)(((int)d + 3) & 3);
    public static Dir Back(this Dir d) => (Dir)(((int)d + 2) & 3);

    public static Dir Parse(char c) => c switch
    {
        'N' => Dir.North,
        'E' => Dir.East,
        'S' => Dir.South,
        'W' => Dir.West,
        _ => throw new ArgumentException("bad direction " + c),
    };
}

/// <summary>Everything the player can name: objects, creatures, features and a few abstract nouns.</summary>
public enum Noun
{
    None,
    // ---- island ----
    Club,
    Gourd,
    Knife,
    Drawer,
    Cigarettes,
    Key,
    Torch,
    Boots,
    Skeleton,
    Plant,
    Kit,
    Tonic,
    Serum,
    Aspirin,
    Bandage,
    Coconut,
    Palm,
    Bananas,
    Shovel,
    Earth,
    Trapdoor,
    Bottle,
    Gun,
    Spider,
    Cobra,
    Scorpion,
    Spring,
    Lava,
    Grille,
    // ---- underground ----
    Rope,
    Buddha,
    Helmet,
    Hammer,
    Bucket,
    RustyGrille,
    Well,
    Idol,
    Inscription,
    Ghost,
    Sabre,
    Gorilla,
    Sage,
    Door,
    Dragon,
    Diamond,
    Jerrican,
    Helicopter,
    Button,
    // ---- abstract ----
    Eye,
    Water,
    Fuel,
    Message,
    Hangar,
}

/// <summary>Which half of the adventure a location belongs to.</summary>
public enum Part
{
    Island = 1,
    Underground = 2,
}

/// <summary>What one facing direction of a location shows.</summary>
public sealed record View(string Background, bool Mirror = false);

/// <summary>A place on the island or under it. Every place has four views, one per direction.</summary>
public sealed class Location
{
    public Location(string id, Part part, Loc name, Loc description)
    {
        Id = id;
        Part = part;
        Name = name;
        Description = description;
    }

    public string Id { get; }
    public Part Part { get; }
    public Loc Name { get; }
    public Loc Description { get; }

    /// <summary>Exits by direction (the id of the location reached by walking that way).</summary>
    public Dictionary<Dir, string> Exits { get; } = new();

    /// <summary>The picture seen facing each direction.</summary>
    public Dictionary<Dir, View> Views { get; } = new();

    /// <summary>Underground places are dark without a lit torch.</summary>
    public bool Dark { get; init; }

    /// <summary>Scorpions live among these rocks: walking here without boots gets you stung.</summary>
    public bool Scorpions { get; init; }

    /// <summary>The swamp: mosquitoes give you a fever.</summary>
    public bool Mosquitoes { get; init; }

    /// <summary>Hot ground (the volcano): you tire and thirst faster.</summary>
    public bool Hot { get; init; }

    public override string ToString() => Id;
}

/// <summary>Where a thing is drawn in a view: centre x and ground line y in picture pixels, and height.</summary>
public readonly record struct Placement(float X, float Y, float Height);

/// <summary>The fixed description of an object, creature or feature.</summary>
public sealed class ThingDef
{
    public ThingDef(Noun noun, Loc name, bool portable, float height, string sprite)
    {
        Noun = noun;
        Name = name;
        Portable = portable;
        Height = height;
        Sprite = sprite;
    }

    public Noun Noun { get; }
    public Loc Name { get; }

    /// <summary>Can be taken and carried.</summary>
    public bool Portable { get; }

    /// <summary>Height in picture pixels when standing in the foreground.</summary>
    public float Height { get; }

    /// <summary>Sprite name (Art/&lt;sprite&gt;.png); states may substitute another.</summary>
    public string Sprite { get; }

    /// <summary>Worn things (boots, helmet) don't take a hand.</summary>
    public bool Wearable { get; init; }
}

/// <summary>Where a thing is now.</summary>
public sealed class ThingState
{
    public ThingState(ThingDef def)
    {
        Def = def;
    }

    public ThingDef Def { get; }
    public Noun Noun => Def.Noun;

    /// <summary>Location id, or null when carried (or gone: see <see cref="Gone"/>).</summary>
    public string Location { get; set; }
    public Dir Facing { get; set; }
    public Placement Place { get; set; }

    /// <summary>Hidden things are in place but not yet visible (the trapdoor under the earth).</summary>
    public bool Hidden { get; set; }

    /// <summary>Destroyed, eaten, drunk or otherwise removed from the game.</summary>
    public bool Gone { get; set; }

    public bool Carried { get; set; }

    /// <summary>Worn (boots, helmet).</summary>
    public bool Worn { get; set; }

    /// <summary>Order in which carried things were picked up (the ghost takes the oldest).</summary>
    public int TakenAt { get; set; }

    public bool IsAt(string location, Dir facing) =>
        !Gone && !Carried && !Hidden && Location == location && Facing == facing;
}
