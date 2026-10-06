using System.Linq;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.World;

namespace Diamond.Tests;

public class VocabularyTests
{
    [Theory]
    [InlineData("PRENDS", Verb.Take)]
    [InlineData("PREN", Verb.Take)]
    [InlineData("pren", Verb.Take)]
    [InlineData("DECA", Verb.Behead)]
    [InlineData("DECO", Verb.Fly)]
    [InlineData("DEMI-TOUR", Verb.Back)]
    [InlineData("DEMI", Verb.Back)]
    [InlineData("AVAN", Verb.Forward)]
    [InlineData("TIRE", Verb.Fire)]
    public void FrenchVerbsAreRecognisedFromThreeOrFourLetters(string token, Verb verb)
    {
        var w = Vocabulary.Lookup(Language.French, token);
        Assert.NotNull(w);
        Assert.Equal(verb, w.Value.Verb);
    }

    [Theory]
    [InlineData("MAS", Noun.Club)]
    [InlineData("COUT", Noun.Knife)]
    [InlineData("COCO", Noun.Coconut)]
    [InlineData("COCOT", Noun.Palm)]
    [InlineData("TIRO", Noun.Drawer)]
    [InlineData("BAND", Noun.Bandage)]
    [InlineData("oeil", Noun.Eye)]
    [InlineData("ŒIL", Noun.Eye)]
    [InlineData("CLÉ", Noun.Key)]
    [InlineData("hélico", Noun.Helicopter)]
    public void FrenchNounsAreRecognised(string token, Noun noun)
    {
        var w = Vocabulary.Lookup(Language.French, token);
        Assert.NotNull(w);
        Assert.Equal(noun, w.Value.Noun);
    }

    [Theory]
    [InlineData("DEC")]   // DECAPITE or DECOLLE
    [InlineData("COU")]   // COUPE or COUTEAU
    [InlineData("REM")]   // REMPLIS or REMONTE
    public void AmbiguousAbbreviationsAreNotGuessed(string token) =>
        Assert.Null(Vocabulary.Lookup(Language.French, token));

    [Theory]
    [InlineData("XYZZY")]
    [InlineData("PR")]
    public void UnknownOrTooShortWordsAreRejected(string token) => Assert.Null(Vocabulary.Lookup(Language.French, token));

    [Theory]
    [InlineData("PIC", Verb.Take)]
    [InlineData("FORW", Verb.Forward)]
    [InlineData("BEH", Verb.Behead)]
    [InlineData("INV", Verb.Inventory)]
    public void EnglishVerbsAreRecognised(string token, Verb verb) =>
        Assert.Equal(verb, Vocabulary.Lookup(Language.English, token)?.Verb);

    [Fact]
    public void CompletionGivesTheFullWord()
    {
        Assert.Equal("MASSUE", Vocabulary.Complete(Language.French, "MAS"));
        Assert.Equal("DECAPITE", Vocabulary.Complete(Language.French, "DECA"));
        Assert.Null(Vocabulary.Complete(Language.French, "DEC"));
        Assert.True(Vocabulary.IsPrefix(Language.French, "DEC"));
        Assert.False(Vocabulary.IsPrefix(Language.French, "QQQ"));
    }

    [Fact]
    public void ShortFormHasAboutNinetyWordsLikeTheOriginal()
    {
        foreach (var lang in new[] { Language.French, Language.English })
        {
            int meanings = Vocabulary.Primary(lang).Count;
            Assert.InRange(meanings, 80, 100);
        }
    }

    [Fact]
    public void EveryVerbAndNounHasAWordInBothLanguages()
    {
        foreach (var lang in new[] { Language.French, Language.English })
        {
            var words = Vocabulary.All(lang);
            foreach (var verb in System.Enum.GetValues<Verb>().Where(v => v != Verb.None))
                Assert.Contains(words, w => w.Verb == verb);
            foreach (var noun in System.Enum.GetValues<Noun>().Where(n => n is not (Noun.None or Noun.RustyGrille)))
                Assert.Contains(words, w => w.Noun == noun);
        }
    }

    [Fact]
    public void ShortFormWordsAreUniqueWithinALanguage()
    {
        foreach (var lang in new[] { Language.French, Language.English })
        {
            var all = Vocabulary.All(lang, ParserMode.Long).GroupBy(w => w.Text).Where(g => g.Select(w => (w.Verb, w.Noun)).Distinct().Count() > 1);
            Assert.Empty(all);
        }
    }

    [Theory]
    [InlineData("AVANCER", Verb.Forward)]
    [InlineData("PRENEZ", Verb.Take)]
    [InlineData("PRENDRE", Verb.Take)]
    [InlineData("DESCENDRE", Verb.Descend)]
    [InlineData("BOTTE", Verb.None)]
    public void LongFormKnowsOtherVerbForms(string token, Verb verb)
    {
        var w = Vocabulary.Lookup(Language.French, token, ParserMode.Long);
        Assert.NotNull(w);
        Assert.Equal(verb, w.Value.Verb);
    }

    [Theory]
    [InlineData("WALKING", Verb.Forward)]
    [InlineData("FORWARDS", Verb.Forward)]
    [InlineData("GRABS", Verb.Take)]
    public void LongFormAcceptsEndings(string token, Verb verb) =>
        Assert.Equal(verb, Vocabulary.Lookup(Language.English, token, ParserMode.Long)?.Verb);

    [Fact]
    public void ShortFormDoesNotKnowLongFormWords()
    {
        Assert.Null(Vocabulary.Lookup(Language.French, "PRENEZ"));
        Assert.Null(Vocabulary.Lookup(Language.English, "GRAB"));
        Assert.NotNull(Vocabulary.Lookup(Language.English, "GRAB", ParserMode.Long));
    }
}

public class ParserTests
{
    private static Command One(Language lang, string text, ParserMode mode = ParserMode.Short)
    {
        var r = Parser.ParseLine(lang, text, mode);
        Assert.Single(r);
        Assert.True(r[0].Ok, $"'{text}' failed: {r[0].Error} {r[0].BadWord}");
        return r[0].Command;
    }

    [Theory]
    [InlineData("PRENDS LA MASSUE", Verb.Take, Noun.Club)]
    [InlineData("pren mass", Verb.Take, Noun.Club)]
    [InlineData("OUVRE LE PAQUET DE CIGARETTES", Verb.Open, Noun.Cigarettes)]
    [InlineData("MANGE LA NOIX DE COCO", Verb.Eat, Noun.Coconut)]
    [InlineData("AVALE LE CACHET D'ASPIRINE", Verb.Swallow, Noun.Aspirin)]
    [InlineData("FAIS PLEIN", Verb.Fill, Noun.Fuel)]
    [InlineData("DEMI TOUR", Verb.Back, Noun.None)]
    [InlineData("APPUIE OEIL", Verb.Press, Noun.Eye)]
    [InlineData("monte hélicoptère", Verb.Climb, Noun.Helicopter)]
    public void FrenchCommands(string text, Verb verb, Noun noun) =>
        Assert.Equal(new Command(verb, noun), One(Language.French, text));

    [Theory]
    [InlineData("TAKE THE KEY", Verb.Take, Noun.Key)]
    [InlineData("pick up the club", Verb.Take, Noun.Club)]
    [InlineData("TAKE OFF", Verb.Fly, Noun.None)]
    [InlineData("PUT ON BOOTS", Verb.Wear, Noun.Boots)]
    [InlineData("TURN LEFT", Verb.Left, Noun.None)]
    [InlineData("TURN AROUND", Verb.Back, Noun.None)]
    [InlineData("PRESS EYE", Verb.Press, Noun.Eye)]
    public void EnglishCommands(string text, Verb verb, Noun noun) =>
        Assert.Equal(new Command(verb, noun), One(Language.English, text));

    [Fact]
    public void CommandsChainWithSlash()
    {
        var r = Parser.ParseLine(Language.French, "AVANCE/GAUCHE/PRENDS GOURDE");
        Assert.Equal([Verb.Forward, Verb.Left, Verb.Take], r.Select(x => x.Command.Verb));
        Assert.All(r, x => Assert.True(x.Ok));
    }

    [Fact]
    public void NoMoreThanFortyChainedCommands()
    {
        var r = Parser.ParseLine(Language.French, string.Join("/", Enumerable.Repeat("GAUCHE", 45)));
        Assert.Equal(41, r.Count);
        Assert.Equal(ParseError.TooMany, r[^1].Error);
    }

    [Fact]
    public void UnknownWordsAreReported()
    {
        var r = Parser.Parse(Language.French, "PRENDS LE PARAPLUIE");
        Assert.Equal(ParseError.UnknownWord, r.Error);
        Assert.Equal("PARAPLUIE", r.BadWord);
        Assert.Equal(ParseError.NoVerb, Parser.Parse(Language.French, "MASSUE").Error);
        Assert.Equal(ParseError.Empty, Parser.ParseLine(Language.French, "  ")[0].Error);
    }

    [Fact]
    public void ShortFormRejectsSentences()
    {
        Assert.False(Parser.Parse(Language.French, "JE VEUX PRENDRE LA MASSUE").Ok);
        Assert.False(Parser.Parse(Language.English, "I WANT TO GRAB THE CLUB").Ok);
    }

    [Theory]
    [InlineData("je veux prendre la massue", Verb.Take, Noun.Club)]
    [InlineData("Prenez la trousse de survie", Verb.Take, Noun.Kit)]
    [InlineData("tourne à gauche", Verb.Left, Noun.None)]
    [InlineData("va tout droit", Verb.Forward, Noun.None)]
    [InlineData("fais demi-tour", Verb.Back, Noun.None)]
    [InlineData("monter dans l'hélicoptère", Verb.Climb, Noun.Helicopter)]
    public void LongFormFrench(string text, Verb verb, Noun noun) =>
        Assert.Equal(new Command(verb, noun), One(Language.French, text, ParserMode.Long) with { Target = Noun.None });

    [Theory]
    [InlineData("I want to grab the club please", Verb.Take, Noun.Club)]
    [InlineData("climb the coconut palm", Verb.Climb, Noun.Palm)]
    [InlineData("pick up the survival kit", Verb.Take, Noun.Kit)]
    [InlineData("go forwards", Verb.Forward, Noun.None)]
    [InlineData("walk left", Verb.Left, Noun.None)]
    public void LongFormEnglish(string text, Verb verb, Noun noun) =>
        Assert.Equal(new Command(verb, noun), One(Language.English, text, ParserMode.Long) with { Target = Noun.None });

    [Fact]
    public void LongFormFindsTheTarget()
    {
        Assert.Equal(new Command(Verb.Throw, Noun.Club, Noun.Spider),
            One(Language.English, "throw the club at the spider", ParserMode.Long));
        Assert.Equal(new Command(Verb.Throw, Noun.Club, Noun.Spider),
            One(Language.French, "lance la massue sur la mygale", ParserMode.Long));
        Assert.Equal(new Command(Verb.Cut, Noun.Plant, Noun.Knife),
            One(Language.English, "cut the plant with the knife", ParserMode.Long));
    }

    [Fact]
    public void LongFormChainsWithConjunctionsAndReusesTheVerb()
    {
        var r = Parser.ParseLine(Language.English, "take the rope and the bucket, then go forward", ParserMode.Long);
        Assert.Equal([new Command(Verb.Take, Noun.Rope), new Command(Verb.Take, Noun.Bucket), new Command(Verb.Forward)],
            r.Select(x => x.Command));
        r = Parser.ParseLine(Language.French, "prends la corde et le seau puis avance", ParserMode.Long);
        Assert.Equal([new Command(Verb.Take, Noun.Rope), new Command(Verb.Take, Noun.Bucket), new Command(Verb.Forward)],
            r.Select(x => x.Command));
    }

    [Fact]
    public void FormatAndParseRoundTripEveryCommandOfTheWalkthrough()
    {
        foreach (var lang in new[] { Language.French, Language.English })
            foreach (var c in Walkthrough.All)
                Assert.Equal(c, One(lang, Parser.Format(lang, c)));
    }
}
