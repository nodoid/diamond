using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;
using Diamond.Core.Audio;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Input;
using Diamond.Core.Localization;
using Diamond.Core.Oric;
using Diamond.Core.Platform;
using Diamond.Core.Scenes;
using Diamond.Core.Session;

namespace Diamond.Core;

/// <summary>
/// The Diamond of Cursed Island (Le Diamant de l'Île Maudite), by PFJ, based on the 1984 Loriciels
/// game by Bertrand d'Armagnac and Frédéric Baille. Laid out on the Oric's 240x224 screen (picture
/// above, text below) but drawn at the full resolution of the display, in French or English.
/// </summary>
public class DiamondGame : Game
{
    public const int TicksPerSecond = 50;

    private const string GameFile = "game.sav";
    private const string CheckpointFile = "part2.sav";

    private readonly GraphicsDeviceManager _graphics;
    private readonly Queue<char> _text = new();
    private RenderTarget2D _target;
    private SpriteBatch _present;
    private Rectangle _destination;
    private Scene _scene;
    private Scene _pending;
    private bool _paused;
    private KeyboardState _prevKeys;

    public DiamondGame() : this(null)
    {
    }

    public DiamondGame(IPlatformServices platform)
    {
        Platform = platform ?? new DesktopPlatformServices();
        _graphics = new GraphicsDeviceManager(this);
        Content.RootDirectory = "Content";
        IsFixedTimeStep = true;
        TargetElapsedTime = TimeSpan.FromSeconds(1.0 / TicksPerSecond);

        if (Platform.IsMobile)
        {
            _graphics.IsFullScreen = true;
            _graphics.SupportedOrientations = DisplayOrientation.LandscapeLeft | DisplayOrientation.LandscapeRight;
        }
        else
        {
            _graphics.PreferredBackBufferWidth = Canvas.Width * 4;
            _graphics.PreferredBackBufferHeight = Canvas.Height * 4;
            IsMouseVisible = true;
        }
    }

    public IPlatformServices Platform { get; }
    public Canvas Canvas { get; private set; }
    public InputManager Input { get; private set; }
    public SoundBank Sound { get; private set; }
    public HighScoreTable HighScores { get; private set; }
    public GameSettings Settings { get; private set; }

    /// <summary>The game in progress, if any (kept so the menu can continue it).</summary>
    public Adventure Current { get; private set; }

    public bool IsMobile => Platform.IsMobile || (Capture?.Mobile ?? false);

    /// <summary>Store-asset capture in progress (see <see cref="Demo.CaptureDirector"/>).</summary>
    public Demo.CaptureDirector Capture { get; set; }

    internal void ShowCaptureScene(Scene scene) => _scene = scene;

    internal Scene CurrentCaptureScene => Capture != null ? _scene : null;

    /// <summary>Characters typed since the last frame (keyboard text input; '\b' backspace, '\r' enter).</summary>
    public Queue<char> TypedText => _text;

    protected override void Initialize()
    {
        Window.Title = "The Diamond of Cursed Island - Le Diamant de l'Île Maudite";
        Window.TextInput += (_, e) =>
        {
            if (_text.Count < 64)
                _text.Enqueue(e.Key == Keys.Back ? '\b' : e.Key == Keys.Enter ? '\r' : e.Character);
        };
        if (Capture != null)
        {
            // Captures render as fast as possible, even when the display is asleep.
            _graphics.SynchronizeWithVerticalRetrace = false;
            _graphics.ApplyChanges();
        }
        else if (!IsMobile)
        {
            Window.AllowUserResizing = true;
            FitWindowToDisplay();
        }
        base.Initialize();
    }

    private void FitWindowToDisplay()
    {
        var mode = GraphicsAdapter.DefaultAdapter.CurrentDisplayMode;
        int scale = 4;
        while (scale > 1 && (Canvas.Width * scale > mode.Width * 0.9 || Canvas.Height * scale > mode.Height * 0.85))
            scale--;
        _graphics.PreferredBackBufferWidth = Canvas.Width * scale;
        _graphics.PreferredBackBufferHeight = Canvas.Height * scale;
        _graphics.ApplyChanges();
    }

    protected override void LoadContent()
    {
        _present = new SpriteBatch(GraphicsDevice);
        Canvas = new Canvas(GraphicsDevice);
        Input = new InputManager(IsMobile);
        Sound = new SoundBank();
        Settings = GameSettings.Load(Platform.DataDirectory, Platform.SystemLanguage);
        Strings.Current = Capture?.Language ?? Settings.Language;
        for (int i = 0; i < Settings.Volume; i++)
            Sound.CycleVolume();
        Sound.Muted = Capture != null;
        HighScores = new HighScoreTable(Platform.DataDirectory);
        HighScores.Load();
        Current = LoadGame(GameFile);
        _scene = new TitleScene(this);
        _scene.Enter();
    }

    protected override void UnloadContent()
    {
        Sound?.Dispose();
        Canvas?.Dispose();
        _target?.Dispose();
        _present?.Dispose();
        base.UnloadContent();
    }

    protected override void OnDeactivated(object sender, EventArgs args)
    {
        if (_scene is IPausable)
            _paused = true;
        SaveGame();
        base.OnDeactivated(sender, args);
    }

    protected override void Update(GameTime gameTime)
    {
        if (Capture != null)
        {
            IsFixedTimeStep = false;
            Capture.Update(this);
            base.Update(gameTime);
            return;
        }
        UpdateDestination();
        Input.Update(ToVirtual, IsActive);

        var keys = Keyboard.GetState();
        bool altEnter = keys.IsKeyDown(Keys.Enter) && !_prevKeys.IsKeyDown(Keys.Enter) &&
                        (keys.IsKeyDown(Keys.LeftAlt) || keys.IsKeyDown(Keys.RightAlt));
        if (!IsMobile && (altEnter || (keys.IsKeyDown(Keys.F11) && !_prevKeys.IsKeyDown(Keys.F11))))
        {
            _graphics.ToggleFullScreen();
            _text.Clear();
        }
        _prevKeys = keys;

        if (_pending != null)
        {
            _scene.Leave();
            _scene = _pending;
            _pending = null;
            _paused = false;
            _text.Clear();
            _scene.Enter();
        }

        if (_scene is IPausable && _paused)
        {
            _text.Clear();
            if (Input.ConfirmPressed || Input.Taps.Count > 0)
                _paused = false;
            else if (Input.BackPressed)
            {
                _paused = false;
                ShowMenu();
            }
            base.Update(gameTime);
            return;
        }

        _scene.Tick();
        _text.Clear();
        base.Update(gameTime);
    }

    /// <summary>Largest render scale used on screen (device pixels per virtual pixel).</summary>
    public const float MaxScale = 8f;

    /// <summary>Makes sure the render target matches the resolution the frame is drawn at.</summary>
    private float PrepareTarget()
    {
        UpdateDestination();
        float scale = Capture?.Scale ?? Math.Clamp((float)_destination.Width / Canvas.Width, 1f, MaxScale);
        int w = (int)MathF.Round(Canvas.Width * scale), h = (int)MathF.Round(Canvas.Height * scale);
        if (_target == null || _target.Width != w || _target.Height != h)
        {
            _target?.Dispose();
            _target = new RenderTarget2D(GraphicsDevice, w, h, false, SurfaceFormat.Color, DepthFormat.None,
                Platform.IsMobile ? 0 : 4, RenderTargetUsage.DiscardContents);
        }
        return scale;
    }

    protected override void Draw(GameTime gameTime)
    {
        float scale = PrepareTarget();
        GraphicsDevice.SetRenderTarget(_target);
        GraphicsDevice.Clear(Color.Black);
        Canvas.Begin(scale);
        _scene.Draw(Canvas);
        if (_paused && Capture == null)
        {
            Canvas.Fill(78, 60, 84, 26, OricColor.Blue);
            Canvas.TextCentered(64, Strings.Paused, OricColor.Yellow);
            Canvas.TextCentered(75, Strings.Resume(IsMobile), OricColor.White);
        }
        Canvas.End();
        GraphicsDevice.SetRenderTarget(null);
        Capture?.AfterDraw(_target);

        GraphicsDevice.Clear(Color.Black);
        _present.Begin(SpriteSortMode.Immediate, BlendState.Opaque, SamplerState.LinearClamp);
        _present.Draw(_target, _destination, Color.White);
        _present.End();
        base.Draw(gameTime);
    }

    private void UpdateDestination()
    {
        var pp = GraphicsDevice.PresentationParameters;
        _destination = ComputeDestination(pp.BackBufferWidth, pp.BackBufferHeight, false);
    }

    /// <summary>Largest aspect-correct rectangle for the Oric screen, integer scaled when it fits.</summary>
    public static Rectangle ComputeDestination(int backWidth, int backHeight, bool preferInteger)
    {
        float scale = Math.Min((float)backWidth / Canvas.Width, (float)backHeight / Canvas.Height);
        if (preferInteger && scale >= 1f)
            scale = (float)Math.Floor(scale);
        int w = Math.Max(1, (int)(Canvas.Width * scale));
        int h = Math.Max(1, (int)(Canvas.Height * scale));
        return new Rectangle((backWidth - w) / 2, (backHeight - h) / 2, w, h);
    }

    /// <summary>Converts window / touch coordinates into Oric pixels.</summary>
    public Vector2 ToVirtual(Vector2 screen)
    {
        if (_destination.Width == 0 || _destination.Height == 0)
            return new Vector2(-1, -1);
        return new Vector2(
            (screen.X - _destination.X) * Canvas.Width / _destination.Width,
            (screen.Y - _destination.Y) * Canvas.Height / _destination.Height);
    }

    // ---------------- flow ----------------

    public void SwitchTo(Scene scene) => _pending = scene;

    public void ShowTitle() => SwitchTo(new TitleScene(this));

    public void ShowMenu() => SwitchTo(new MenuScene(this));

    public void ShowInstructions() => SwitchTo(new InstructionsScene(this));

    public void ShowHallOfFame(Adventure finished = null) => SwitchTo(new HallOfFameScene(this, finished));

    /// <summary>A new game: the story first, then the beach.</summary>
    public void StartNewGame()
    {
        Current = new Adventure(Sound);
        DeleteFile(GameFile);
        DeleteFile(CheckpointFile);
        Sound.Play(Sfx.Start);
        SwitchTo(new StoryScene(this, Current));
    }

    public void ContinueGame()
    {
        if (Current == null || Current.Ended)
            return;
        SwitchTo(new GameScene(this, Current, false));
    }

    public bool HasCheckpoint => File.Exists(Path.Combine(Platform.DataDirectory, CheckpointFile));

    /// <summary>Starts again from the beginning of part two (saved when it was reached).</summary>
    public void RestartPart2()
    {
        var a = LoadGame(CheckpointFile);
        if (a == null)
            return;
        Current = a;
        Sound.Play(Sfx.Start);
        SwitchTo(new GameScene(this, Current, true));
    }

    public void PlayAdventure(Adventure adventure) => SwitchTo(new GameScene(this, adventure, true));

    /// <summary>The explorer has gone through the grille: save the checkpoint and show the interlude.</summary>
    public void EnteredPart2(Adventure adventure)
    {
        adventure.EnteredPart2 = false;
        if (Capture != null)
            return;
        WriteFile(CheckpointFile, adventure.Save());
        SaveGame();
        SwitchTo(new PartTwoScene(this, adventure));
    }

    public void GameEnded(Adventure adventure)
    {
        Current = null;
        DeleteFile(GameFile);
        if (adventure.Won)
            DeleteFile(CheckpointFile);
        SwitchTo(new EndScene(this, adventure));
    }

    /// <summary>Saves the game in progress (after every command, and when the app is sent to the background).</summary>
    public void SaveGame()
    {
        if (Capture != null || Current == null || Current.Ended)
            return;
        WriteFile(GameFile, Current.Save());
    }

    private Adventure LoadGame(string file)
    {
        try
        {
            string path = Path.Combine(Platform.DataDirectory, file);
            if (!File.Exists(path))
                return null;
            var a = Adventure.Load(File.ReadAllText(path), Sound);
            return a is { Ended: false } ? a : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private void WriteFile(string file, string text)
    {
        try
        {
            Directory.CreateDirectory(Platform.DataDirectory);
            File.WriteAllText(Path.Combine(Platform.DataDirectory, file), text);
        }
        catch (Exception)
        {
        }
    }

    private void DeleteFile(string file)
    {
        try
        {
            File.Delete(Path.Combine(Platform.DataDirectory, file));
        }
        catch (Exception)
        {
        }
    }

    public void ToggleLanguage()
    {
        Strings.Current = Strings.Current == Language.French ? Language.English : Language.French;
        Settings.Language = Strings.Current;
        Settings.Save();
    }

    public void ToggleParserMode()
    {
        Settings.Parser = Settings.Parser == ParserMode.Short ? ParserMode.Long : ParserMode.Short;
        Settings.Save();
    }

    public void CycleVolume()
    {
        Sound.CycleVolume();
        Settings.Volume = (Settings.Volume + 1) % 4;
        Settings.Save();
    }

    public void Quit()
    {
        SaveGame();
        Platform.Quit(this);
    }
}

/// <summary>Marks scenes that may be paused (gameplay).</summary>
public interface IPausable
{
}

/// <summary>Player preferences persisted between runs.</summary>
public sealed class GameSettings
{
    private const string FileName = "settings.txt";
    private string _directory;

    public Language Language { get; set; }

    /// <summary>Volume step index as used by <see cref="SoundBank.CycleVolume"/>.</summary>
    public int Volume { get; set; }

    /// <summary>Short form (1984 abbreviations) or long form (sentences).</summary>
    public ParserMode Parser { get; set; } = ParserMode.Short;

    /// <summary>Loads the settings; the first run takes its language from the device.</summary>
    public static GameSettings Load(string directory, string systemLanguage)
    {
        var s = new GameSettings { _directory = directory, Language = Strings.FromIso(systemLanguage) };
        try
        {
            string path = Path.Combine(directory, FileName);
            if (File.Exists(path))
                s.Parse(File.ReadAllText(path));
        }
        catch (Exception)
        {
        }
        return s;
    }

    internal void Parse(string text)
    {
        foreach (var line in text.Split('\n'))
        {
            var kv = line.Split('=');
            if (kv.Length != 2)
                continue;
            string value = kv[1].Trim();
            if (kv[0] == "language")
                Language = Strings.FromIso(value);
            else if (kv[0] == "volume" && int.TryParse(value, out int v))
                Volume = Math.Clamp(v, 0, 3);
            else if (kv[0] == "parser")
                Parser = value == "long" ? ParserMode.Long : ParserMode.Short;
        }
    }

    internal string Serialize() =>
        $"language={Strings.IsoCode(Language)}\nvolume={Volume}\nparser={(Parser == ParserMode.Long ? "long" : "short")}\n";

    public void Save()
    {
        try
        {
            Directory.CreateDirectory(_directory);
            File.WriteAllText(Path.Combine(_directory, FileName), Serialize());
        }
        catch (Exception)
        {
        }
    }
}
