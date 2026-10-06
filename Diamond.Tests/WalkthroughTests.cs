using System.Collections.Generic;
using System.Linq;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.Oric;
using Diamond.Core.World;

namespace Diamond.Tests;

public class WalkthroughTests
{
    [Theory]
    [InlineData(Language.French, ParserMode.Short)]
    [InlineData(Language.English, ParserMode.Short)]
    [InlineData(Language.French, ParserMode.Long)]
    [InlineData(Language.English, ParserMode.Long)]
    public void TheIslandCanBeCompletedWithFullMarks(Language language, ParserMode mode)
    {
        var a = new Adventure();
        foreach (var c in Walkthrough.All)
        {
            Assert.False(a.Ended, $"ended early at {a.LocationId}: {a.EndMessage.En}");
            var parsed = Parser.ParseLine(language, Parser.Format(language, c), mode).Single();
            Assert.True(parsed.Ok);
            a.Execute(parsed.Command);
        }
        Assert.Equal(Ending.EscapedWithDiamond, a.Ending);
        Assert.Equal(100, a.Score);
        Assert.True(a.Health.Fitness > 10, "the walkthrough should not be a near miss");
    }

    [Fact]
    public void PartTwoCanBeReplayedFromTheCheckpoint()
    {
        var a = new Adventure();
        foreach (var c in Walkthrough.Part1)
            a.Execute(c);
        Assert.True(a.EnteredPart2);
        var checkpoint = a.Save();
        for (int round = 0; round < 2; round++)
        {
            var b = Adventure.Load(checkpoint);
            Assert.Equal(Island.Part2Start, b.LocationId);
            foreach (var c in Walkthrough.Part2)
                b.Execute(c);
            Assert.True(b.Won);
        }
    }

    [Fact]
    public void EveryMessageOfTheWalkthroughCanBeDrawnAndFits()
    {
        var a = new Adventure();
        var said = new List<Loc>(a.Begin());
        foreach (var c in Walkthrough.All)
            said.AddRange(a.Execute(c));
        said.AddRange(a.Health.Report());
        foreach (var line in said)
            foreach (var text in new[] { line.Fr, line.En })
            {
                Assert.False(string.IsNullOrWhiteSpace(text));
                foreach (char ch in text)
                    Assert.True(OricFont.CanDraw(ch), $"'{ch}' in \"{text}\"");
            }
    }
}
