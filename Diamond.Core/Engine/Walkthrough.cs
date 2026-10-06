using System.Collections.Generic;
using Diamond.Core.World;

namespace Diamond.Core.Engine;

/// <summary>
/// A complete solution, scoring 100. Used by the tests (the island can be completed), by the
/// autopilot that records the store screenshots, and as the hint list in the instructions.
/// </summary>
public static class Walkthrough
{
    private static Command C(Verb verb, Noun noun = Noun.None) => new(verb, noun);

    private static readonly Command L = C(Verb.Left), R = C(Verb.Right), B = C(Verb.Back), F = C(Verb.Forward);

    /// <summary>Part 1: from the shipwreck to the grille under the hangar.</summary>
    public static IReadOnlyList<Command> Part1 { get; } =
    [
        R, C(Verb.Take, Noun.Club),
        R, C(Verb.Take, Noun.Bottle), C(Verb.Read, Noun.Bottle), C(Verb.Drop, Noun.Bottle),
        R, F, R, F, F,                                              // the tower
        R, C(Verb.Throw, Noun.Club), L, C(Verb.Take, Noun.Torch),
        B, F, L, F, F,                                              // to the hut
        L, F, C(Verb.Open, Noun.Drawer), C(Verb.Take, Noun.Cigarettes), C(Verb.Open, Noun.Cigarettes),
        C(Verb.Drop, Noun.Cigarettes), L, C(Verb.Take, Noun.Knife), B, C(Verb.Take, Noun.Gourd),
        R, F, R, F, R, F, F, C(Verb.Take, Noun.Bananas),            // the banana grove
        B, F, F, L, F, F,                                           // back to the crossing paths
        F, L, F, R, F,                                              // through the swamp to the clearing
        C(Verb.Cut, Noun.Plant), C(Verb.Take, Noun.Kit), C(Verb.Take, Noun.Tonic), C(Verb.Take, Noun.Serum),
        C(Verb.Take, Noun.Aspirin), C(Verb.Swallow, Noun.Aspirin),
        B, F, L, F, F,                                              // to the coconut palm
        C(Verb.Climb, Noun.Palm), C(Verb.Take, Noun.Coconut), C(Verb.Descend), C(Verb.Eat, Noun.Coconut),
        R, F, R, F, F,                                              // the narrow path and its cobra
        C(Verb.Throw, Noun.Knife), C(Verb.Take, Noun.Knife), F,
        L, C(Verb.Take, Noun.Boots), C(Verb.Wear, Noun.Boots),
        R, F, L, C(Verb.Drink, Noun.Water), C(Verb.Fill, Noun.Gourd),
        R, F, F, C(Verb.Light, Noun.Torch),                         // the crater
        B, F, F, L, F, R, F, L, F, F,                               // across the scorpions' rocks
        L, C(Verb.Take, Noun.Shovel), F, C(Verb.Dig), C(Verb.Drop, Noun.Shovel), C(Verb.Open, Noun.Trapdoor),
        C(Verb.Descend), B, C(Verb.Open, Noun.Grille), F,
    ];

    /// <summary>Part 2: from the entrance gallery to the helicopter.</summary>
    public static IReadOnlyList<Command> Part2 { get; } =
    [
        C(Verb.Drop, Noun.Key), C(Verb.Drop, Noun.Knife),
        L, C(Verb.Take, Noun.Rope), R, F, C(Verb.Press, Noun.Eye), F, C(Verb.Take, Noun.Helmet),
        C(Verb.Wear, Noun.Helmet), B, F, F,
        L, F, F, F, R, C(Verb.Take, Noun.Hammer), L, F, L, C(Verb.Take, Noun.Bucket),
        L, F, F, R, F, F,                                           // the stalactites and the well
        C(Verb.Tie, Noun.Bucket), C(Verb.Descend, Noun.Bucket), C(Verb.Raise, Noun.Bucket), C(Verb.Drink, Noun.Water),
        C(Verb.Eat, Noun.Bananas), C(Verb.Swallow, Noun.Tonic),
        B, F, F, L, F, L, C(Verb.Break, Noun.Grille), F, F,         // past the ghost
        R, F, L, F, C(Verb.Take, Noun.Sabre), B, F, R, F,
        R, F, C(Verb.Throw, Noun.Sabre),                            // the gorilla
        L, F, R, C(Verb.Take, Noun.Sabre), R, F, L, F,
        C(Verb.Ask, Noun.Sage), R, C(Verb.Open, Noun.Door), F,
        C(Verb.Behead, Noun.Dragon), F, C(Verb.Take, Noun.Diamond),
        L, F, F, R, C(Verb.Take, Noun.Jerrican), L, F,
        L, C(Verb.Press, Noun.Button), R, C(Verb.Fill, Noun.Fuel), C(Verb.Climb, Noun.Helicopter), C(Verb.Fly),
    ];

    public static IEnumerable<Command> All
    {
        get
        {
            foreach (var c in Part1)
                yield return c;
            foreach (var c in Part2)
                yield return c;
        }
    }
}
