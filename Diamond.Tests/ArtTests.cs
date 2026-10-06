using System.Collections.Generic;
using System.Linq;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.World;

namespace Diamond.Tests;

/// <summary>Every picture the game asks for is embedded in the core assembly.</summary>
public class ArtTests
{
    private static readonly HashSet<string> Resources =
        typeof(Canvas).Assembly.GetManifestResourceNames().ToHashSet();

    private static bool Has(string name) => Resources.Contains("Art." + name + ".png") || Resources.Contains("Art." + name + ".jpg");

    [Fact]
    public void EveryViewHasAPicture()
    {
        var names = Island.Locations.Values.SelectMany(l => l.Views.Values).Select(v => v.Background)
            .Concat(["palm_top", "temple_opening", "hangar_in_doors", "hangar_in_open"]).Distinct();
        foreach (var n in names)
            Assert.True(Has("bg_" + n), "bg_" + n);
    }

    [Fact]
    public void TheFullScreenPicturesExist()
    {
        foreach (var n in new[] { "title", "intro", "escape", "part2" })
            Assert.True(Has("bg_" + n), n);
    }

    [Fact]
    public void EveryThingHasASpriteInEveryState()
    {
        var sprites = new HashSet<string> { "scorpion", "bucket", "bucket_full" };
        var a = new Adventure();
        foreach (var t in a.AllThings)
            sprites.Add(a.SpriteFor(t));
        // Play through so every state change is seen.
        foreach (var c in Walkthrough.All)
        {
            a.Execute(c);
            foreach (var t in a.AllThings)
                sprites.Add(a.SpriteFor(t));
        }
        foreach (var s in sprites.Where(s => s.Length > 0))
            Assert.True(Has(s), s);
    }
}
