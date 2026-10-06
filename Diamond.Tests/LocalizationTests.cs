using System.Linq;
using System.Reflection;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.Oric;
using Diamond.Core.World;

namespace Diamond.Tests;

public class LocalizationTests
{
    private static void Drawable(string text)
    {
        foreach (char ch in text)
            Assert.True(OricFont.CanDraw(ch) || ch == '\n', $"'{ch}' (U+{(int)ch:X4}) in \"{text}\"");
    }

    [Theory]
    [InlineData(Language.French)]
    [InlineData(Language.English)]
    public void EveryScreenStringCanBeDrawn(Language language)
    {
        var saved = Strings.Current;
        Strings.Current = language;
        try
        {
            foreach (var p in typeof(Strings).GetProperties(BindingFlags.Public | BindingFlags.Static)
                         .Where(p => p.PropertyType == typeof(string)))
                Drawable((string)p.GetValue(null));
            foreach (bool mobile in new[] { false, true })
            {
                Drawable(Strings.PressToStart(mobile));
                Drawable(Strings.TypeHere(mobile));
                Drawable(Strings.RetryPart2(mobile));
                foreach (var mode in new[] { ParserMode.Short, ParserMode.Long })
                    foreach (var page in Strings.InstructionPages(mobile, mode))
                        Drawable(page);
            }
            foreach (var mode in new[] { ParserMode.Short, ParserMode.Long })
            {
                Drawable(Strings.ParserItem(mode));
                Drawable(Strings.ParserHint(mode));
            }
            for (int score = 0; score <= 100; score += 10)
                Drawable(Strings.Rank(score));
            foreach (var h in Strings.InstructionHeaders)
                Drawable(h);
        }
        finally
        {
            Strings.Current = saved;
        }
    }

    [Fact]
    public void LanguagesDiffer()
    {
        Strings.Current = Language.French;
        string fr = Strings.Title;
        Strings.Current = Language.English;
        string en = Strings.Title;
        Assert.NotEqual(fr, en);
        Assert.Equal("LE DIAMANT DE L'ÎLE MAUDITE", fr);
    }

    [Fact]
    public void PlacesAndThingsCanBeDrawn()
    {
        foreach (var loc in Island.Locations.Values)
        {
            Drawable(loc.Name.Fr);
            Drawable(loc.Name.En);
            Drawable(loc.Description.Fr);
            Drawable(loc.Description.En);
            Assert.True(loc.Name.Fr.Length <= 24 && loc.Name.En.Length <= 24, loc.Id + " name too long for the status line");
        }
        foreach (var t in Island.Things.Values)
        {
            Drawable(t.Name.Fr);
            Drawable(t.Name.En);
        }
    }

    [Fact]
    public void VocabularyWordsFitTheWordListButtons()
    {
        foreach (var lang in new[] { Language.French, Language.English })
            foreach (var w in Vocabulary.Primary(lang))
                Assert.True(w.Text.Length <= 12, w.Text);
    }

    [Theory]
    [InlineData("", 1)]
    [InlineData("one two three", 1)]
    [InlineData("a\nb", 2)]
    public void WrapSplitsLines(string text, int lines) => Assert.Equal(lines, Strings.Wrap(text).Count);

    [Fact]
    public void WrapNeverExceedsTheWidth()
    {
        Strings.Current = Language.French;
        foreach (var line in Strings.Wrap(Strings.Story + " " + new string('X', 95), 40))
            Assert.True(line.Length <= 40);
    }
}
