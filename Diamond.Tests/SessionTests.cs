using System.IO;
using Diamond.Core;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.Session;

namespace Diamond.Tests;

public class SessionTests
{
    [Fact]
    public void HigherScoresAndThenFewerMovesRankFirst()
    {
        var t = new HighScoreTable(Path.GetTempPath());
        Assert.Equal(1, t.Add(100, 200, "ANNE") is 0 ? 1 : 0);
        int rank = t.Add(100, 150, "BOB");
        Assert.Equal(0, rank);
        Assert.Equal("BOB", t.Entries[0].Name);
        Assert.Equal("ANNE", t.Entries[1].Name);
        Assert.Equal(HighScoreTable.Capacity, t.Entries.Count);
    }

    [Fact]
    public void LowScoresDoNotQualify()
    {
        var t = new HighScoreTable(Path.GetTempPath());
        Assert.False(t.Qualifies(0, 10));
        Assert.False(t.Qualifies(1, 10));
        Assert.True(t.Qualifies(100, 999));
        Assert.Equal(-1, t.Add(1, 10, "X"));
    }

    [Fact]
    public void TheTableSurvivesSerialisation()
    {
        var t = new HighScoreTable(Path.GetTempPath());
        t.Add(87, 321, "ZOE");
        var u = new HighScoreTable(Path.GetTempPath());
        u.Deserialize(t.Serialize());
        Assert.Equal(t.Entries, u.Entries);
        u.Deserialize("rubbish\n-5\t3\tX");
        Assert.Equal(t.Entries, u.Entries);
    }

    [Theory]
    [InlineData("pfj", "PFJ")]
    [InlineData("toolongname", "TOOLO")]
    [InlineData("", "?????")]
    [InlineData("é$#", "?????")]
    public void NamesAreSanitised(string name, string expected) => Assert.Equal(expected, HighScoreTable.Sanitize(name));

    [Fact]
    public void SettingsRoundTrip()
    {
        string dir = Path.Combine(Path.GetTempPath(), "diamond-tests-" + System.Guid.NewGuid());
        var s = GameSettings.Load(dir, "fr");
        Assert.Equal(Language.French, s.Language);
        Assert.Equal(ParserMode.Short, s.Parser);
        s.Parser = ParserMode.Long;
        s.Volume = 2;
        s.Language = Language.English;
        s.Save();
        var t = GameSettings.Load(dir, "fr");
        Assert.Equal(ParserMode.Long, t.Parser);
        Assert.Equal(2, t.Volume);
        Assert.Equal(Language.English, t.Language);
        Directory.Delete(dir, true);
    }

    [Fact]
    public void FirstRunFollowsTheDeviceLanguage()
    {
        Assert.Equal(Language.French, GameSettings.Load(Path.GetTempPath() + "nope-" + System.Guid.NewGuid(), "fr").Language);
        Assert.Equal(Language.English, GameSettings.Load(Path.GetTempPath() + "nope-" + System.Guid.NewGuid(), "de").Language);
    }
}
