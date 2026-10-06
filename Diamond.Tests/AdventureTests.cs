using System.Collections.Generic;
using System.Linq;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.World;

namespace Diamond.Tests;

public class AdventureTests
{
    private static Command C(Verb v, Noun n = Noun.None) => new(v, n);

    /// <summary>Plays French short-form commands, e.g. "DROITE/PRENDS MASSUE".</summary>
    private static List<Loc> Play(Adventure a, string line)
    {
        var said = new List<Loc>();
        foreach (var r in Parser.ParseLine(Language.French, line))
        {
            Assert.True(r.Ok, $"{line}: {r.Error} {r.BadWord}");
            said.AddRange(a.Execute(r.Command));
        }
        return said;
    }

    /// <summary>Plays the walkthrough until a condition holds.</summary>
    private static Adventure PlayUntil(System.Func<Adventure, bool> until)
    {
        var a = new Adventure();
        foreach (var c in Walkthrough.All)
        {
            if (until(a))
                return a;
            a.Execute(c);
        }
        Assert.True(until(a), "condition never reached");
        return a;
    }

    [Fact]
    public void TheGameStartsOnTheShipwreckBeach()
    {
        var a = new Adventure();
        Assert.Equal("wreck", a.LocationId);
        Assert.Equal(Dir.North, a.Facing);
        Assert.Equal(Part.Island, a.Part);
        Assert.Equal(Health.MaxFitness, a.Health.Fitness);
        Assert.NotEmpty(a.Begin());
    }

    [Fact]
    public void TurningChangesTheViewAndObjectsAreOnlySeenFacingThem()
    {
        var a = new Adventure();
        Assert.False(a.InView(Noun.Club));
        Play(a, "DROITE");
        Assert.Equal(Dir.East, a.Facing);
        Assert.True(a.InView(Noun.Club));
        Play(a, "DEMI-TOUR");
        Assert.Equal(Dir.West, a.Facing);
        Assert.False(a.InView(Noun.Club));
        Play(a, "PRENDS MASSUE");
        Assert.False(a.Holds(Noun.Club));
    }

    [Fact]
    public void WalkingFollowsTheExits()
    {
        var a = new Adventure();
        Play(a, "AVANCE");
        Assert.Equal("jungle_edge", a.LocationId);
        Play(a, "DEMI-TOUR/AVANCE/AVANCE");
        Assert.Equal("wreck", a.LocationId);   // the sea stops you
        Assert.Equal(4, a.Moves);
    }

    [Fact]
    public void LookingAndTheInventoryTakeNoTime()
    {
        var a = new Adventure();
        Play(a, "REGARDE/INVENTAIRE/BILAN/AIDE");
        Assert.Equal(0, a.Moves);
    }

    [Fact]
    public void TheSpiderBitesWhoeverTakesTheTorch()
    {
        var a = new Adventure();
        Play(a, "DEMI-TOUR/DROITE/AVANCE/DROITE/AVANCE/AVANCE");
        Assert.Equal("tower_in", a.LocationId);
        Play(a, "PRENDS TORCHE");
        Assert.False(a.Holds(Noun.Torch));
        Assert.True(a.Health.SpiderBitten);
    }

    [Fact]
    public void ThrowingTheClubCrushesTheSpider()
    {
        var a = PlayUntil(x => x.LocationId == "tower_in" && x.Facing == Dir.East);
        a.Execute(C(Verb.Throw, Noun.Club));
        Assert.False(a.Alive(Noun.Spider));
        Assert.Contains("spider", a.Milestones);
        a.Execute(C(Verb.Left));
        a.Execute(C(Verb.Take, Noun.Torch));
        Assert.True(a.Holds(Noun.Torch));
        Assert.False(a.Health.SpiderBitten);
    }

    [Fact]
    public void TheDrawerHidesCigarettesAndTheCigarettesHideAKey()
    {
        var a = PlayUntil(x => x.LocationId == "hut_in");
        Assert.False(a.InView(Noun.Cigarettes));
        a.Execute(C(Verb.Open, Noun.Drawer));
        Assert.True(a.InView(Noun.Cigarettes));
        a.Execute(C(Verb.Take, Noun.Cigarettes));
        a.Execute(C(Verb.Open, Noun.Cigarettes));
        Assert.True(a.Holds(Noun.Key));
    }

    [Fact]
    public void WalkingPastTheCobraIsFatal()
    {
        var a = PlayUntil(x => x.LocationId == "narrow");
        Assert.True(a.Alive(Noun.Cobra));
        a.Execute(C(Verb.Forward));
        Assert.Equal(Ending.Dead, a.Ending);
    }

    [Fact]
    public void TheCarnivorousPlantGuardsTheKit()
    {
        var a = PlayUntil(x => x.LocationId == "clearing" && x.Facing == Dir.East);
        int injury = a.Health.Injury;
        a.Execute(C(Verb.Take, Noun.Kit));
        Assert.True(a.Health.Injury > injury);
        Assert.False(a.InView(Noun.Serum));
        a.Execute(C(Verb.Cut, Noun.Plant));
        a.Execute(C(Verb.Take, Noun.Kit));
        Assert.True(a.InView(Noun.Serum) && a.InView(Noun.Tonic) && a.InView(Noun.Aspirin) && a.InView(Noun.Bandage));
    }

    [Fact]
    public void TheSwampGivesAFeverThatAspirinCures()
    {
        var a = PlayUntil(x => x.LocationId == "marsh");
        Assert.True(a.Health.Feverish);
        a = PlayUntil(x => x.Holds(Noun.Aspirin));
        a.Execute(C(Verb.Swallow, Noun.Aspirin));
        Assert.False(a.Health.Feverish);
        Assert.Equal(0, a.Health.Fever);
    }

    [Fact]
    public void CoconutsArePickedFromTheTopOfThePalm()
    {
        var a = PlayUntil(x => x.LocationId == "palm" && x.Facing == Dir.South);
        a.Execute(C(Verb.Take, Noun.Coconut));
        Assert.False(a.Holds(Noun.Coconut));
        a.Execute(C(Verb.Climb, Noun.Palm));
        Assert.True(a.UpPalm);
        Assert.Equal("palm_top", a.CurrentView.Background);
        a.Execute(C(Verb.Forward));
        Assert.Equal("palm", a.LocationId);
        a.Execute(C(Verb.Take, Noun.Coconut));
        a.Execute(C(Verb.Descend));
        Assert.False(a.UpPalm);
        a.Execute(C(Verb.Eat, Noun.Coconut));
        Assert.Equal(0, a.Health.Hunger);
    }

    [Fact]
    public void ScorpionsStingWithoutBoots()
    {
        var a = PlayUntil(x => x.LocationId == "skeleton");
        a.Execute(C(Verb.Right));
        a.Execute(C(Verb.Forward));
        Assert.Equal("scree", a.LocationId);
        Assert.True(a.Health.ScorpionStung);
    }

    [Fact]
    public void BootsKeepTheScorpionsOff()
    {
        var a = PlayUntil(x => x.LocationId == "scree");
        Assert.True(a.Wears(Noun.Boots));
        Assert.False(a.Health.ScorpionStung);
    }

    [Fact]
    public void TheTorchIsLitAtTheCraterOnly()
    {
        var a = PlayUntil(x => x.LocationId == "volcano_foot");
        a.Execute(C(Verb.Light, Noun.Torch));
        Assert.False(a.TorchLit);
        a = PlayUntil(x => x.LocationId == "crater");
        a.Execute(C(Verb.Light, Noun.Torch));
        Assert.True(a.TorchLit);
    }

    [Fact]
    public void DiggingRevealsALockedTrapdoorAndTheWayDownNeedsLight()
    {
        var a = PlayUntil(x => x.LocationId == "hangar_corner");
        Assert.False(a.InView(Noun.Trapdoor));
        a.Execute(C(Verb.Dig));
        Assert.True(a.InView(Noun.Trapdoor));
        Assert.False(a.InView(Noun.Earth));
        a.Execute(C(Verb.Open, Noun.Trapdoor));
        Assert.True(a.TrapOpen);   // the key is carried

        var b = Adventure.Load(a.Save());
        b.Execute(C(Verb.Drop, Noun.Torch));
        b.Execute(C(Verb.Descend));
        Assert.Equal("hangar_corner", b.LocationId);
        a.Execute(C(Verb.Descend));
        Assert.Equal("cellar", a.LocationId);
    }

    [Fact]
    public void TheTrapdoorStaysShutWithoutTheKey()
    {
        var a = PlayUntil(x => x.LocationId == "hangar_corner");
        a.Execute(C(Verb.Dig));
        a.Execute(C(Verb.Drop, Noun.Key));
        a.Execute(C(Verb.Open, Noun.Trapdoor));
        Assert.False(a.TrapOpen);
    }

    [Fact]
    public void PassingTheGrilleStartsPartTwoWithNoWayBack()
    {
        var a = PlayUntil(x => x.Part == Part.Underground);
        Assert.True(a.EnteredPart2);
        Assert.Equal("entry", a.LocationId);
        Assert.Contains("part2", a.Milestones);
        a.Execute(C(Verb.Back));
        a.Execute(C(Verb.Forward));
        Assert.Equal("entry", a.LocationId);
    }

    [Fact]
    public void UndergroundIsDarkWithoutTheTorch()
    {
        var a = PlayUntil(x => x.Part == Part.Underground);
        Assert.True(a.CanSee);
        a.Execute(C(Verb.Drop, Noun.Torch));
        Assert.True(a.CanSee);   // it lights the room from the floor
        a.Execute(C(Verb.Right));
        a.Execute(C(Verb.Forward));
        Assert.False(a.CanSee);
        Assert.Empty(a.Visible());
    }

    [Fact]
    public void TheBuddhasEyeOpensTheSecretPassage()
    {
        var a = PlayUntil(x => x.LocationId == "buddha" && x.Facing == Dir.North);
        a.Execute(C(Verb.Forward));
        Assert.Equal("buddha", a.LocationId);
        a.Execute(C(Verb.Press, Noun.Eye));
        Assert.True(a.SecretOpen);
        Assert.Equal("temple_opening", a.CurrentView.Background);
        a.Execute(C(Verb.Forward));
        Assert.Equal("secret", a.LocationId);
    }

    [Fact]
    public void TheIdolsEyeIsATrap()
    {
        var a = PlayUntil(x => x.LocationId == "well");
        a.Execute(C(Verb.Right));
        Assert.True(a.InView(Noun.Idol));
        a.Execute(C(Verb.Press, Noun.Eye));
        Assert.Equal(Ending.Dead, a.Ending);
    }

    [Fact]
    public void StalactitesHurtWithoutTheHelmet()
    {
        var a = PlayUntil(x => x.LocationId == "junction" && x.Facing == Dir.North);
        a.Execute(C(Verb.Remove, Noun.Helmet));
        int before = a.Health.Injury;
        a.Execute(C(Verb.Forward));
        Assert.True(a.Health.Injury > before);
    }

    [Fact]
    public void WaterIsDrawnFromTheWellWithTheBucketAndRope()
    {
        var a = PlayUntil(x => x.LocationId == "well" && x.Facing == Dir.North);
        a.Execute(C(Verb.Tie, Noun.Bucket));
        Assert.True(a.BucketTied);
        Assert.False(a.Holds(Noun.Rope));
        a.Execute(C(Verb.Descend, Noun.Bucket));
        a.Execute(C(Verb.Raise, Noun.Bucket));
        Assert.True(a.BucketFull);
        a.Execute(C(Verb.Drink, Noun.Water));
        Assert.Equal(0, a.Health.Thirst);
        Assert.False(a.BucketFull);
        a.Execute(C(Verb.Take, Noun.Bucket));
        Assert.True(a.Holds(Noun.Bucket) && a.Holds(Noun.Rope));
    }

    [Fact]
    public void TheGhostStealsTheOldestThingButNeverTheTorch()
    {
        var a = PlayUntil(x => x.LocationId == "store" && x.RustyBroken);
        var oldest = a.Carried.First(t => !t.Worn && t.Noun != Noun.Torch).Noun;
        a.Execute(C(Verb.Forward));
        Assert.Equal("haunted", a.LocationId);
        Assert.False(a.Holds(oldest));
        Assert.True(a.Holds(Noun.Torch));
        Assert.Equal("lit", a.Thing(oldest).Location);
        Assert.True(a.Thing(Noun.Ghost).Gone);
    }

    [Fact]
    public void TheGorillaBlocksTheWayUntilItIsGivenTheSabre()
    {
        var a = PlayUntil(x => x.LocationId == "gorilla" && x.Facing == Dir.North);
        int injury = a.Health.Injury;
        a.Execute(C(Verb.Forward));
        Assert.Equal("gorilla", a.LocationId);
        Assert.True(a.Health.Injury > injury);
        a.Execute(C(Verb.Throw, Noun.Sabre));
        Assert.False(a.Alive(Noun.Gorilla));
        Assert.Equal("den", a.Thing(Noun.Sabre).Location);
    }

    [Fact]
    public void TheDoorOpensOnlyForThoseWhoQuestionTheSage()
    {
        var a = PlayUntil(x => x.LocationId == "sage");
        a.Execute(C(Verb.Right));
        a.Execute(C(Verb.Open, Noun.Door));
        Assert.False(a.DoorOpen);
        a.Execute(C(Verb.Left));
        a.Execute(C(Verb.Ask, Noun.Sage));
        a.Execute(C(Verb.Right));
        a.Execute(C(Verb.Open, Noun.Door));
        Assert.True(a.DoorOpen);
    }

    [Fact]
    public void TheDragonBurnsWhoeverDawdles()
    {
        var a = PlayUntil(x => x.LocationId == "dragon");
        a.Execute(C(Verb.Inventory));
        a.Execute(C(Verb.Left));
        a.Execute(C(Verb.Right));
        Assert.False(a.Ended);
        a.Execute(C(Verb.Rest));
        Assert.Equal(Ending.Dead, a.Ending);
    }

    [Fact]
    public void TheHelicopterNeedsFuelAndOpenDoors()
    {
        var a = PlayUntil(x => x.LocationId == "hangar_in");
        var b = Adventure.Load(a.Save());
        b.Execute(C(Verb.Climb, Noun.Helicopter));
        b.Execute(C(Verb.Fly));
        Assert.False(b.Ended);   // the tank is empty
        b.Execute(C(Verb.Fill, Noun.Fuel));
        b.Execute(C(Verb.Climb, Noun.Helicopter));
        b.Execute(C(Verb.Fly));
        Assert.Equal(Ending.Dead, b.Ending);   // into the closed doors
    }

    [Fact]
    public void EscapingWithoutTheDiamondIsNotFullVictory()
    {
        var a = PlayUntil(x => x.LocationId == "hangar_in" && x.Fuelled);
        a.Execute(C(Verb.Drop, Noun.Diamond));
        a.Execute(C(Verb.Climb, Noun.Helicopter));
        a.Execute(C(Verb.Fly));
        Assert.Equal(Ending.Escaped, a.Ending);
        Assert.True(a.Won);
    }

    [Fact]
    public void HandsHoldEightThings()
    {
        var a = new Adventure();
        foreach (var t in a.AllThings.Where(t => t.Def.Portable && t.Noun != Noun.Kit).Take(10).ToList())
        {
            t.Location = a.LocationId;
            t.Facing = a.Facing;
            t.Hidden = false;
            a.Execute(C(Verb.Take, t.Noun));
        }
        Assert.Equal(Adventure.HandsCapacity, a.Carried.Count(t => !t.Worn));
    }

    [Fact]
    public void TheGourdHoldsThreeSipsAndRefillsAtTheSpring()
    {
        var a = PlayUntil(x => x.LocationId == "volcano_foot" && x.Facing == Dir.West);
        for (int i = 0; i < 4; i++)
            a.Execute(C(Verb.Drink, Noun.Gourd));
        Assert.Equal(0, a.Gourd);
        a.Execute(C(Verb.Fill, Noun.Gourd));
        Assert.Equal(Adventure.GourdSips, a.Gourd);
    }

    [Fact]
    public void TheSerumCuresBothVenoms()
    {
        var a = PlayUntil(x => x.Holds(Noun.Serum));
        a.Health.SpiderBitten = a.Health.ScorpionStung = true;
        a.Health.SpiderVenom = 10;
        a.Health.ScorpionVenom = 10;
        a.Execute(C(Verb.Inject, Noun.Serum));
        Assert.False(a.Health.SpiderBitten || a.Health.ScorpionStung);
        Assert.Equal(Health.Base + a.Health.Hunger + a.Health.Thirst + a.Health.Fatigue + a.Health.Fever + a.Health.Injury,
            a.Health.Troubles);
    }

    [Fact]
    public void DoingNothingForTooLongKills()
    {
        var a = new Adventure();
        for (int i = 0; i < 2000 && !a.Ended; i++)
            a.Wait();
        Assert.Equal(Ending.Dead, a.Ending);
        Assert.Equal(0, a.Moves);   // waiting is not a move
    }

    [Fact]
    public void SaveAndLoadRestoreTheWholeGame()
    {
        var a = PlayUntil(x => x.LocationId == "well" && x.BucketFull);
        var b = Adventure.Load(a.Save());
        Assert.NotNull(b);
        Assert.Equal(a.Save(), b.Save());
        Assert.Equal(a.LocationId, b.LocationId);
        Assert.Equal(a.Score, b.Score);
        Assert.Equal(a.Carried.Select(t => t.Noun), b.Carried.Select(t => t.Noun));
        Assert.Equal(a.Seen.OrderBy(n => n), b.Seen.OrderBy(n => n));
    }

    [Theory]
    [InlineData("")]
    [InlineData("garbage")]
    [InlineData("v=1\nloc=nowhere")]
    public void BadSavesAreRejected(string text) => Assert.Null(Adventure.Load(text));
}
