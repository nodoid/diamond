using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.Xna.Framework.Audio;

namespace Diamond.Core.Audio;

/// <summary>Builds every sound effect at start-up from <see cref="Synth"/> and plays them.</summary>
public sealed class SoundBank : ISoundPlayer, IDisposable
{
    private readonly Dictionary<Sfx, SoundEffect> _effects = new();
    private readonly bool _enabled;
    private static readonly float[] VolumeSteps = [0.6f, 0.3f, 0f, 1f];
    private SoundEffect _tune;
    private SoundEffectInstance _tuneInstance;
    private int _volumeIndex;

    public SoundBank()
    {
        try
        {
            foreach (var (id, pcm) in Build())
                _effects[id] = new SoundEffect(Synth.ToBytes(pcm), Synth.SampleRate, AudioChannels.Mono);
            _tune = new SoundEffect(Synth.ToBytes(TitleTune()), Synth.SampleRate, AudioChannels.Mono);
            _enabled = true;
        }
        catch (Exception)
        {
            // No audio device (e.g. headless CI): run silently.
            _enabled = false;
        }
    }

    /// <summary>Silences everything without changing the volume setting (store captures).</summary>
    public bool Muted { get; set; }

    public float Volume => VolumeSteps[_volumeIndex];

    /// <summary>0 off, 1 low, 2 medium, 3 high.</summary>
    public int Level => Volume <= 0f ? 0 : Volume < 0.5f ? 1 : Volume < 0.9f ? 2 : 3;

    /// <summary>Cycles the volume. Returns the new level 0..3 (0 = mute).</summary>
    public int CycleVolume()
    {
        _volumeIndex = (_volumeIndex + 1) % VolumeSteps.Length;
        Play(Sfx.Menu);
        return (int)Math.Round(Volume * 3);
    }

    public void Play(Sfx sfx, float pitch = 0f)
    {
        if (!_enabled || Muted || Volume <= 0f)
            return;
        if (_effects.TryGetValue(sfx, out var e))
        {
            try
            {
                e.Play(Volume, Math.Clamp(pitch, -1f, 1f), 0f);
            }
            catch (Exception)
            {
            }
        }
    }

    internal static IEnumerable<(Sfx, short[])> Build()
    {
        yield return (Sfx.Step, Synth.Noise(0.03, 0.25, 0, 14));
        yield return (Sfx.Bump, Synth.Mix(Synth.Noise(0.08, 0.4, 0, 30), Synth.Sweep(0.08, 120, 70, 0.3, 0)));
        yield return (Sfx.Take, Synth.Tune(0.4, (784, 0.05), (1047, 0.08)));
        yield return (Sfx.Drop, Synth.Tune(0.35, (523, 0.05), (392, 0.08)));
        yield return (Sfx.Door, Synth.Mix(Synth.Sweep(0.35, 140, 90, 0.35, 0.1), Synth.Noise(0.35, 0.2, 0, 20)));
        yield return (Sfx.Locked, Synth.Tune(0.35, (196, 0.08), (0, 0.04), (196, 0.12)));
        yield return (Sfx.Climb, Synth.Concat(Synth.Noise(0.05, 0.3, 0, 10), Synth.Silence(0.06),
            Synth.Noise(0.05, 0.3, 0, 10), Synth.Silence(0.06), Synth.Noise(0.05, 0.3, 0, 10)));
        yield return (Sfx.Hurt, Synth.Mix(Synth.Noise(0.2, 0.5, 0, 3), Synth.Sweep(0.2, 300, 120, 0.3, 0)));
        yield return (Sfx.Hit, Synth.Mix(Synth.Noise(0.15, 0.7, 0, 5), Synth.Sweep(0.15, 220, 60, 0.4, 0)));
        yield return (Sfx.Hiss, Synth.Noise(0.6, 0.35, 0.05, 1));
        yield return (Sfx.Roar, Synth.Mix(Synth.Noise(0.8, 0.5, 0.1, 40), Synth.Sweep(0.8, 90, 50, 0.4, 0.1)));
        yield return (Sfx.Ghost, Synth.Concat(Synth.Sweep(0.4, 300, 600, 0.25, 0.25), Synth.Sweep(0.4, 600, 250, 0.25, 0)));
        yield return (Sfx.Drink, Synth.Concat(Synth.Sweep(0.08, 400, 800, 0.3, 0.3), Synth.Sweep(0.08, 400, 900, 0.3, 0.3),
            Synth.Tune(0.35, (1047, 0.08), (1319, 0.16))));
        yield return (Sfx.Eat, Synth.Concat(Synth.Noise(0.06, 0.4, 0, 6), Synth.Silence(0.06), Synth.Noise(0.06, 0.4, 0, 6)));
        yield return (Sfx.Splash, Synth.Concat(Synth.Sweep(0.1, 900, 300, 0.3, 0.1), Synth.Noise(0.4, 0.4, 0, 2)));
        yield return (Sfx.Dig, Synth.Concat(Synth.Noise(0.08, 0.5, 0, 8), Synth.Silence(0.1), Synth.Noise(0.08, 0.5, 0, 8),
            Synth.Silence(0.1), Synth.Noise(0.12, 0.5, 0, 8)));
        yield return (Sfx.Fire, Synth.Mix(Synth.Noise(0.7, 0.45, 0.05, 2), Synth.Sweep(0.7, 80, 160, 0.2, 0)));
        yield return (Sfx.Engine, Synth.Mix(Synth.Sweep(1.2, 40, 90, 0.4, 0.3), Synth.Noise(1.2, 0.25, 0.2, 60)));
        yield return (Sfx.Explosion, Synth.Concat(Synth.Noise(0.9, 0.9, 0, 12), Synth.Noise(0.4, 0.3, 0, 30)));
        yield return (Sfx.Magic, Synth.Tune(0.35, (1319, 0.06), (1568, 0.06), (1976, 0.06), (2637, 0.06), (1976, 0.06), (2637, 0.2)));
        yield return (Sfx.Treasure, Synth.Tune(0.4, (1047, 0.06), (1319, 0.06), (1568, 0.06), (2093, 0.18)));
        yield return (Sfx.Victory, Synth.Tune(0.45, (392, 0.15), (523, 0.15), (659, 0.15), (784, 0.3), (659, 0.15),
            (784, 0.15), (1047, 0.6)));
        yield return (Sfx.Death, Synth.Tune(0.4, (392, 0.25), (370, 0.25), (349, 0.25), (330, 0.6)));
        yield return (Sfx.Menu, Synth.Sweep(0.05, 900, 1200, 0.3, 0.1));
        yield return (Sfx.Start, Synth.Tune(0.4, (294, 0.12), (349, 0.12), (440, 0.12), (587, 0.3)));
        yield return (Sfx.Warning, Synth.Tune(0.35, (880, 0.08), (0, 0.06), (880, 0.08)));
        yield return (Sfx.Key, Synth.Noise(0.012, 0.25, 0, 3));
        yield return (Sfx.Beep, Synth.Tune(0.4, (1200, 0.12)));
    }

    /// <summary>
    /// The title music: the opening of Bach's Toccata in D minor, as the 1984 original played it on the
    /// Oric's sound chip (the melody doubled an octave down, like an organ).
    /// </summary>
    internal static short[] TitleTune()
    {
        const double A5 = 880, G5 = 784, F5 = 698.46, E5 = 659.26, D5 = 587.33, Cs5 = 554.37;
        const double A4 = 440, G4 = 392, F4 = 349.23, E4 = 329.63, D4 = 293.66, Cs4 = 277.18;
        const double A3 = 220, G3 = 196, F3 = 174.61, E3 = 164.81, D3 = 146.83, Cs3 = 138.59;
        const double s = 0.09, q = 0.36;
        var melody = new (double, double)[]
        {
            (A5, s), (G5, s), (A5, q * 3), (0, q),
            (G5, s), (F5, s), (E5, s), (D5, s), (Cs5, q), (D5, q * 3), (0, q * 2),
            (A4, s), (G4, s), (A4, q * 3), (0, q),
            (E4, q), (F4, q), (Cs4, q), (D4, q * 3), (0, q * 2),
            (A3, s), (G3, s), (A3, q * 3), (0, q),
            (G3, s), (F3, s), (E3, s), (D3, s), (Cs3, q), (D3, q * 4),
        };
        var low = melody.Select(n => (n.Item1 / 2, n.Item2)).ToArray();
        // The rolling diminished chord that follows, then the final D minor.
        var roll = new List<(double, double)>();
        foreach (var f in new[] { Cs4, E4, G4, A4, Cs5, E5, G5, A5 })
            roll.Add((f, 0.07));
        roll.Add((0, 0.1));
        foreach (var f in new[] { D4, F4, A4, D5, F5, A5 })
            roll.Add((f, 0.08));
        roll.Add((D5, q * 4));
        return Synth.Concat(Synth.Mix(Synth.Tune(0.3, melody), Synth.Tune(0.18, low)), Synth.Tune(0.28, roll.ToArray()));
    }

    /// <summary>Plays the title tune once (restarting it if it is already playing).</summary>
    public void PlayTune()
    {
        if (!_enabled || Muted || Volume <= 0f || _tune == null)
            return;
        try
        {
            _tuneInstance?.Stop();
            _tuneInstance ??= _tune.CreateInstance();
            _tuneInstance.Volume = Volume;
            _tuneInstance.Play();
        }
        catch (Exception)
        {
        }
    }

    public void StopTune()
    {
        try
        {
            _tuneInstance?.Stop();
        }
        catch (Exception)
        {
        }
    }

    public void Dispose()
    {
        _tuneInstance?.Dispose();
        _tune?.Dispose();
        foreach (var e in _effects.Values)
            e.Dispose();
        _effects.Clear();
    }
}
