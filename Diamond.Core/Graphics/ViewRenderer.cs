using System;
using System.Linq;
using Microsoft.Xna.Framework;
using Diamond.Core.Engine;
using Diamond.Core.World;

namespace Diamond.Core.Graphics;

/// <summary>
/// Paints what the explorer sees: the painted view for the place and direction, then every object,
/// creature and feature standing in it, lit by daylight, the torch, the lava or the crystals.
/// </summary>
public static class ViewRenderer
{
    /// <summary>The picture window at the top of the screen.</summary>
    public static readonly RectF Window = new(0, 0, Canvas.Width, 136);

    public static void Draw(Canvas c, Adventure a, int ticks, RectF? into = null)
    {
        var r = into ?? Window;
        float sx = r.W / Window.W, sy = r.H / Window.H;
        RectF Map(float x, float y, float w, float h) => new(r.X + x * sx, r.Y + y * sy, w * sx, h * sy);

        if (!a.CanSee)
        {
            DrawDark(c, r, ticks);
            return;
        }

        var view = a.CurrentView;
        if (!c.DrawArt("bg_" + view.Background, r, null, view.Mirror))
            c.Fill(r.X, r.Y, r.W, r.H, new Color(20, 30, 40));

        var loc = a.Location;
        bool underground = loc.Part == Part.Underground || a.LocationId == "cellar";
        Color tint = Color.White;
        if (a.LocationId == "lit")
            tint = new Color(190, 255, 210);
        else if (underground && loc.Dark)
        {
            float flicker = 0.92f + 0.08f * MathF.Sin(ticks * 0.37f) * MathF.Sin(ticks * 0.13f + 1);
            tint = new Color(255 * flicker / 255f, 214 * flicker / 255f, 170 * flicker / 255f);
        }

        // Scorpions scuttle among the hot rocks.
        if (loc.Scorpions && !a.UpPalm)
        {
            int seed = a.LocationId.Length * 7 + (int)a.Facing * 13;
            for (int i = 0; i < 2; i++)
            {
                float x = 30 + (seed * 37 + i * 97) % 180;
                float wiggle = MathF.Sin(ticks * 0.2f + i * 2) * 1.5f;
                var p = Map(x + wiggle, 131 - i * 6, 0, 0);
                c.DrawStanding("scorpion", p.X, p.Y, 6 * sy, null, i == 1);
            }
        }

        foreach (var t in a.Visible().OrderBy(t => t.Place.Y))
            DrawThing(c, a, t, ticks, Map, sy, tint);

        // The bucket hangs from the well's pulley.
        if (a.LocationId == "well" && a.Facing == Dir.North && a.BucketTied && !a.BucketDown)
        {
            var p = Map(146, 104, 0, 0);
            c.DrawStanding(a.BucketFull ? "bucket_full" : "bucket", p.X, p.Y, 13 * sy, tint);
        }

        // Lighting.
        if (a.LocationId == "crater" && a.Facing == Dir.North)
            c.Glow(r.X + r.W / 2, r.Bottom - 20 * sy, 90 * sx, new Color(255, 120, 30) * (0.18f + 0.05f * MathF.Sin(ticks * 0.1f)));
        if (underground && loc.Dark)
        {
            float flick = MathF.Sin(ticks * 0.31f) * 2 + MathF.Sin(ticks * 0.77f);
            c.Vignette(r, 0.82f, r.X + r.W / 2, r.Y + r.H * 0.62f, (120 + flick) * sx);
            c.Glow(r.X + r.W / 2, r.Bottom, 70 * sx, new Color(255, 150, 60) * 0.10f);
        }
    }

    private static void DrawThing(Canvas c, Adventure a, ThingState t, int ticks, Func<float, float, float, float, RectF> map,
        float sy, Color tint)
    {
        string sprite = a.SpriteFor(t);
        float x = t.Place.X, y = t.Place.Y;
        float h = t.Place.Height > 0 ? t.Place.Height : t.Def.Height;
        var color = tint;
        bool mirror = false;

        switch (t.Noun)
        {
            case Noun.Inscription:
                DrawInscription(c, map, sy);
                return;
            case Noun.Buddha when a.SecretOpen:
                x = 62;
                break;
            case Noun.Ghost:
                y += MathF.Sin(ticks * 0.08f) * 3;
                x += MathF.Sin(ticks * 0.05f) * 4;
                color = tint * (0.7f + 0.2f * MathF.Sin(ticks * 0.11f));
                break;
            case Noun.Cobra when a.Alive(Noun.Cobra):
                x += MathF.Sin(ticks * 0.09f) * 1.2f;
                break;
            case Noun.Torch when a.TorchLit:
                h = 20;
                break;
            case Noun.Spider when a.Alive(Noun.Spider):
                y += MathF.Sin(ticks * 0.05f) * 0.6f;
                break;
            case Noun.Dragon when a.Alive(Noun.Dragon):
                y += MathF.Sin(ticks * 0.06f) * 0.8f;
                break;
            case Noun.Dragon:
            case Noun.Spider:
            case Noun.Cobra:
                h = sprite switch { "dragon_dead" => 30, "spider_dead" => 8, "cobra_dead" => 6, _ => h };
                break;
            case Noun.Plant when !a.Alive(Noun.Plant):
                h = 18;
                break;
            case Noun.Trapdoor when a.TrapOpen:
                h = 22;
                break;
        }

        var p = map(x, y, 0, 0);
        var rect = c.DrawStanding(sprite, p.X, p.Y, h * sy, color, mirror);
        if (rect.W <= 0)
        {
            // Missing artwork: a placeholder box keeps the game playable.
            c.Fill(p.X - h * sy / 3, p.Y - h * sy, h * sy * 2 / 3, h * sy, Color.Magenta * 0.5f);
            return;
        }

        if (t.Noun == Noun.Diamond)
        {
            float pulse = 0.5f + 0.5f * MathF.Sin(ticks * 0.15f);
            c.Glow(rect.X + rect.W / 2, rect.Y + rect.H / 2, 18 * sy, new Color(200, 230, 255) * (0.25f + 0.25f * pulse));
        }
        if (t.Noun == Noun.Torch && a.TorchLit)
            c.Glow(rect.X + rect.W / 2, rect.Y + 2 * sy, 22 * sy, new Color(255, 170, 60) * (0.30f + 0.08f * MathF.Sin(ticks * 0.5f)));
        if (t.Noun == Noun.Dragon && a.Alive(Noun.Dragon))
            c.Glow(rect.X + rect.W * 0.3f, rect.Y + rect.H * 0.25f, 14 * sy, new Color(255, 80, 20) * (0.15f + 0.1f * MathF.Sin(ticks * 0.2f)));
    }

    /// <summary>The carved warning in the collapsed gallery: rows of strange signs.</summary>
    private static void DrawInscription(Canvas c, Func<float, float, float, float, RectF> map, float sy)
    {
        var rnd = new Random(1984);
        var ink = new Color(40, 25, 15) * 0.85f;
        var light = new Color(255, 220, 170) * 0.35f;
        for (int row = 0; row < 4; row++)
        {
            for (int i = 0; i < 9; i++)
            {
                var o = map(84 + i * 8, 72 + row * 9, 0, 0);
                float s = 3 * sy;
                for (int k = 0; k < 3; k++)
                {
                    var a0 = new Vector2(o.X + (float)rnd.NextDouble() * s * 2, o.Y + (float)rnd.NextDouble() * s * 2);
                    var a1 = new Vector2(o.X + (float)rnd.NextDouble() * s * 2, o.Y + (float)rnd.NextDouble() * s * 2);
                    var shift = new Vector2(0.3f * sy, 0.3f * sy);
                    c.Line(a0 + shift, a1 + shift, light, 0.8f);
                    c.Line(a0, a1, ink, 0.5f);
                }
            }
        }
    }

    private static void DrawDark(Canvas c, RectF r, int ticks)
    {
        c.Fill(r.X, r.Y, r.W, r.H, Color.Black);
        // Two eyes in the dark, now and then.
        if (ticks / 90 % 3 == 1)
        {
            float x = r.X + r.W * 0.62f, y = r.Y + r.H * 0.45f;
            c.Glow(x, y, 3, new Color(255, 230, 120) * 0.5f);
            c.Glow(x + 8, y, 3, new Color(255, 230, 120) * 0.5f);
        }
    }
}
