using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Xna.Framework.Graphics;
using Diamond.Core.Audio;
using Diamond.Core.Engine;
using Diamond.Core.Localization;
using Diamond.Core.Scenes;
using Diamond.Core.World;

namespace Diamond.Core.Demo;

/// <summary>
/// App preview video: plays the highlights of the walkthrough on autopilot, at exactly 30 frames a
/// second, and writes every frame (frames/00000.jpg...) plus a soundtrack (audio.wav: the Toccata
/// and the game's sound effects at the moments they happen). tools/make_preview_videos.sh encodes
/// them for the App Store and Mac App Store. Orders are typed in the desktop layout and picked from
/// the WORDS list in the touch layout. About 28 seconds (Apple allows 15 to 30).
/// </summary>
internal sealed class VideoDirector
{
    public const int Fps = 30;

    /// <summary>The orders shown being given, in walkthrough order (everything between them is played off camera).</summary>
    private static readonly Command[] Highlights =
    [
        new(Verb.Throw, Noun.Club),
        new(Verb.Climb, Noun.Palm),
        new(Verb.Throw, Noun.Knife),
        new(Verb.Light, Noun.Torch),
        new(Verb.Press, Noun.Eye),
        new(Verb.Throw, Noun.Sabre),
        new(Verb.Behead, Noun.Dragon),
        new(Verb.Fly),
    ];

    private readonly string _folder;
    private readonly bool _mobile;
    private readonly Recorder _recorder = new();
    private IEnumerator<Scene> _script;
    private Scene _scene;
    private int _frame;
    private float _tickDebt;
    private bool _save;

    public VideoDirector(string folder, bool mobile)
    {
        _folder = folder;
        _mobile = mobile;
    }

    /// <summary>Records which sound plays on which frame.</summary>
    private sealed class Recorder : ISoundPlayer
    {
        public bool Enabled { get; set; } = true;
        public int Frame { get; set; }
        public List<(int frame, Sfx sfx)> Played { get; } = new();

        public void Play(Sfx sfx, float pitch = 0f)
        {
            if (Enabled)
                Played.Add((Frame, sfx));
        }
    }

    public void Update(DiamondGame game)
    {
        _script ??= Script(game).GetEnumerator();
        _recorder.Frame = _frame;
        if (!_script.MoveNext())
        {
            WriteAudio();
            game.Exit();
            return;
        }
        var scene = _script.Current;
        if (scene != _scene)
        {
            _scene = scene;
            game.ShowCaptureScene(scene);
            _tickDebt = 0;
        }
        // The game runs at 50 ticks a second; the video at 30 frames.
        for (_tickDebt += (float)DiamondGame.TicksPerSecond / Fps; _tickDebt >= 1; _tickDebt--)
            scene.Tick();
        _save = true;
    }

    public void AfterDraw(RenderTarget2D target)
    {
        if (!_save)
            return;
        _save = false;
        string dir = Path.Combine(_folder, "frames");
        Directory.CreateDirectory(dir);
        using (var stream = File.Create(Path.Combine(dir, $"{_frame:D5}.jpg")))
            target.SaveAsJpeg(stream, target.Width, target.Height);
        _frame++;
    }

    /// <summary>The video, one yield per frame (the scene to show on that frame).</summary>
    private IEnumerable<Scene> Script(DiamondGame game)
    {
        var language = Strings.Current;
        var title = new TitleScene(game);
        for (int i = 0; i < 75; i++)
            yield return title;
        _recorder.Played.Add((0, Sfx.Start));

        var a = new Adventure(_recorder);
        var play = new GameScene(game, a, true);
        _recorder.Enabled = false;
        play.Enter();
        var walk = Walkthrough.All.ToList();
        int next = 0;

        foreach (var highlight in Highlights)
        {
            // Off camera up to the highlight (showing the interlude when part two begins).
            _recorder.Enabled = false;
            while (next < walk.Count && walk[next] != highlight)
            {
                var part = a.Part;
                play.Feed(walk[next++]);
                if (part == Part.Island && a.Part == Part.Underground)
                {
                    var interlude = new PartTwoScene(game, a);
                    _recorder.Enabled = true;
                    _recorder.Played.Add((_frame, Sfx.Magic));
                    for (int i = 0; i < 50; i++)
                        yield return interlude;
                    _recorder.Enabled = false;
                }
            }
            if (next >= walk.Count)
                yield break;

            for (int i = 0; i < 14; i++)
                yield return play;

            // The order being given: typed on a desktop, picked from the word list on a phone.
            _recorder.Enabled = true;
            if (_mobile)
            {
                play.PickerDemo(false, highlight.Verb, Noun.None);
                for (int i = 0; i < 14; i++)
                    yield return play;
                if (highlight.Noun != Noun.None)
                {
                    play.PickerDemo(true, highlight.Verb, highlight.Noun);
                    for (int i = 0; i < 14; i++)
                        yield return play;
                }
                play.OpenPicker(Verb.None);
            }
            else
            {
                string text = Parser.Format(language, highlight);
                for (int k = 1; k <= text.Length; k++)
                {
                    play.SetInput(text[..k]);
                    _recorder.Played.Add((_frame, Sfx.Key));
                    yield return play;
                    if (k % 2 == 0)
                        yield return play;
                }
                for (int i = 0; i < 6; i++)
                    yield return play;
                play.SetInput(null);
            }

            play.Feed(walk[next++]);
            for (int i = 0; i < (a.Ended ? 20 : 42); i++)
                yield return play;
        }

        var end = new EndScene(game, a);
        _recorder.Played.Add((_frame, Sfx.Victory));
        for (int i = 0; i < 90; i++)
            yield return end;
    }

    /// <summary>audio.wav: the Toccata from the start, and every sound effect on its frame.</summary>
    private void WriteAudio()
    {
        int rate = Synth.SampleRate;
        int length = (int)((long)_frame * rate / Fps);
        var mix = new int[length];
        void Add(short[] clip, int at, float gain)
        {
            for (int i = 0; i < clip.Length && at + i < length; i++)
                if (at + i >= 0)
                    mix[at + i] += (int)(clip[i] * gain);
        }
        Add(SoundBank.TitleTune(), 0, 0.8f);
        var effects = SoundBank.Build().ToDictionary(e => e.Item1, e => e.Item2);
        foreach (var (frame, sfx) in _recorder.Played)
            if (effects.TryGetValue(sfx, out var clip))
                Add(clip, (int)((long)frame * rate / Fps), sfx == Sfx.Key ? 0.5f : 0.9f);

        var pcm = mix.Select(v => (short)Math.Clamp(v, short.MinValue, short.MaxValue)).ToArray();
        var data = Synth.ToBytes(pcm);
        using var w = new BinaryWriter(File.Create(Path.Combine(_folder, "audio.wav")));
        w.Write("RIFF"u8);
        w.Write(36 + data.Length);
        w.Write("WAVEfmt "u8);
        w.Write(16);
        w.Write((short)1);
        w.Write((short)1);
        w.Write(rate);
        w.Write(rate * 2);
        w.Write((short)2);
        w.Write((short)16);
        w.Write("data"u8);
        w.Write(data.Length);
        w.Write(data);
    }
}
