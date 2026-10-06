using System;
using Microsoft.Xna.Framework;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;

namespace Diamond.Core.Scenes;

/// <summary>The title: the cursed island at dusk, the name in both languages, the credits and Bach's Toccata.</summary>
public sealed class TitleScene : Scene
{
    public TitleScene(DiamondGame game) : base(game)
    {
    }

    public override void Enter() => Game.Sound.PlayTune();

    public override void Leave() => Game.Sound.StopTune();

    protected override void Update()
    {
        var input = Game.Input;
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (input.BackPressed)
        {
            Game.Quit();
            return;
        }
        if (Ticks > 10 && (input.ConfirmPressed || input.Taps.Count > 0))
            Game.ShowMenu();
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, "title");
        DrawTitle(c, 10, Ticks);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Credit)) / 2, 196, Strings.Credit, Color.White);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.BasedOn)) / 2, 205, Strings.BasedOn, Ui.Leaf);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Authors)) / 2, 214, Strings.Authors, Ui.Leaf);
        Ui.Blink(c, Ticks, 182, Strings.PressToStart(Game.IsMobile));
    }

    /// <summary>The two-line title in large letters, with a sparkle running across it.</summary>
    public static void DrawTitle(Canvas c, float y, int ticks)
    {
        string l1 = Strings.TitleLine1, l2 = Strings.TitleLine2;
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(l1, 2)) / 2, y, l1, Ui.Gold, 2);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(l2, 2)) / 2, y + 18, l2, Ui.Gold, 2);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Subtitle)) / 2, y + 38, Strings.Subtitle, Ui.Sky);
        float sweep = ticks * 2.4f % 420 - 90;
        c.Glow(sweep, y + 16, 9, Color.White * 0.35f);
    }
}
