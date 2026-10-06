using System.Collections.Generic;
using System.Linq;
using Diamond.Core.Engine;
using Diamond.Core.World;

namespace Diamond.Tests;

public class IslandTests
{
    [Fact]
    public void EveryExitLeadsSomewhere()
    {
        foreach (var loc in Island.Locations.Values)
            foreach (var (_, to) in loc.Exits)
                Assert.True(Island.Locations.ContainsKey(to), $"{loc.Id} -> {to}");
    }

    [Fact]
    public void PathsGoBothWaysExceptThroughTheGrille()
    {
        foreach (var loc in Island.Locations.Values)
            foreach (var (dir, to) in loc.Exits)
            {
                if (loc.Id == "cellar")
                    continue;
                Assert.True(Island.Locations[to].Exits.TryGetValue(dir.Back(), out var back) && back == loc.Id,
                    $"{loc.Id} {dir} -> {to} has no way back");
            }
    }

    [Fact]
    public void EveryPlaceCanBeReached()
    {
        var reached = new HashSet<string> { Island.Start, "cellar" };
        var queue = new Queue<string>(reached);
        while (queue.Count > 0)
            foreach (var to in Island.Locations[queue.Dequeue()].Exits.Values)
                if (reached.Add(to))
                    queue.Enqueue(to);
        Assert.Equal(Island.Locations.Count, reached.Count);
    }

    [Fact]
    public void TheIslandIsLarge()
    {
        Assert.True(Island.Locations.Count >= 45);
        Assert.True(Island.Locations.Count * 4 >= 180, "views");
        Assert.Contains(Island.Locations.Values, l => l.Part == Part.Underground);
    }

    [Fact]
    public void EveryThingStartsInAKnownPlace()
    {
        foreach (var (noun, location, _, _, hidden) in Island.StartPositions())
        {
            Assert.True(Island.Things.ContainsKey(noun), noun.ToString());
            if (location != null && location != Island.PalmTop)
                Assert.True(Island.Locations.ContainsKey(location), $"{noun} in {location}");
            else
                Assert.True(hidden || location == Island.PalmTop, $"{noun} has no place");
        }
        Assert.Equal(Island.Things.Count, Island.StartPositions().Count());
    }

    [Fact]
    public void UndergroundPlacesAreDarkExceptWhereThereIsLight()
    {
        var lit = new[] { "lit", "diamond_room", "hangar_in" };
        foreach (var loc in Island.Locations.Values.Where(l => l.Part == Part.Underground))
            Assert.Equal(!lit.Contains(loc.Id), loc.Dark);
    }

    [Fact]
    public void NamesAndDescriptionsAreInBothLanguages()
    {
        foreach (var loc in Island.Locations.Values)
        {
            Assert.False(string.IsNullOrWhiteSpace(loc.Name.Fr) || string.IsNullOrWhiteSpace(loc.Name.En), loc.Id);
            Assert.False(string.IsNullOrWhiteSpace(loc.Description.Fr) || string.IsNullOrWhiteSpace(loc.Description.En), loc.Id);
            Assert.NotEqual(loc.Description.Fr, loc.Description.En);
        }
        foreach (var t in Island.Things.Values)
            Assert.False(string.IsNullOrWhiteSpace(t.Name.Fr) || string.IsNullOrWhiteSpace(t.Name.En), t.Noun.ToString());
    }
}
