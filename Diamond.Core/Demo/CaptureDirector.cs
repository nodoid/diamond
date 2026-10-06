using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Xna.Framework.Graphics;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.Scenes;
using Diamond.Core.World;

namespace Diamond.Core.Demo;

/// <summary>
/// Store screenshots: plays the walkthrough on autopilot and saves the screen at chosen moments,
/// at high resolution (default 10x: 2400 x 2240).
///
///     Diamond --capture &lt;folder&gt; [--video] [--mobile] [--lang fr|en] [--scale n]
///
/// Each still is written to &lt;folder&gt;/stills/NN-name.png and the game quits when done. With --video,
/// the app preview frames and soundtrack are written instead (see <see cref="VideoDirector"/>).
/// </summary>
public sealed class CaptureDirector
{
    private sealed record Shot(string Name, Func<Adventure, bool> When, Func<DiamondGame, Adventure, GameScene, Scene> Show = null,
        string Typed = null, Verb Picker = Verb.None);

    private static readonly Shot[] Shots =
    [
        new("01-title", a => true, (g, a, s) => new TitleScene(g)),
        new("02-beach", a => a.Moves >= 2),
        new("03-tower", a => a.LocationId == "tower_in" && a.Facing == Dir.East && a.Alive(Noun.Spider), Typed: "LANCE MAS"),
        new("04-hut", a => a.LocationId == "hut_in" && a.DrawerOpen),
        new("05-plant", a => a.LocationId == "clearing" && a.Alive(Noun.Plant), Picker: Verb.Cut),
        new("06-palm", a => a.UpPalm),
        new("07-cobra", a => a.LocationId == "narrow" && a.Alive(Noun.Cobra), Typed: "LANCE COUT"),
        new("08-crater", a => a.TorchLit),
        new("09-trapdoor", a => a.TrapOpen),
        new("10-part2", a => a.LocationId == "entry", (g, a, s) => new PartTwoScene(g, a)),
        new("11-buddha", a => a.SecretOpen && a.LocationId == "buddha"),
        new("12-well", a => a.BucketFull),
        new("13-gorilla", a => a.LocationId == "gorilla" && a.Alive(Noun.Gorilla) && a.Facing == Dir.North),
        new("14-sage", a => a.SageAsked),
        new("15-dragon", a => a.LocationId == "dragon" && a.Alive(Noun.Dragon), Typed: "DECAPITE DRA"),
        new("16-diamond", a => a.LocationId == "diamond_room"),
        new("17-hangar", a => a.HangarOpen && a.Facing == Dir.North),
        new("18-victory", a => a.Ended, (g, a, s) => new EndScene(g, a)),
        new("19-menu", a => true, (g, a, s) => new MenuScene(g)),
        new("20-instructions", a => true, (g, a, s) => new InstructionsScene(g)),
    ];

    private readonly string _folder;
    private VideoDirector _video;
    private bool _videoMode;
    private IEnumerator<Command> _walk;
    private Adventure _adventure;
    private GameScene _game;
    private int _shot;
    private int _frames;
    private bool _save;

    private CaptureDirector(string folder)
    {
        _folder = folder;
    }

    public bool Mobile { get; private set; }
    public Language? Language { get; private set; }
    public float Scale { get; private set; } = 10f;

    public static CaptureDirector FromArgs(string[] args)
    {
        int i = Array.IndexOf(args, "--capture");
        if (i < 0 || i + 1 >= args.Length)
            return null;
        var d = new CaptureDirector(args[i + 1]);
        for (int k = 0; k < args.Length; k++)
        {
            if (args[k] == "--mobile")
                d.Mobile = true;
            else if (args[k] == "--video")
                d._videoMode = true;
            else if (args[k] == "--lang" && k + 1 < args.Length)
                d.Language = Strings.FromIso(args[k + 1]);
            else if (args[k] == "--scale" && k + 1 < args.Length && float.TryParse(args[k + 1],
                         System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float s))
                d.Scale = Math.Clamp(s, 1f, 16f);
        }
        return d;
    }

    public void Update(DiamondGame game)
    {
        if (_videoMode)
        {
            Strings.Current = Language ?? Strings.Current;
            _video ??= new VideoDirector(_folder, Mobile);
            _video.Update(game);
            return;
        }
        if (_adventure == null)
        {
            Strings.Current = Language ?? Strings.Current;
            _adventure = new Adventure();
            _walk = Walkthrough.All.GetEnumerator();
            _game = new GameScene(game, _adventure, true);
            _game.Enter();
        }
        if (_shot >= Shots.Length)
        {
            game.Exit();
            return;
        }

        var shot = Shots[_shot];
        if (_frames == 0)
        {
            // Play on until the moment of this shot.
            while (!shot.When(_adventure) && _walk.MoveNext())
                _game.Feed(_walk.Current);
            _game.SetInput(shot.Typed == null ? null : Typed(shot.Typed));
            _game.OpenPicker(shot.Picker);
            var scene = shot.Show?.Invoke(game, _adventure, _game) ?? _game;
            if (scene != _game)
                scene.Enter();
            game.ShowCaptureScene(scene);
        }
        game.CurrentCaptureScene?.Tick();
        _frames++;
        _save = _frames == 30;
        if (_frames > 30)
        {
            _frames = 0;
            _shot++;
            _game.SetInput(null);
            _game.OpenPicker(Verb.None);
        }
    }

    /// <summary>The French example typed in the short form, in the capture's language.</summary>
    private static string Typed(string french)
    {
        if (Strings.Current == Localization.Language.French)
            return french;
        return french switch
        {
            "LANCE MAS" => "THROW CLU",
            "LANCE COUT" => "THROW KNI",
            "DECAPITE DRA" => "BEHEAD DRA",
            _ => french,
        };
    }

    public void AfterDraw(RenderTarget2D target)
    {
        if (_videoMode)
        {
            _video?.AfterDraw(target);
            return;
        }
        if (!_save)
            return;
        _save = false;
        string dir = Path.Combine(_folder, "stills");
        Directory.CreateDirectory(dir);
        using var stream = File.Create(Path.Combine(dir, Shots[_shot].Name + ".png"));
        target.SaveAsPng(stream, target.Width, target.Height);
    }
}
