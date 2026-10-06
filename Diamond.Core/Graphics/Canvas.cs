using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Diamond.Core.Oric;

namespace Diamond.Core.Graphics;

/// <summary>A rectangle in (fractional) virtual pixels.</summary>
public readonly record struct RectF(float X, float Y, float W, float H)
{
    public float Right => X + W;
    public float Bottom => Y + H;
    public bool Contains(float x, float y) => x >= X && x < Right && y >= Y && y < Bottom;
    public bool Contains(Vector2 p) => Contains(p.X, p.Y);
    public RectF Inflate(float by) => new(X - by, Y - by, W + by * 2, H + by * 2);
    public static implicit operator RectF(Rectangle r) => new(r.X, r.Y, r.Width, r.Height);
}

/// <summary>
/// Draws the game at high resolution. Layout uses a 240x224 virtual screen (the Oric's, so the
/// screens keep its proportions and text grid), but everything is rendered at the full device
/// resolution: the pictures are high-resolution paintings (Art/), shapes are filled per device pixel
/// row with smooth shading, and the ROM font is enlarged with the Scale2x edge-smoothing filter and
/// drawn with linear filtering, so nothing looks blocky.
/// </summary>
public sealed class Canvas : IDisposable
{
    public const int Width = 240;
    public const int Height = 224;
    public const int Columns = Width / OricFont.GlyphWidth;   // 40
    public const int Rows = Height / OricFont.GlyphHeight;    // 28

    /// <summary>Font glyphs are smoothed to this many texels per pixel (Scale2x twice).</summary>
    public const int FontDetail = 4;

    private readonly GraphicsDevice _device;
    private readonly SpriteBatch _batch;
    private readonly Texture2D _pixel;
    private readonly Texture2D _ramp;
    private readonly Texture2D _shadow;
    private readonly Texture2D _glow;
    private readonly Texture2D _font;
    private readonly Texture2D _hole;

    public Canvas(GraphicsDevice device)
    {
        _device = device;
        _batch = new SpriteBatch(device);
        _pixel = new Texture2D(device, 1, 1);
        _pixel.SetData([Color.White]);
        _ramp = BuildRamp(device);
        _shadow = BuildRadial(device, 64, 32, 0.55f);
        _glow = BuildRadial(device, 64, 64, 1f);
        _font = BuildFont(device);
        _hole = BuildHole(device, 128);
    }

    /// <summary>Device pixels per virtual pixel for the frame being drawn.</summary>
    public float Scale { get; private set; } = 1f;

    private int DeviceWidth => (int)MathF.Round(Width * Scale);
    private int DeviceHeight => (int)MathF.Round(Height * Scale);

    public void Begin(float scale)
    {
        Scale = scale;
        _batch.Begin(SpriteSortMode.Deferred, BlendState.AlphaBlend, SamplerState.LinearClamp);
    }

    public void End() => _batch.End();

    // ---------------------------------------------------------------- rectangles and lines

    public void Fill(float x, float y, float w, float h, Color color)
    {
        if (w <= 0 || h <= 0)
            return;
        _batch.Draw(_pixel, new Vector2(x * Scale, y * Scale), null, color, 0f, Vector2.Zero,
            new Vector2(w * Scale, h * Scale), SpriteEffects.None, 0f);
    }

    public void Fill(float x, float y, float w, float h, OricColor color) => Fill(x, y, w, h, color.ToColor());

    public void Plot(float x, float y, OricColor color) => Fill(x, y, 1, 1, color);

    /// <summary>Outline of a rectangle.</summary>
    public void Frame(float x, float y, float w, float h, Color color, float thickness = 1f)
    {
        Fill(x, y, w, thickness, color);
        Fill(x, y + h - thickness, w, thickness, color);
        Fill(x, y, thickness, h, color);
        Fill(x + w - thickness, y, thickness, h, color);
    }

    public void Frame(float x, float y, float w, float h, OricColor color, float thickness = 1f) =>
        Frame(x, y, w, h, color.ToColor(), thickness);

    /// <summary>A thin line (width in virtual pixels; at least one device pixel).</summary>
    public void Line(Vector2 a, Vector2 b, Color color, float width = 0.6f)
    {
        var d = (b - a) * Scale;
        float length = d.Length();
        if (length < 0.01f)
            return;
        float w = MathF.Max(1f, width * Scale);
        float angle = MathF.Atan2(d.Y, d.X);
        _batch.Draw(_pixel, a * Scale, null, color, angle, new Vector2(0f, 0.5f), new Vector2(length, w),
            SpriteEffects.None, 0f);
    }

    public void Line(Vector2 a, Vector2 b, OricColor color, float width = 0.6f) => Line(a, b, color.ToColor(), width);

    public void Line(float x0, float y0, float x1, float y1, OricColor color, float width = 0.6f) =>
        Line(new Vector2(x0, y0), new Vector2(x1, y1), color.ToColor(), width);

    public void Outline(ReadOnlySpan<Vector2> points, Color color, float width = 0.6f)
    {
        for (int i = 0; i < points.Length; i++)
            Line(points[i], points[(i + 1) % points.Length], color, width);
    }

    // ---------------------------------------------------------------- polygons

    /// <summary>Fills a convex polygon, one device pixel row at a time.</summary>
    public void FillPolygon(ReadOnlySpan<Vector2> points, Color color)
    {
        foreach (var (y, x0, x1) in Geometry.Spans(points, Scale, DeviceWidth, DeviceHeight))
            _batch.Draw(_pixel, new Vector2(x0, y), null, color, 0f, Vector2.Zero, new Vector2(x1 - x0, 1f),
                SpriteEffects.None, 0f);
    }

    public void FillPolygon(ReadOnlySpan<Vector2> points, OricColor color) => FillPolygon(points, color.ToColor());

    /// <summary>
    /// Fills a convex polygon with smooth shading: <paramref name="brightness"/> gives the light
    /// (0 dark .. 1 full colour) at a virtual point, interpolated along each row.
    /// </summary>
    public void ShadePolygon(ReadOnlySpan<Vector2> points, Color color, Func<float, float, float> brightness)
    {
        foreach (var (y, x0, x1) in Geometry.Spans(points, Scale, DeviceWidth, DeviceHeight))
        {
            float vy = (y + 0.5f) / Scale;
            float b0 = Math.Clamp(brightness(x0 / Scale, vy), 0f, 1f);
            float b1 = Math.Clamp(brightness(x1 / Scale, vy), 0f, 1f);
            int u0 = (int)(b0 * 255), u1 = (int)(b1 * 255);
            var flip = SpriteEffects.None;
            if (u0 > u1)
            {
                (u0, u1) = (u1, u0);
                flip = SpriteEffects.FlipHorizontally;
            }
            var src = new Rectangle(u0, 0, Math.Max(1, u1 - u0), 1);
            _batch.Draw(_ramp, new Vector2(x0, y), src, color, 0f, Vector2.Zero,
                new Vector2((x1 - x0) / src.Width, 1f), flip, 0f);
        }
    }

    /// <summary>A soft dark ellipse on the floor under a figure.</summary>
    public void Shadow(float cx, float cy, float w, float h, float opacity = 0.6f)
    {
        _batch.Draw(_shadow, new Vector2((cx - w / 2) * Scale, (cy - h / 2) * Scale), null, Color.Black * opacity, 0f,
            Vector2.Zero, new Vector2(w * Scale / _shadow.Width, h * Scale / _shadow.Height), SpriteEffects.None, 0f);
    }

    /// <summary>A soft pool of light (torch flames, the lamp, magic).</summary>
    public void Glow(float cx, float cy, float radius, Color color)
    {
        _batch.Draw(_glow, new Vector2((cx - radius) * Scale, (cy - radius) * Scale), null, color, 0f, Vector2.Zero,
            new Vector2(radius * 2 * Scale / _glow.Width, radius * 2 * Scale / _glow.Height), SpriteEffects.None, 0f);
    }

    // ---------------------------------------------------------------- pictures

    /// <summary>
    /// Draws a picture (embedded Art/&lt;name&gt;.png or .jpg) stretched into a rectangle. Returns false
    /// when there is no such picture.
    /// </summary>
    public bool DrawArt(string name, RectF r, Color? tint = null, bool mirror = false)
    {
        var tex = Art(name);
        if (tex == null || r.W <= 0 || r.H <= 0)
            return tex != null;
        _batch.Draw(tex, new Vector2(r.X * Scale, r.Y * Scale), null, tint ?? Color.White, 0f, Vector2.Zero,
            new Vector2(r.W * Scale / tex.Width, r.H * Scale / tex.Height),
            mirror ? SpriteEffects.FlipHorizontally : SpriteEffects.None, 0f);
        return true;
    }

    /// <summary>Draws part of a picture (in picture pixels) into a rectangle.</summary>
    public void DrawArtPart(string name, Rectangle source, RectF r, Color? tint = null, bool mirror = false)
    {
        var tex = Art(name);
        if (tex == null || r.W <= 0 || r.H <= 0)
            return;
        _batch.Draw(tex, new Vector2(r.X * Scale, r.Y * Scale), source, tint ?? Color.White, 0f, Vector2.Zero,
            new Vector2(r.W * Scale / source.Width, r.H * Scale / source.Height),
            mirror ? SpriteEffects.FlipHorizontally : SpriteEffects.None, 0f);
    }

    /// <summary>Size in pixels of a picture, or null when missing.</summary>
    public Point? ArtSize(string name)
    {
        var tex = Art(name);
        return tex == null ? null : new Point(tex.Width, tex.Height);
    }

    /// <summary>Draws a sprite picture standing on (cx, groundY), <paramref name="height"/> virtual pixels tall.</summary>
    public RectF DrawStanding(string name, float cx, float groundY, float height, Color? tint = null, bool mirror = false)
    {
        var size = ArtSize(name);
        if (size == null)
            return default;
        float w = height * size.Value.X / size.Value.Y;
        var r = new RectF(cx - w / 2, groundY - height, w, height);
        DrawArt(name, r, tint, mirror);
        return r;
    }

    /// <summary>Darkens the edges of a rectangle (torch light falling off into the dark).</summary>
    public void Vignette(RectF r, float strength, float cx, float cy, float radius)
    {
        // Four dark bands around a soft hole: the radial texture is drawn inverted with a black fill.
        float x0 = (cx - radius), y0 = (cy - radius), d = radius * 2;
        _batch.Draw(_hole, new Vector2(x0 * Scale, y0 * Scale), null, Color.Black * strength, 0f, Vector2.Zero,
            new Vector2(d * Scale / _hole.Width, d * Scale / _hole.Height), SpriteEffects.None, 0f);
        Fill(r.X, r.Y, r.W, Math.Max(0, y0 - r.Y), Color.Black * strength);
        Fill(r.X, y0 + d, r.W, Math.Max(0, r.Bottom - y0 - d), Color.Black * strength);
        Fill(r.X, Math.Max(r.Y, y0), Math.Max(0, x0 - r.X), Math.Min(d, r.Bottom - y0), Color.Black * strength);
        Fill(x0 + d, Math.Max(r.Y, y0), Math.Max(0, r.Right - x0 - d), Math.Min(d, r.Bottom - y0), Color.Black * strength);
    }

    // ---------------------------------------------------------------- text

    /// <summary>Text at a virtual position in the (smoothed) Oric ROM font.</summary>
    public void Text(float x, float y, string text, Color ink, float scale = 1f)
    {
        float gw = OricFont.GlyphWidth * scale, gh = OricFont.GlyphHeight * scale;
        var size = new Vector2(gw * Scale / (OricFont.GlyphWidth * FontDetail), gh * Scale / (OricFont.GlyphHeight * FontDetail));
        for (int i = 0; i < text.Length; i++)
        {
            int index = OricFont.IndexOf(text[i]);
            if (index == 0)
                continue;
            var src = new Rectangle(index * (OricFont.GlyphWidth * FontDetail + FontPad * 2) + FontPad, FontPad,
                OricFont.GlyphWidth * FontDetail, OricFont.GlyphHeight * FontDetail);
            _batch.Draw(_font, new Vector2((x + i * gw) * Scale, y * Scale), src, ink, 0f, Vector2.Zero, size,
                SpriteEffects.None, 0f);
        }
    }

    public void Text(float x, float y, string text, OricColor ink, float scale = 1f) => Text(x, y, text, ink.ToColor(), scale);

    /// <summary>Text with a dark drop shadow, for titles over pictures.</summary>
    public void TextShadowed(float x, float y, string text, Color ink, float scale = 1f)
    {
        Text(x + 0.5f * scale, y + 0.5f * scale, text, Color.Black * 0.8f, scale);
        Text(x, y, text, ink, scale);
    }

    /// <summary>Text at a character cell (40 columns).</summary>
    public void TextAt(int column, float y, string text, OricColor ink) =>
        Text(column * OricFont.GlyphWidth, y, text, ink);

    /// <summary>Text horizontally centred on the screen.</summary>
    public void TextCentered(float y, string text, OricColor ink, float scale = 1f) =>
        TextCentered(y, text, ink.ToColor(), scale);

    public void TextCentered(float y, string text, Color ink, float scale = 1f) =>
        Text((Width - text.Length * OricFont.GlyphWidth * scale) / 2, y, text, ink, scale);

    public static float TextWidth(string text, float scale = 1f) => text.Length * OricFont.GlyphWidth * scale;

    // ---------------------------------------------------------------- textures

    private readonly Dictionary<string, Texture2D> _art = new();

    /// <summary>The high-resolution picture with this name (embedded Art/name.png), or null.</summary>
    private Texture2D Art(string name)
    {
        if (_art.TryGetValue(name, out var tex))
            return tex;
        var asm = typeof(Canvas).Assembly;
        using var stream = asm.GetManifestResourceStream("Art." + name + ".png") ?? asm.GetManifestResourceStream("Art." + name + ".jpg");
        if (stream != null)
        {
            tex = Texture2D.FromStream(_device, stream);
            // Pictures are stored with straight alpha; the sprite batch blends premultiplied colour.
            var data = new Color[tex.Width * tex.Height];
            tex.GetData(data);
            for (int i = 0; i < data.Length; i++)
            {
                var c = data[i];
                data[i] = new Color(c.R * c.A / 255, c.G * c.A / 255, c.B * c.A / 255, c.A);
            }
            tex.SetData(data);
        }
        _art[name] = tex;
        return tex;
    }

    /// <summary>True when the picture exists.</summary>
    public bool HasArt(string name) => Art(name) != null;

    /// <summary>Transparent in the middle, black at the edges (smoothly): the torch-light vignette.</summary>
    private static Texture2D BuildHole(GraphicsDevice device, int size)
    {
        var data = new Color[size * size];
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float dx = (x + 0.5f) / size * 2 - 1, dy = (y + 0.5f) / size * 2 - 1;
                float d = Math.Clamp(MathF.Sqrt(dx * dx + dy * dy), 0f, 1f);
                float a = d * d * (3 - 2 * d);
                data[y * size + x] = new Color(0f, 0f, 0f, a);
            }
        var tex = new Texture2D(device, size, size);
        tex.SetData(data);
        return tex;
    }

    private static Texture2D BuildRamp(GraphicsDevice device)
    {
        var data = new Color[256];
        for (int i = 0; i < 256; i++)
            data[i] = new Color(i, i, i, 255);
        var tex = new Texture2D(device, 256, 1);
        tex.SetData(data);
        return tex;
    }

    private static Texture2D BuildRadial(GraphicsDevice device, int w, int h, float softness)
    {
        var data = new Color[w * h];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float dx = (x + 0.5f) / w * 2 - 1, dy = (y + 0.5f) / h * 2 - 1;
                float d = MathF.Sqrt(dx * dx + dy * dy);
                float a = Math.Clamp((1f - d) / softness, 0f, 1f);
                a = a * a * (3 - 2 * a);
                data[y * w + x] = new Color(a, a, a, a);
            }
        var tex = new Texture2D(device, w, h);
        tex.SetData(data);
        return tex;
    }

    /// <summary>Texels of padding around each glyph in the font texture (edge texels repeated, so magnified
    /// glyphs keep crisp edges instead of fading where the cell ends).</summary>
    private const int FontPad = 2;

    private static Texture2D BuildFont(GraphicsDevice device)
    {
        int count = OricFont.GlyphCount;
        int gw = OricFont.GlyphWidth * FontDetail, gh = OricFont.GlyphHeight * FontDetail;
        int cw = gw + FontPad * 2, ch = gh + FontPad * 2;
        int w = count * cw;
        var data = new Color[w * ch];
        for (int g = 0; g < count; g++)
        {
            var rows = OricFont.GlyphAt(g);
            var bits = new byte[OricFont.GlyphWidth * OricFont.GlyphHeight];
            for (int y = 0; y < OricFont.GlyphHeight; y++)
                for (int x = 0; x < OricFont.GlyphWidth; x++)
                    if ((rows[y] & (1 << (OricFont.GlyphWidth - 1 - x))) != 0)
                        bits[y * OricFont.GlyphWidth + x] = 1;
            var (big, bw, bh) = PixelArt.Smooth(bits, OricFont.GlyphWidth, OricFont.GlyphHeight, FontDetail);
            for (int y = -FontPad; y < bh + FontPad; y++)
                for (int x = -FontPad; x < bw + FontPad; x++)
                {
                    int sx = Math.Clamp(x, 0, bw - 1), sy = Math.Clamp(y, 0, bh - 1);
                    if (big[sy * bw + sx] != 0)
                        data[(y + FontPad) * w + g * cw + x + FontPad] = Color.White;
                }
        }
        var tex = new Texture2D(device, w, ch);
        tex.SetData(data);
        return tex;
    }

    public void Dispose()
    {
        foreach (var t in _art.Values)
            t?.Dispose();
        _art.Clear();
        _pixel.Dispose();
        _ramp.Dispose();
        _shadow.Dispose();
        _glow.Dispose();
        _font.Dispose();
        _hole.Dispose();
        _batch.Dispose();
    }
}

/// <summary>Enlarging pixel art without blocks: the Scale2x (EPX) filter, applied repeatedly.</summary>
public static class PixelArt
{
    /// <summary>Scale2x: doubles the image, rounding off diagonal edges instead of making stairs.</summary>
    public static byte[] Scale2x(byte[] src, int w, int h)
    {
        var dst = new byte[w * 2 * h * 2];
        int dw = w * 2;
        byte At(int x, int y) => src[Math.Clamp(y, 0, h - 1) * w + Math.Clamp(x, 0, w - 1)];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                byte b = At(x, y - 1), d = At(x - 1, y), e = At(x, y), f = At(x + 1, y), hh = At(x, y + 1);
                byte e0 = e, e1 = e, e2 = e, e3 = e;
                if (b != hh && d != f)
                {
                    e0 = d == b ? d : e;
                    e1 = b == f ? f : e;
                    e2 = d == hh ? d : e;
                    e3 = hh == f ? f : e;
                }
                dst[y * 2 * dw + x * 2] = e0;
                dst[y * 2 * dw + x * 2 + 1] = e1;
                dst[(y * 2 + 1) * dw + x * 2] = e2;
                dst[(y * 2 + 1) * dw + x * 2 + 1] = e3;
            }
        return dst;
    }

    /// <summary>Applies Scale2x until the image is <paramref name="factor"/> (a power of two) times larger.</summary>
    public static (byte[] pixels, int width, int height) Smooth(byte[] src, int w, int h, int factor)
    {
        var p = src;
        for (int f = 1; f < factor; f *= 2)
        {
            p = Scale2x(p, w, h);
            w *= 2;
            h *= 2;
        }
        return (p, w, h);
    }
}

/// <summary>Raster helpers (testable without a graphics device).</summary>
public static class Geometry
{
    public static IEnumerable<(int x, int y)> LinePoints(int x0, int y0, int x1, int y1)
    {
        int dx = Math.Abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
        int dy = -Math.Abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
        int err = dx + dy;
        while (true)
        {
            yield return (x0, y0);
            if (x0 == x1 && y0 == y1)
                yield break;
            int e2 = 2 * err;
            if (e2 >= dy) { err += dy; x0 += sx; }
            if (e2 <= dx) { err += dx; y0 += sy; }
        }
    }

    /// <summary>
    /// Horizontal spans (device row, left, right) covering a convex polygon given in virtual
    /// pixels, rasterised at <paramref name="scale"/> device pixels per virtual pixel and clipped.
    /// </summary>
    public static List<(int y, float x0, float x1)> Spans(ReadOnlySpan<Vector2> pts, float scale, int width, int height)
    {
        var result = new List<(int, float, float)>();
        if (pts.Length < 3)
            return result;
        float top = float.MaxValue, bottom = float.MinValue;
        foreach (var p in pts)
        {
            top = Math.Min(top, p.Y * scale);
            bottom = Math.Max(bottom, p.Y * scale);
        }
        int y0 = Math.Max(0, (int)MathF.Floor(top));
        int y1 = Math.Min(height - 1, (int)MathF.Ceiling(bottom) - 1);
        for (int y = y0; y <= y1; y++)
        {
            float yc = y + 0.5f;
            float left = float.MaxValue, right = float.MinValue;
            for (int i = 0; i < pts.Length; i++)
            {
                var a = pts[i] * scale;
                var b = pts[(i + 1) % pts.Length] * scale;
                float lo = Math.Min(a.Y, b.Y), hi = Math.Max(a.Y, b.Y);
                if (yc < lo || yc > hi || hi - lo < 1e-6f)
                    continue;
                float x = a.X + (yc - a.Y) * (b.X - a.X) / (b.Y - a.Y);
                left = Math.Min(left, x);
                right = Math.Max(right, x);
            }
            if (left > right)
                continue;
            left = Math.Max(0, left);
            right = Math.Min(width, right);
            if (right > left)
                result.Add((y, left, right));
        }
        return result;
    }
}
