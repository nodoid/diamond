using System;
using System.Collections.Generic;
using System.Linq;
using Diamond.Core.Localization;
using Diamond.Core.World;

namespace Diamond.Core.Engine;

/// <summary>A command: a verb, usually a noun, and sometimes a target ("THROW CLUB AT SPIDER").</summary>
public readonly record struct Command(Verb Verb, Noun Noun = Noun.None, Noun Target = Noun.None)
{
    public override string ToString() =>
        Noun == Noun.None ? Verb.ToString() : Target == Noun.None ? $"{Verb} {Noun}" : $"{Verb} {Noun} {Target}";
}

/// <summary>Why a line could not be understood.</summary>
public enum ParseError
{
    None,
    Empty,
    UnknownWord,
    NoVerb,
    TooMany,
}

public readonly record struct ParseResult(Command Command, ParseError Error, string BadWord = null)
{
    public bool Ok => Error == ParseError.None;
}

/// <summary>
/// Turns typed lines into commands. As in the original, several commands may be chained with
/// "/" (up to forty) and words may be abbreviated to their first three or four letters. In the
/// long form, sentences may also be chained with "ET", "PUIS", "AND", "THEN" or commas, and a
/// part without a verb reuses the previous one ("TAKE ROPE AND BUCKET").
/// </summary>
public static class Parser
{
    public const int MaxChained = 40;

    private static readonly Dictionary<Language, HashSet<string>> Conjunctions = new()
    {
        [Language.French] = ["ET", "PUIS", "ENSUITE", "ALORS"],
        [Language.English] = ["AND", "THEN", "AFTERWARDS"],
    };

    /// <summary>Splits a line into commands and parses each.</summary>
    public static List<ParseResult> ParseLine(Language language, string line, ParserMode mode = ParserMode.Short)
    {
        var results = new List<ParseResult>();
        Verb previous = Verb.None;
        foreach (var part in Split(language, line, mode))
        {
            if (results.Count == MaxChained)
            {
                results.Add(new ParseResult(default, ParseError.TooMany));
                break;
            }
            var r = Parse(language, part, mode);
            if (mode == ParserMode.Long && r.Error == ParseError.NoVerb && previous != Verb.None)
            {
                var again = Parse(language, Parser.Format(language, new Command(previous)) + " " + part, mode);
                if (again.Ok)
                    r = again;
            }
            if (r.Ok)
                previous = r.Command.Verb;
            results.Add(r);
        }
        if (results.Count == 0)
            results.Add(new ParseResult(default, ParseError.Empty));
        return results;
    }

    private static IEnumerable<string> Split(Language language, string line, ParserMode mode)
    {
        foreach (var part in (line ?? string.Empty).Split('/'))
        {
            if (mode == ParserMode.Short)
            {
                if (!string.IsNullOrWhiteSpace(part))
                    yield return part;
                continue;
            }
            var current = new List<string>();
            var tokens = Vocabulary.Normalize(part).Replace(",", " , ").Split(' ', StringSplitOptions.RemoveEmptyEntries);
            foreach (var t in tokens)
            {
                if (t == "," || Conjunctions[language].Contains(t))
                {
                    if (current.Count > 0)
                        yield return string.Join(' ', current);
                    current.Clear();
                }
                else
                {
                    current.Add(t);
                }
            }
            if (current.Count > 0)
                yield return string.Join(' ', current);
        }
    }

    /// <summary>Parses one command such as "PRENDS LA MASSUE", "OUVRE PAQUET DE CIGARETTES" or "TAKE KEY".</summary>
    public static ParseResult Parse(Language language, string text, ParserMode mode = ParserMode.Short)
    {
        var tokens = new List<string>(Vocabulary.Normalize(text).Replace(",", " ")
            .Split(' ', StringSplitOptions.RemoveEmptyEntries));
        if (tokens.Count == 0)
            return new ParseResult(default, ParseError.Empty);

        // Two-word phrases.
        if (language == Language.English)
        {
            Join(tokens, "TAKE", "OFF", "TAKEOFF");
            Join(tokens, "PUT", "ON", "WEAR");
            Join(tokens, "TURN", "AROUND", "BACK");
            Join(tokens, "TURN", "BACK", "BACK");
            Join(tokens, "GO", "BACK", "BACK");
            Join(tokens, "ABOUT", "TURN", "BACK");
            Join(tokens, "U-TURN", null, "BACK");
            Join(tokens, "LOOK", "AROUND", "LOOK");
            Join(tokens, "FIRST", "AID", "KIT");
        }
        else
        {
            Join(tokens, "DEMI", "TOUR", "DEMI-TOUR");
            Join(tokens, "FAIS", "DEMI-TOUR", "DEMI-TOUR");
            Join(tokens, "FAITES", "DEMI-TOUR", "DEMI-TOUR");
        }

        Verb verb = Verb.None;
        Noun noun = Noun.None, target = Noun.None;
        bool afterPreposition = false;
        foreach (var token in tokens)
        {
            if (mode == ParserMode.Long && Vocabulary.IsPreposition(language, token) && verb != Verb.None && noun != Noun.None)
            {
                afterPreposition = true;
                continue;
            }
            if (Vocabulary.IsStopWord(language, token, mode))
                continue;
            var word = Vocabulary.Lookup(language, token, mode);
            if (word == null)
                return new ParseResult(default, ParseError.UnknownWord, token);
            var w = word.Value;
            if (w.IsVerb)
            {
                // "TURN LEFT", "GO RIGHT", "TOURNE A GAUCHE": the direction wins.
                if (verb == Verb.None || (verb is Verb.Back or Verb.Forward && w.Verb is Verb.Left or Verb.Right))
                    verb = w.Verb;
                // "FAIS PLEIN" names no object: the fuel is meant.
            }
            else if (afterPreposition)
            {
                if (target == Noun.None)
                    target = w.Noun;
            }
            else if (noun == Noun.None)
            {
                noun = w.Noun;
            }
            else if (language == Language.English && mode == ParserMode.Long)
            {
                // English puts the main noun last ("COCONUT PALM", "SURVIVAL KIT"); French first ("NOIX DE COCO").
                noun = w.Noun;
            }
        }
        if (verb == Verb.None)
            return new ParseResult(default, ParseError.NoVerb);
        return new ParseResult(new Command(verb, noun, target), ParseError.None);
    }

    private static void Join(List<string> tokens, string first, string second, string replacement)
    {
        for (int i = 0; i < tokens.Count; i++)
        {
            if (tokens[i] != first)
                continue;
            if (second == null)
            {
                tokens[i] = replacement;
            }
            else if (i + 1 < tokens.Count && tokens[i + 1] == second)
            {
                tokens[i] = replacement;
                tokens.RemoveAt(i + 1);
            }
        }
    }

    /// <summary>The canonical (short form) text of a command, as the touch word picker builds it.</summary>
    public static string Format(Language language, Command command)
    {
        string verb = null, noun = null;
        foreach (var w in Vocabulary.All(language))
        {
            if (verb == null && w.Verb == command.Verb && command.Verb != Verb.None)
                verb = w.Text;
            if (noun == null && w.Noun == command.Noun && command.Noun != Noun.None)
                noun = w.Text;
        }
        return noun == null ? verb ?? string.Empty : verb + " " + noun;
    }
}
