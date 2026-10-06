using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Input;
using Diamond.Core.Audio;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;
using Diamond.Core.Oric;
using Diamond.Core.World;

namespace Diamond.Core.Scenes;

/// <summary>
/// The adventure: the picture of what the explorer sees above, the status line, the story so far,
/// the command line and the buttons below. Orders are typed (with the short form's completion as
/// in 1984, or as sentences in the long form) or built by touch from the word list.
/// </summary>
public sealed class GameScene : Scene, IPausable
{
    public const int StatusY = 137;
    public const int LogY = 147;
    public const int LogLines = 6;
    public const int InputY = 197;
    public const int ButtonsY = 207;
    public const int Columns = 40;

    /// <summary>Ticks between chained commands, so each step can be seen.</summary>
    private const int StepDelay = 12;

    /// <summary>Real time: a minute of inactivity counts as one move, as the original ran in real time.</summary>
    private const int IdleTicks = 60 * DiamondGame.TicksPerSecond;

    private static readonly Color LogColor = new(235, 235, 220);
    private static readonly Color EchoColor = new(120, 220, 255);
    private static readonly Color WarnColor = new(255, 200, 90);

    private readonly Adventure _a;
    private readonly bool _fresh;
    private readonly List<(string text, Color color)> _log = new();
    private readonly CommandLine _line = new();
    private readonly Queue<Command> _queue = new();
    private readonly List<string> _history = new();
    private int _historyIndex = -1;
    private int _scroll;
    private int _stepTimer;
    private int _idle;
    private int _endTimer = -1;
    private int _beepFlash;
    private float? _dragY;
    private int _wheel;

    // Word list (touch / mouse).
    private enum Picker { Closed, Verbs, Nouns }
    private Picker _picker;
    private Verb _pickVerb;
    private int _pickPage;

    public GameScene(DiamondGame game, Adventure adventure, bool fresh) : base(game)
    {
        _a = adventure;
        _fresh = fresh;
    }

    private Language Lang => Strings.Current;
    private ParserMode Mode => Game.Settings.Parser;

    public override void Enter()
    {
        _wheel = Mouse.GetState().ScrollWheelValue;
        if (_fresh || _log.Count == 0)
            Print(_a.Begin());
        Game.SaveGame();
    }

    // ------------------------------------------------------------------ log

    private void Print(IEnumerable<Loc> lines, Color? color = null)
    {
        foreach (var l in lines)
            Print(l.ToString(), color ?? LogColor);
    }

    private void Print(string text, Color color)
    {
        foreach (var line in Strings.Wrap(text, Columns))
            _log.Add((line, color));
        while (_log.Count > 300)
            _log.RemoveAt(0);
        _scroll = 0;
    }

    // ------------------------------------------------------------------ update

    protected override void Update()
    {
        var input = Game.Input;

        if (_endTimer >= 0)
        {
            _endTimer++;
            if (_endTimer > 40 && (input.ConfirmPressed || input.Taps.Count > 0) || _endTimer > 400)
                Game.GameEnded(_a);
            return;
        }
        if (_beepFlash > 0)
            _beepFlash--;

        if (input.BackPressed)
        {
            if (_picker != Picker.Closed)
                _picker = Picker.Closed;
            else
            {
                Game.SaveGame();
                Game.ShowMenu();
            }
            return;
        }

        // Chained commands run one at a time.
        if (_queue.Count > 0)
        {
            if (--_stepTimer <= 0)
            {
                Run(_queue.Dequeue());
                _stepTimer = StepDelay;
            }
            return;
        }

        if (++_idle >= IdleTicks && _picker == Picker.Closed)
        {
            _idle = 0;
            var lines = _a.Wait();
            Print(lines, WarnColor);
            AfterCommand();
            if (_endTimer >= 0)
                return;
        }

        UpdateScroll(input);
        if (_picker != Picker.Closed)
        {
            UpdatePicker(input);
            return;
        }

        UpdateKeyboard(input);
        UpdateButtons(input);
    }

    private void UpdateScroll(Input.InputManager input)
    {
        var keys = Keyboard.GetState();
        int wheel = Mouse.GetState().ScrollWheelValue;
        int maxScroll = Math.Max(0, _log.Count - LogLines);
        if (wheel != _wheel)
        {
            _scroll = Math.Clamp(_scroll + Math.Sign(wheel - _wheel) * 2, 0, maxScroll);
            _wheel = wheel;
        }
        if (Pressed(keys, Keys.PageUp))
            _scroll = Math.Clamp(_scroll + LogLines - 1, 0, maxScroll);
        if (Pressed(keys, Keys.PageDown))
            _scroll = Math.Clamp(_scroll - (LogLines - 1), 0, maxScroll);
        _prevKeys = keys;

        // Dragging over the text scrolls it.
        if (input.Holding is { } h && h.Y >= LogY && h.Y < InputY && _picker == Picker.Closed)
        {
            if (_dragY is { } y0)
            {
                int lines = (int)((h.Y - y0) / 8);
                if (lines != 0)
                {
                    _scroll = Math.Clamp(_scroll + lines, 0, maxScroll);
                    _dragY = y0 + lines * 8;
                }
            }
            else
            {
                _dragY = h.Y;
            }
        }
        else
        {
            _dragY = null;
        }
    }

    private KeyboardState _prevKeys;

    private bool Pressed(KeyboardState keys, Keys k) => keys.IsKeyDown(k) && !_prevKeys.IsKeyDown(k);

    private void UpdateKeyboard(Input.InputManager input)
    {
        _line.Language = Lang;
        _line.Mode = Mode;
        foreach (char ch in Game.TypedText)
        {
            _idle = 0;
            if (!char.IsControl(ch) && !OricFont.CanDraw(char.ToUpperInvariant(ch)))
                continue;
            switch (_line.Type(ch))
            {
                case Keystroke.Typed:
                case Keystroke.Erased:
                    Game.Sound.Play(Sfx.Key);
                    break;
                case Keystroke.Beep:
                    Beep();
                    break;
                case Keystroke.Submit:
                    Submit(_line.Submitted);
                    break;
            }
        }

        if (_line.Length == 0)
        {
            if (input.UpPressed) Order(new Command(Verb.Forward));
            else if (input.LeftPressed) Order(new Command(Verb.Left));
            else if (input.RightPressed) Order(new Command(Verb.Right));
            else if (input.DownPressed) Order(new Command(Verb.Back));
        }
        else if (input.UpPressed && _history.Count > 0)
        {
            _historyIndex = _historyIndex < 0 ? _history.Count - 1 : Math.Max(0, _historyIndex - 1);
            _line.Set(_history[_historyIndex]);
        }
        else if (input.DownPressed && _historyIndex >= 0)
        {
            _historyIndex++;
            _line.Set(_historyIndex < _history.Count ? _history[_historyIndex] : null);
            if (_historyIndex >= _history.Count)
                _historyIndex = -1;
        }
    }

    private void Beep()
    {
        Game.Sound.Play(Sfx.Beep);
        _beepFlash = 10;
    }

    private void Submit(string line)
    {
        _historyIndex = -1;
        if (string.IsNullOrEmpty(line))
            return;
        if (_history.Count == 0 || _history[^1] != line)
            _history.Add(line);
        Print("> " + line, EchoColor);
        var results = Parser.ParseLine(Lang, line, Mode);
        foreach (var r in results)
        {
            if (!r.Ok)
            {
                Beep();
                Print(r.Error switch
                {
                    ParseError.UnknownWord => Strings.UnknownWord(r.BadWord),
                    ParseError.TooMany => Strings.TooMany,
                    _ => Strings.NoVerb,
                }, WarnColor);
                break;
            }
            _queue.Enqueue(r.Command);
        }
        _stepTimer = 0;
    }

    /// <summary>A command from a button or the word list: echoed, then run.</summary>
    private void Order(Command command)
    {
        _idle = 0;
        Print("> " + Parser.Format(Lang, command), EchoColor);
        _queue.Enqueue(command);
        _stepTimer = 0;
    }

    private void Run(Command command)
    {
        _idle = 0;
        Print(_a.Execute(command));
        AfterCommand();
    }

    private void AfterCommand()
    {
        if (_a.Ended)
        {
            _queue.Clear();
            _endTimer = 0;
            return;
        }
        Game.SaveGame();
        if (_a.EnteredPart2)
        {
            _queue.Clear();
            Game.EnteredPart2(_a);
        }
    }

    // ------------------------------------------------------------------ autopilot (store captures)

    /// <summary>Runs a command at once, as if it had been typed (echoed in the short form).</summary>
    internal void Feed(Command command)
    {
        Print("> " + Parser.Format(Lang, command), EchoColor);
        Print(_a.Execute(command));
        _a.EnteredPart2 = false;
    }

    /// <summary>Shows a half-typed order (null clears it).</summary>
    internal void SetInput(string text)
    {
        _line.Set(text);
    }

    /// <summary>Opens the word list at the nouns for a verb (Verb.None closes it).</summary>
    internal void OpenPicker(Verb verb)
    {
        _picker = verb == Verb.None ? Picker.Closed : Picker.Nouns;
        _pickVerb = verb;
        _pickPage = 0;
    }

    // ------------------------------------------------------------------ buttons

    private static readonly RectF LeftButton = new(2, ButtonsY, 28, 15);
    private static readonly RectF ForwardButton = new(33, ButtonsY, 28, 15);
    private static readonly RectF BackButton = new(64, ButtonsY, 28, 15);
    private static readonly RectF RightButton = new(95, ButtonsY, 28, 15);
    private static readonly RectF WordsButton = new(128, ButtonsY, 58, 15);
    private static readonly RectF MenuButton = new(190, ButtonsY, 48, 15);
    private static readonly RectF InputBox = new(0, InputY - 1, Canvas.Width, 9);

    private void UpdateButtons(Input.InputManager input)
    {
        var taps = input.Taps;
        if (taps.Count == 0)
            return;
        if (Ui.Hit(LeftButton, taps)) Order(new Command(Verb.Left));
        else if (Ui.Hit(ForwardButton, taps)) Order(new Command(Verb.Forward));
        else if (Ui.Hit(BackButton, taps)) Order(new Command(Verb.Back));
        else if (Ui.Hit(RightButton, taps)) Order(new Command(Verb.Right));
        else if (Ui.Hit(WordsButton, taps) || (Game.IsMobile && Ui.Hit(InputBox, taps)))
        {
            _picker = Picker.Verbs;
            _pickPage = 0;
            Game.Sound.Play(Sfx.Menu);
        }
        else if (Ui.Hit(MenuButton, taps))
        {
            Game.SaveGame();
            Game.ShowMenu();
        }
    }

    // ------------------------------------------------------------------ word list

    private const int PickTop = 14, PickRows = 12, PickCols = 3, PickH = 14, PickW = 78;
    private static readonly RectF PickBack = new(2, 188, 76, 16);
    private static readonly RectF PickAlone = new(82, 188, 76, 16);
    private static readonly RectF PickMore = new(162, 188, 76, 16);

    /// <summary>Verbs that need no noun run as soon as they are picked.</summary>
    private static bool Standalone(Verb v) => v is Verb.Look or Verb.Inventory or Verb.Status or Verb.Help or Verb.Dig
        or Verb.Fly or Verb.Rest or Verb.Descend;

    private List<Word> PickWords()
    {
        var primary = Vocabulary.Primary(Lang);
        if (_picker == Picker.Verbs)
            return primary.Where(w => w.IsVerb && w.Verb is not (Verb.Forward or Verb.Left or Verb.Right or Verb.Back)).ToList();
        var seen = _a.Seen;
        return primary.Where(w => !w.IsVerb && seen.Contains(w.Noun)).ToList();
    }

    private int PageCount(int words) => Math.Max(1, (words + PickRows * PickCols - 1) / (PickRows * PickCols));

    private static RectF Cell(int i) =>
        new(2 + i / PickRows * (PickW + 1), PickTop + i % PickRows * PickH, PickW, PickH - 1);

    private void UpdatePicker(Input.InputManager input)
    {
        var words = PickWords();
        int perPage = PickRows * PickCols;
        int pages = PageCount(words.Count);
        _pickPage = Math.Min(_pickPage, pages - 1);
        foreach (var tap in input.Taps)
        {
            if (PickBack.Inflate(1).Contains(tap))
            {
                _picker = _picker == Picker.Nouns ? Picker.Verbs : Picker.Closed;
                _pickPage = 0;
                return;
            }
            if (PickMore.Inflate(1).Contains(tap) && pages > 1)
            {
                _pickPage = (_pickPage + 1) % pages;
                return;
            }
            if (_picker == Picker.Nouns && PickAlone.Inflate(1).Contains(tap))
            {
                _picker = Picker.Closed;
                Order(new Command(_pickVerb));
                return;
            }
            for (int i = 0; i < perPage; i++)
            {
                int index = _pickPage * perPage + i;
                if (index >= words.Count || !Cell(i).Contains(tap))
                    continue;
                var w = words[index];
                Game.Sound.Play(Sfx.Menu);
                if (_picker == Picker.Verbs)
                {
                    if (Standalone(w.Verb))
                    {
                        _picker = Picker.Closed;
                        Order(new Command(w.Verb));
                    }
                    else
                    {
                        _pickVerb = w.Verb;
                        _picker = Picker.Nouns;
                        _pickPage = 0;
                    }
                }
                else
                {
                    _picker = Picker.Closed;
                    Order(new Command(_pickVerb, w.Noun));
                }
                return;
            }
        }
        // Typing still works while the list is open.
        if (Game.TypedText.Count > 0)
        {
            _picker = Picker.Closed;
            UpdateKeyboard(input);
        }
    }

    // ------------------------------------------------------------------ drawing

    public override void Draw(Canvas c)
    {
        ViewRenderer.Draw(c, _a, Ticks);
        if (_a.Ended && !_a.Won)
            c.Fill(0, 0, Canvas.Width, 136, new Color(120, 0, 0) * Math.Min(0.55f, _endTimer / 60f));
        c.Fill(0, 136, Canvas.Width, Canvas.Height - 136, new Color(4, 8, 22));
        c.Fill(0, 136, Canvas.Width, 0.6f, new Color(90, 130, 200));
        DrawStatus(c);
        DrawLog(c);
        DrawInput(c);
        DrawButtons(c);
        if (_picker != Picker.Closed)
            DrawPicker(c);
    }

    private void DrawStatus(Canvas c)
    {
        string facing = Lang == Language.French ? "NESO"[(int)_a.Facing].ToString() : "NESW"[(int)_a.Facing].ToString();
        string name = (_a.UpPalm ? (Lang == Language.French ? "En haut du cocotier" : "Up the coconut palm") : _a.Location.Name.ToString())
            .ToUpperInvariant();
        if (name.Length > 24)
            name = name[..24];
        c.Fill(0, StatusY - 0.5f, Canvas.Width, 9, new Color(16, 32, 70));
        c.Text(2, StatusY + 0.5f, name, Ui.Gold);
        c.Text(232, StatusY + 0.5f, facing, Color.White);

        string label = Strings.Fitness;
        float barX = 186, barW = 42;
        c.Text(barX - Canvas.TextWidth(label) - 3, StatusY + 0.5f, label, Ui.Sky);
        float f = Math.Clamp(_a.Health.Fitness / (float)Health.MaxFitness, 0f, 1f);
        var col = f > 0.6f ? new Color(80, 220, 90) : f > 0.3f ? new Color(240, 200, 60) : new Color(240, 60, 50);
        if (f <= 0.3f && Ticks / 15 % 2 == 0)
            col = Color.Lerp(col, Color.White, 0.4f);
        c.Fill(barX, StatusY + 1.5f, barW, 5, new Color(40, 40, 60));
        c.Fill(barX, StatusY + 1.5f, barW * f, 5, col);
        c.Frame(barX, StatusY + 1.5f, barW, 5, new Color(150, 170, 220), 0.4f);
    }

    private void DrawLog(Canvas c)
    {
        int end = _log.Count - _scroll;
        int start = Math.Max(0, end - LogLines);
        for (int i = start; i < end; i++)
            c.Text(0, LogY + (i - start) * 8, _log[i].text, _log[i].color);
        if (_scroll > 0)
            c.Text(234, LogY, "^", Ui.Sky);
    }

    private void DrawInput(Canvas c)
    {
        var bg = _beepFlash > 0 ? new Color(120, 20, 20) : new Color(10, 20, 45);
        c.Fill(0, InputY - 1, Canvas.Width, 9, bg);
        if (_line.Length == 0 && _queue.Count == 0)
        {
            c.Text(0, InputY, ">", Ui.Gold);
            if (Ticks / 20 % 2 == 0)
                c.Fill(7, InputY, 5, 7, Ui.Gold);
            c.Text(18, InputY, Strings.TypeHere(Game.IsMobile), new Color(90, 110, 150));
            return;
        }
        _line.Language = Lang;
        _line.Mode = Mode;
        string text = "> " + _line.Text;
        string ghost = _line.Ghost;
        int visible = Columns - 1 - ghost.Length;
        if (text.Length > visible)
            text = text[^Math.Max(1, visible)..];
        c.Text(0, InputY, text, Color.White);
        float x = Canvas.TextWidth(text);
        if (ghost.Length > 0)
            c.Text(x, InputY, ghost, new Color(110, 140, 190));
        if (Ticks / 20 % 2 == 0)
            c.Fill(x + Canvas.TextWidth(ghost) + 1, InputY, 5, 7, Ui.Gold);
    }

    private void DrawButtons(Canvas c)
    {
        var p = Game.Input.Pointer;
        bool Hot(RectF r) => p is { } v && r.Contains(v);
        Ui.ArrowButton(c, LeftButton, -1, Hot(LeftButton));
        Ui.ArrowButton(c, ForwardButton, 0, Hot(ForwardButton));
        Ui.ArrowButton(c, BackButton, 2, Hot(BackButton));
        Ui.ArrowButton(c, RightButton, 1, Hot(RightButton));
        Ui.Button(c, WordsButton, Strings.Words, Hot(WordsButton) || _picker != Picker.Closed);
        // The word list has its own BACK button: no MENU while it is open.
        if (_picker == Picker.Closed)
            Ui.Button(c, MenuButton, Strings.Menu, Hot(MenuButton));
    }

    private void DrawPicker(Canvas c)
    {
        c.Fill(0, 0, Canvas.Width, ButtonsY - 2, Ui.Panel * 0.94f);
        var words = PickWords();
        string title = _picker == Picker.Verbs
            ? Strings.ChooseVerb
            : Strings.ChooseNoun(Parser.Format(Lang, new Command(_pickVerb)));
        c.TextCentered(3, title, Ui.Gold);
        int perPage = PickRows * PickCols;
        var pointer = Game.Input.Pointer;
        for (int i = 0; i < perPage; i++)
        {
            int index = _pickPage * perPage + i;
            if (index >= words.Count)
                break;
            var r = Cell(i);
            Ui.Button(c, r, words[index].Text, pointer is { } v && r.Contains(v));
        }
        bool hotBack = pointer is { } pb && PickBack.Contains(pb);
        Ui.Button(c, PickBack, Strings.Back, hotBack);
        if (_picker == Picker.Nouns)
            Ui.Button(c, PickAlone, Strings.Alone, pointer is { } pa && PickAlone.Contains(pa));
        int pages = PageCount(words.Count);
        if (pages > 1)
            Ui.Button(c, PickMore, Strings.More + $" {_pickPage + 1}/{pages}", pointer is { } pm && PickMore.Contains(pm));
    }
}
