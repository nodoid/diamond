using Microsoft.Xna.Framework;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;

namespace Diamond.Core.Scenes;

/// <summary>The interlude between the island and the underground (where the original asked you to save).</summary>
public sealed class PartTwoScene : Scene
{
    private readonly Adventure _adventure;

    public PartTwoScene(DiamondGame game, Adventure adventure) : base(game)
    {
        _adventure = adventure;
    }

    public override void Enter() => Game.Sound.Play(Audio.Sfx.Magic);

    protected override void Update()
    {
        var input = Game.Input;
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (Ticks > 25 && (input.ConfirmPressed || input.Taps.Count > 0 || input.BackPressed))
            Game.PlayAdventure(_adventure);
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, "part2", 0.25f);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.PartTwo, 2)) / 2, 24, Strings.PartTwo, Ui.Gold, 2);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Underground)) / 2, 46, Strings.Underground, Ui.Sky);
        c.Fill(10, 120, 220, 78, Color.Black * 0.55f);
        Ui.Paragraphs(c, Strings.PartTwoText, 14, 126, 36, Color.White);
        Ui.Blink(c, Ticks, 212, Strings.NextPage(Game.IsMobile));
    }
}
