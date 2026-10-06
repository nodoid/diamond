using System;
using System.Text;
using Diamond.Core.Localization;

namespace Diamond.Core.Engine;

/// <summary>What typing a character did.</summary>
public enum Keystroke
{
    Ignored,
    Typed,
    Erased,
    /// <summary>The short form refused a word: it was unknown (and erased) or still ambiguous.</summary>
    Beep,
    /// <summary>ENTER: the line is ready in <see cref="CommandLine.Submitted"/>.</summary>
    Submit,
}

/// <summary>
/// The command line being typed. In the short form it behaves like the 1984 original: as soon as a
/// word is finished (space, "/" or ENTER) it is completed if it is a known abbreviation, and
/// erased with a beep if it is unknown. The long form takes the line as it is.
/// </summary>
public sealed class CommandLine
{
    public const int MaxLength = 200;

    private readonly StringBuilder _text = new();

    public Language Language { get; set; } = Language.French;
    public ParserMode Mode { get; set; } = ParserMode.Short;

    public string Text => _text.ToString();
    public int Length => _text.Length;

    /// <summary>The line given by the last <see cref="Keystroke.Submit"/>.</summary>
    public string Submitted { get; private set; }

    public void Clear() => _text.Clear();

    public void Set(string text)
    {
        _text.Clear();
        if (text != null)
            _text.Append(text);
    }

    /// <summary>The word being typed (after the last space, "/", comma or apostrophe).</summary>
    public string CurrentWord
    {
        get
        {
            string s = _text.ToString();
            int i = s.LastIndexOfAny([' ', '/', ',', '\'']);
            return s[(i + 1)..];
        }
    }

    /// <summary>The rest of the word the current abbreviation stands for ("SSUE" after "MA" + "S"), or "".</summary>
    public string Ghost
    {
        get
        {
            string word = CurrentWord;
            if (word.Length < Vocabulary.MinPrefix)
                return string.Empty;
            var full = Vocabulary.Complete(Language, word, Mode);
            string typed = Vocabulary.Normalize(word);
            return full != null && full.Length > typed.Length && full.StartsWith(typed, StringComparison.Ordinal)
                ? full[typed.Length..]
                : string.Empty;
        }
    }

    public Keystroke Type(char ch)
    {
        switch (ch)
        {
            case '\r':
            case '\n':
                if (Mode == ParserMode.Short && !CheckWord())
                    return Keystroke.Beep;
                Submitted = _text.ToString().Trim();
                _text.Clear();
                return Keystroke.Submit;
            case '\b':
                if (_text.Length == 0)
                    return Keystroke.Ignored;
                _text.Length--;
                return Keystroke.Erased;
            case '\t':
                var full = Vocabulary.Complete(Language, CurrentWord, Mode);
                if (full == null)
                    return Keystroke.Ignored;
                ReplaceCurrentWord(full);
                _text.Append(' ');
                return Keystroke.Typed;
            case ' ':
            case '/':
            case ',':
                return Separator(ch);
        }
        if (char.IsControl(ch) || _text.Length >= MaxLength)
            return Keystroke.Ignored;
        _text.Append(char.ToUpperInvariant(ch));
        return Keystroke.Typed;
    }

    private Keystroke Separator(char ch)
    {
        if (_text.Length == 0 || (ch == ' ' && _text[^1] is ' ' or '/'))
            return Keystroke.Ignored;
        if (Mode == ParserMode.Short && !CheckWord())
            return Keystroke.Beep;
        if (_text.Length > 0 && _text[^1] == ' ' && ch != ' ')
            _text.Length--;
        _text.Append(ch);
        return Keystroke.Typed;
    }

    /// <summary>Completes or erases the word just finished (short form). False when it beeped.</summary>
    private bool CheckWord()
    {
        string word = CurrentWord;
        if (word.Length == 0 || Vocabulary.IsStopWord(Language, word))
            return true;
        var full = Vocabulary.Complete(Language, word);
        if (full != null)
        {
            ReplaceCurrentWord(full);
            return true;
        }
        // Unknown: erased, as in 1984. Ambiguous (the start of several words): kept, to be finished.
        if (!Vocabulary.IsPrefix(Language, word))
            ReplaceCurrentWord(string.Empty);
        return false;
    }

    private void ReplaceCurrentWord(string word)
    {
        _text.Length -= CurrentWord.Length;
        _text.Append(word);
    }
}
