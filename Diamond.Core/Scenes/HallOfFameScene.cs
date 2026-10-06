using Microsoft.Xna.Framework;
using Diamond.Core.Audio;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;
using Diamond.Core.Oric;
using Diamond.Core.Session;

namespace Diamond.Core.Scenes;

/// <summary>The hall of fame, with arcade style name entry after a qualifying game.</summary>
public sealed class HallOfFameScene : Scene
{
    private const string Alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789. <";
    private const char EndMark = '<';
    private const int NameY = 100;
    private readonly Adventure _finished;
    private bool _entering;
    private char[] _name;
    private int _cursor;
    private int _letter;
    private int _rank = -1;

    public HallOfFameScene(DiamondGame game, Adventure finished) : base(game)
    {
        _finished = finished;
    }

    public bool Entering => _entering;

    public override void Enter()
    {
        if (_finished != null && Game.HighScores.Qualifies(_finished.Score, _finished.Moves))
        {
            _entering = true;
            _name = new string(' ', HighScoreTable.NameLength).ToCharArray();
        }
    }

    protected override void Update()
    {
        var input = Game.Input;
        if (_entering)
        {
            UpdateEntry();
            return;
        }
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (Ticks > 25 && (input.BackPressed || input.ConfirmPressed || input.Taps.Count > 0))
            Game.ShowMenu();
        else if (Ticks > 900)
            Game.ShowTitle();
    }

    private void UpdateEntry()
    {
        var input = Game.Input;
        if (Ticks < 30)
            return;

        foreach (char ch in Game.TypedText)
        {
            char u = char.ToUpperInvariant(ch);
            if (ch == '\b')
            {
                if (_cursor > 0)
                    _name[--_cursor] = ' ';
            }
            else if (ch == '\r')
            {
                Finish();
                return;
            }
            else if (_cursor < HighScoreTable.NameLength && ((u >= 'A' && u <= 'Z') || (u >= '0' && u <= '9') || u == '.'))
            {
                _name[_cursor++] = u;
            }
        }

        int step = 0;
        if (input.LeftPressed || input.UpPressed) step = -1;
        if (input.RightPressed || input.DownPressed) step = 1;
        bool accept = Game.IsMobile && input.ConfirmPressed;

        // Touch: the left and right thirds change the letter, the middle accepts it.
        foreach (var tap in input.Taps)
        {
            if (tap.X < Canvas.Width / 3f) step = -1;
            else if (tap.X > Canvas.Width * 2 / 3f) step = 1;
            else accept = true;
        }

        if (step != 0)
        {
            _letter = (_letter + step + Alphabet.Length) % Alphabet.Length;
            Game.Sound.Play(Sfx.Step);
        }

        if (accept && _cursor < HighScoreTable.NameLength)
        {
            char ch = Alphabet[_letter];
            if (ch == EndMark)
            {
                Finish();
                return;
            }
            _name[_cursor++] = ch;
            Game.Sound.Play(Sfx.Menu);
        }
        if (_cursor >= HighScoreTable.NameLength || input.BackPressed)
            Finish();
    }

    private void Finish()
    {
        _entering = false;
        _rank = Game.HighScores.Add(_finished.Score, _finished.Moves, new string(_name));
        Game.HighScores.Save();
        Game.Sound.Play(Sfx.Treasure);
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, "title", 0.65f);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.HallOfFame, 2)) / 2, 4, Strings.HallOfFame, Ui.Gold, 2);
        if (_entering)
        {
            c.TextCentered(40, Strings.YourScore + " " + _finished.Score + "/100", OricColor.Yellow);
            c.TextCentered(70, Strings.EnterName, OricColor.Cyan);
            int x0 = (Canvas.Width - HighScoreTable.NameLength * 12) / 2;
            for (int i = 0; i < HighScoreTable.NameLength; i++)
            {
                char ch = i < _cursor ? _name[i] : (i == _cursor && Game.IsMobile ? Alphabet[_letter] : '-');
                bool blink = i == _cursor && Ticks / 10 % 2 == 0;
                if (blink)
                    c.Fill(x0 + i * 12 - 1, NameY - 1, 8, 10, OricColor.Yellow);
                c.Text(x0 + i * 12, NameY, ch.ToString(), blink ? OricColor.Blue : OricColor.White);
            }
            if (Game.IsMobile)
            {
                c.Text(24, NameY, "<", OricColor.Yellow, 2);
                c.Text(204, NameY, ">", OricColor.Yellow, 2);
                c.TextCentered(136, Strings.ChangeLetter(true), OricColor.Yellow);
                c.TextCentered(148, Strings.AcceptLetter(true), OricColor.Yellow);
                c.TextCentered(160, Strings.EndMarkHint, OricColor.Yellow);
            }
            return;
        }

        c.TextAt(4, 28, Strings.ScoreHeader, OricColor.Cyan);
        c.TextAt(14, 28, Strings.MovesHeader, OricColor.Cyan);
        c.TextAt(24, 28, Strings.NameHeader, OricColor.Cyan);
        var entries = Game.HighScores.Entries;
        for (int i = 0; i < entries.Count; i++)
        {
            var ink = i == _rank && Ticks / 8 % 2 == 0 ? Color.White : Ui.Gold;
            float y = 42 + i * 15;
            c.TextAt(1, y, $"{i + 1,2}", OricColor.Green);
            c.Text(4 * 6, y, $"{entries[i].Score,3}", ink);
            c.Text(14 * 6, y, $"{entries[i].Moves,5}", ink);
            c.Text(24 * 6, y, entries[i].Name, ink);
        }
        Ui.Blink(c, Ticks, 202, Strings.PlayOrMenu(Game.IsMobile));
    }
}
