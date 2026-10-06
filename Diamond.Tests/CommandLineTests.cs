using Diamond.Core.Engine;
using Diamond.Core.Localization;

namespace Diamond.Tests;

public class CommandLineTests
{
    private static CommandLine Line(ParserMode mode = ParserMode.Short, Language lang = Language.French) =>
        new() { Mode = mode, Language = lang };

    private static Keystroke TypeAll(CommandLine line, string text)
    {
        var last = Keystroke.Ignored;
        foreach (char ch in text)
            last = line.Type(ch);
        return last;
    }

    [Fact]
    public void FinishedAbbreviationsAreCompleted()
    {
        var l = Line();
        TypeAll(l, "pren mas");
        Assert.Equal("PRENDS MAS", l.Text);
        Assert.Equal("SUE", l.Ghost);
        Assert.Equal(Keystroke.Submit, l.Type('\r'));
        Assert.Equal("PRENDS MASSUE", l.Submitted);
        Assert.Equal(0, l.Length);
    }

    [Fact]
    public void UnknownWordsAreErasedWithABeep()
    {
        var l = Line();
        TypeAll(l, "PRENDS ");
        Assert.Equal(Keystroke.Beep, TypeAll(l, "XYZ "));
        Assert.Equal("PRENDS ", l.Text);
    }

    [Fact]
    public void AmbiguousWordsBeepButStayToBeFinished()
    {
        var l = Line();
        Assert.Equal(Keystroke.Beep, TypeAll(l, "DEC "));
        Assert.Equal("DEC", l.Text);
        TypeAll(l, "A ");
        Assert.Equal("DECAPITE ", l.Text);
    }

    [Fact]
    public void ArticlesAndChainingAreKept()
    {
        var l = Line();
        TypeAll(l, "PREN LA GOUR/AVA");
        Assert.Equal("PRENDS LA GOURDE/AVA", l.Text);
        Assert.Equal(Keystroke.Beep, l.Type('\r'));   // AVA: AVANCE or AVALE
        TypeAll(l, "N\r");
        Assert.Equal("PRENDS LA GOURDE/AVANCE", l.Submitted);
    }

    [Fact]
    public void ApostrophesSplitWords()
    {
        var l = Line();
        TypeAll(l, "AVAL CACH D'ASPI\r");
        Assert.Equal("AVALE CACHET D'ASPIRINE", l.Submitted);
    }

    [Fact]
    public void TabCompletes()
    {
        var l = Line(lang: Language.English);
        TypeAll(l, "THRO\t");
        Assert.Equal("THROW ", l.Text);
    }

    [Fact]
    public void LongFormLeavesSentencesAlone()
    {
        var l = Line(ParserMode.Long, Language.English);
        TypeAll(l, "i want to pick up the coconut\r");
        Assert.Equal("I WANT TO PICK UP THE COCONUT", l.Submitted);
    }

    [Fact]
    public void BackspaceErases()
    {
        var l = Line();
        TypeAll(l, "AB");
        Assert.Equal(Keystroke.Erased, l.Type('\b'));
        Assert.Equal("A", l.Text);
        l.Type('\b');
        Assert.Equal(Keystroke.Ignored, l.Type('\b'));
    }
}
