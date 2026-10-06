using System;
using System.Collections.Generic;
using Diamond.Core.Localization;

namespace Diamond.Core.Engine;

/// <summary>
/// The explorer's troubles, as in the original's BASIC: hunger, thirst, fatigue, fever, injury and
/// the venoms of the tarantula and the scorpions add up to the "sum of troubles" (KA). It starts
/// at 10 and the explorer dies when it reaches 70. Each trouble grows with time until it is cured.
/// </summary>
public sealed class Health
{
    public const int Base = 10;
    public const int Fatal = 70;

    /// <summary>Fitness shown on screen: 60 when well, 0 at death.</summary>
    public const int MaxFitness = Fatal - Base;

    // Moves between one more point of each trouble.
    public const int ThirstEvery = 6;
    public const int HungerEvery = 9;
    public const int FatigueEvery = 10;
    public const int FeverEvery = 4;

    public int Hunger { get; set; }
    public int Thirst { get; set; }
    public int Fatigue { get; set; }
    public int Fever { get; set; }
    public int Injury { get; set; }
    public int SpiderVenom { get; set; }
    public int ScorpionVenom { get; set; }

    public bool Feverish { get; set; }
    public bool SpiderBitten { get; set; }
    public bool ScorpionStung { get; set; }

    // Timers (moves since the trouble last grew).
    public int ThirstClock { get; set; }
    public int HungerClock { get; set; }
    public int FatigueClock { get; set; }
    public int FeverClock { get; set; }

    /// <summary>The sum of troubles (KA in the original).</summary>
    public int Troubles => Math.Min(Fatal, Base + Hunger + Thirst + Fatigue + Fever + Injury + SpiderVenom + ScorpionVenom);

    public int Fitness => Fatal - Troubles;

    public bool Dead => Troubles >= Fatal;

    /// <summary>One move passes. Hot ground (the volcano) makes you thirsty and tired twice as fast.</summary>
    public IEnumerable<Loc> Pass(bool hot)
    {
        var warnings = new List<Loc>();
        int before = Troubles;
        ThirstClock += hot ? 2 : 1;
        HungerClock++;
        FatigueClock += hot ? 2 : 1;
        if (ThirstClock >= ThirstEvery)
        {
            ThirstClock -= ThirstEvery;
            Thirst++;
            if (Thirst == 8)
                warnings.Add(new Loc("Vous avez soif.", "You are thirsty."));
            else if (Thirst == 16)
                warnings.Add(new Loc("Vous mourez de soif !", "You are dying of thirst!"));
        }
        if (HungerClock >= HungerEvery)
        {
            HungerClock -= HungerEvery;
            Hunger++;
            if (Hunger == 8)
                warnings.Add(new Loc("Votre estomac gargouille.", "Your stomach rumbles."));
            else if (Hunger == 14)
                warnings.Add(new Loc("Vous êtes affamé !", "You are starving!"));
        }
        if (FatigueClock >= FatigueEvery)
        {
            FatigueClock -= FatigueEvery;
            Fatigue++;
            if (Fatigue == 8)
                warnings.Add(new Loc("Vous êtes fatigué.", "You are tired."));
            else if (Fatigue == 14)
                warnings.Add(new Loc("Vous tombez de fatigue !", "You are exhausted!"));
        }
        if (Feverish && ++FeverClock >= FeverEvery)
        {
            FeverClock = 0;
            Fever++;
            if (Fever == 3)
                warnings.Add(new Loc("Vous frissonnez : vous avez de la fièvre.", "You are shivering: you have a fever."));
        }
        if (SpiderBitten)
            SpiderVenom++;
        if (ScorpionStung)
            ScorpionVenom++;
        if ((SpiderBitten || ScorpionStung) && (SpiderVenom + ScorpionVenom) % 6 == 0)
            warnings.Add(new Loc("Le venin vous brûle les veines !", "The venom burns in your veins!"));

        int after = Troubles;
        if (before < 50 && after >= 50)
            warnings.Add(new Loc("Vous êtes au bord de l'évanouissement !", "You are on the point of collapse!"));
        else if (before < 40 && after >= 40)
            warnings.Add(new Loc("Vous vous sentez faiblir.", "You feel yourself growing weak."));
        return warnings;
    }

    /// <summary>The report given by BILAN / STATUS.</summary>
    public IEnumerable<Loc> Report()
    {
        yield return new Loc($"Forme : {Fitness}/{MaxFitness}", $"Fitness: {Fitness}/{MaxFitness}");
        if (Thirst >= 4)
            yield return Level(Thirst, new Loc("soif", "thirst"));
        if (Hunger >= 4)
            yield return Level(Hunger, new Loc("faim", "hunger"));
        if (Fatigue >= 4)
            yield return Level(Fatigue, new Loc("fatigue", "fatigue"));
        if (Feverish || Fever > 0)
            yield return Level(Math.Max(Fever, 4), new Loc("fièvre", "fever"));
        if (Injury > 0)
            yield return Level(Injury, new Loc("blessures", "injuries"));
        if (SpiderBitten)
            yield return new Loc("Venin de mygale dans le sang !", "Tarantula venom in your blood!");
        if (ScorpionStung)
            yield return new Loc("Venin de scorpion dans le sang !", "Scorpion venom in your blood!");
        if (Troubles <= Base + 3)
            yield return new Loc("Vous êtes en pleine forme.", "You are in fine shape.");
    }

    private static Loc Level(int value, Loc what)
    {
        var (fr, en) = value switch
        {
            < 8 => ("légère", "slight"),
            < 14 => ("forte", "serious"),
            _ => ("terrible", "terrible"),
        };
        return new Loc($"- {what.Fr} : {fr}", $"- {what.En}: {en}");
    }

    public string Serialize() =>
        string.Join(",", Hunger, Thirst, Fatigue, Fever, Injury, SpiderVenom, ScorpionVenom, Feverish ? 1 : 0,
            SpiderBitten ? 1 : 0, ScorpionStung ? 1 : 0, ThirstClock, HungerClock, FatigueClock, FeverClock);

    public static Health Deserialize(string text)
    {
        var v = Array.ConvertAll(text.Split(','), int.Parse);
        return new Health
        {
            Hunger = v[0], Thirst = v[1], Fatigue = v[2], Fever = v[3], Injury = v[4], SpiderVenom = v[5],
            ScorpionVenom = v[6], Feverish = v[7] != 0, SpiderBitten = v[8] != 0, ScorpionStung = v[9] != 0,
            ThirstClock = v[10], HungerClock = v[11], FatigueClock = v[12], FeverClock = v[13],
        };
    }
}
