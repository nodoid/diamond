using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;
using Diamond.Core.Oric;

namespace Diamond.Core.Scenes;

/// <summary>Shared drawing for the screens: buttons, panels, wrapped text and the backdrop picture.</summary>
public static class Ui
{
    public static readonly Color Gold = new(255, 214, 90);
    public static readonly Color Sky = new(150, 220, 255);
    public static readonly Color Leaf = new(170, 230, 170);
    public static readonly Color Panel = new(10, 18, 40);

    /// <summary>A full-screen picture, optionally darkened.</summary>
    public static void Backdrop(Canvas c, string picture, float darken = 0f)
    {
        if (!c.DrawArt("bg_" + picture, new RectF(0, 0, Canvas.Width, Canvas.Height)))
            c.Fill(0, 0, Canvas.Width, Canvas.Height, new Color(6, 10, 30));
        if (darken > 0)
            c.Fill(0, 0, Canvas.Width, Canvas.Height, Color.Black * darken);
    }

    /// <summary>A bevelled button with centred text; <paramref name="hot"/> highlights it.</summary>
    public static void Button(Canvas c, RectF r, string text, bool hot, bool enabled = true)
    {
        var top = enabled ? (hot ? new Color(250, 205, 90) : new Color(40, 70, 130)) : new Color(40, 40, 50);
        var bottom = enabled ? (hot ? new Color(190, 130, 40) : new Color(18, 30, 70)) : new Color(25, 25, 32);
        for (int i = 0; i < 4; i++)
        {
            float y0 = r.Y + r.H * i / 4f, h = r.H / 4f + 0.2f;
            c.Fill(r.X, y0, r.W, h, Color.Lerp(top, bottom, i / 3f));
        }
        c.Frame(r.X, r.Y, r.W, r.H, enabled ? new Color(120, 170, 255) * 0.8f : new Color(70, 70, 80), 0.5f);
        var ink = enabled ? (hot ? new Color(30, 20, 60) : Color.White) : new Color(110, 110, 120);
        c.Text(r.X + (r.W - Canvas.TextWidth(text)) / 2, r.Y + (r.H - 7) / 2, text, ink);
    }

    /// <summary>A left-pointing (-1), up (0, forward), down (2) or right (1) arrow button.</summary>
    public static void ArrowButton(Canvas c, RectF r, int direction, bool hot)
    {
        Button(c, r, string.Empty, hot);
        float cx = r.X + r.W / 2, cy = r.Y + r.H / 2, s = Math.Min(r.W, r.H) * 0.3f;
        Vector2[] pts = direction switch
        {
            -1 => [new(cx - s, cy), new(cx + s * 0.7f, cy - s), new(cx + s * 0.7f, cy + s)],
            1 => [new(cx + s, cy), new(cx - s * 0.7f, cy + s), new(cx - s * 0.7f, cy - s)],
            0 => [new(cx, cy - s), new(cx + s, cy + s * 0.7f), new(cx - s, cy + s * 0.7f)],
            _ => [new(cx, cy + s), new(cx - s, cy - s * 0.7f), new(cx + s, cy - s * 0.7f)],
        };
        c.FillPolygon(pts, hot ? new Color(30, 20, 60) : Color.White);
    }

    public static void Header(Canvas c, float y, string text, Color color)
    {
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(text)) / 2, y, text, color);
        float w = Canvas.TextWidth(text);
        c.Fill((Canvas.Width - w) / 2, y + 9, w, 0.6f, color * 0.8f);
    }

    /// <summary>Draws wrapped text; returns the y after the last line.</summary>
    public static float Paragraphs(Canvas c, string text, float x, float y, int columns, Color color, float lineHeight = 9f)
    {
        foreach (var line in Strings.Wrap(text, columns))
        {
            c.TextShadowed(x, y, line, color);
            y += lineHeight;
        }
        return y;
    }

    public static void Blink(Canvas c, int ticks, float y, string text)
    {
        float pulse = 0.6f + 0.4f * MathF.Sin(ticks * 0.12f);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(text)) / 2, y, text, Color.Lerp(Gold, Color.White, pulse));
    }

    public static bool Hit(RectF r, IReadOnlyList<Vector2> taps)
    {
        foreach (var t in taps)
            if (r.Inflate(1).Contains(t))
                return true;
        return false;
    }
}
