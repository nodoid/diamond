using System;
using Microsoft.Xna.Framework;
using Diamond.Core.Audio;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;

namespace Diamond.Core.Scenes;

/// <summary>Death or escape: what happened, the score, the rank, and the way back into part two.</summary>
public sealed class EndScene : Scene
{
    private static readonly RectF RetryButton = new(40, 176, 160, 16);
    private readonly Adventure _adventure;

    public EndScene(DiamondGame game, Adventure adventure) : base(game)
    {
        _adventure = adventure;
    }

    private bool CanRetry => !_adventure.Won && Game.HasCheckpoint;

    public override void Enter()
    {
        if (_adventure.Won)
            Game.Sound.Play(Sfx.Victory);
    }

    protected override void Update()
    {
        var input = Game.Input;
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (Ticks < 40)
            return;
        bool retry = CanRetry && (Ui.Hit(RetryButton, input.Taps) || (!Game.IsMobile && Game.TypedText.Contains('r')) ||
                                  Game.TypedText.Contains('R'));
        if (retry)
        {
            Game.RestartPart2();
            return;
        }
        if (input.ConfirmPressed || input.Taps.Count > 0 || input.BackPressed)
            Game.ShowHallOfFame(_adventure);
    }

    public override void Draw(Canvas c)
    {
        var a = _adventure;
        if (a.Won)
        {
            Ui.Backdrop(c, "escape", 0.15f);
            string title = a.Ending == Ending.EscapedWithDiamond ? Strings.Victory : Strings.Escaped;
            c.TextShadowed((Canvas.Width - Canvas.TextWidth(title, 2)) / 2, 12, title, Ui.Gold, 2);
            if (a.Ending == Ending.EscapedWithDiamond)
            {
                float pulse = 0.5f + 0.5f * MathF.Sin(Ticks * 0.1f);
                var size = c.ArtSize("diamond");
                if (size != null)
                {
                    c.Glow(120, 50, 24, new Color(200, 230, 255) * (0.3f + 0.3f * pulse));
                    c.DrawStanding("diamond", 120, 62, 26);
                }
            }
        }
        else
        {
            ViewRenderer.Draw(c, a, Ticks, new RectF(0, 0, Canvas.Width, Canvas.Height));
            c.Fill(0, 0, Canvas.Width, Canvas.Height, new Color(90, 0, 0) * 0.6f);
            c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.YouAreDead, 2)) / 2, 12, Strings.YouAreDead,
                new Color(255, 120, 100), 2);
        }

        c.Fill(8, 72, 224, 98, Color.Black * 0.6f);
        float y = Ui.Paragraphs(c, a.EndMessage.ToString(), 14, 78, 36, Color.White);
        y = Math.Max(y + 6, 124);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.ScoreLine(a.Score))) / 2, y, Strings.ScoreLine(a.Score), Ui.Gold);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.MovesLine(a.Moves))) / 2, y + 11, Strings.MovesLine(a.Moves), Ui.Sky);
        string rank = Strings.Rank(a.Score);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(rank)) / 2, y + 22, rank, Ui.Leaf);

        if (CanRetry)
            Ui.Button(c, RetryButton, Strings.RetryPart2(Game.IsMobile), Game.Input.Pointer is { } p && RetryButton.Contains(p));
        if (Ticks >= 40)
            Ui.Blink(c, Ticks, 208, Strings.EndContinue(Game.IsMobile));
    }
}
