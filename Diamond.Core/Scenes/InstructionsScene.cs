using Microsoft.Xna.Framework;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;

namespace Diamond.Core.Scenes;

/// <summary>Four pages: giving orders, moving, survival and the controls.</summary>
public sealed class InstructionsScene : Scene
{
    private readonly int _page;

    public InstructionsScene(DiamondGame game, int page = 0) : base(game)
    {
        _page = page;
    }

    private int Pages => Strings.InstructionHeaders.Length;

    protected override void Update()
    {
        var input = Game.Input;
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (input.BackPressed)
        {
            Game.ShowMenu();
            return;
        }
        if (Ticks > 10 && (input.ConfirmPressed || input.Taps.Count > 0 || input.RightPressed))
        {
            if (_page + 1 < Pages)
                Game.SwitchTo(new InstructionsScene(Game, _page + 1));
            else
                Game.ShowMenu();
        }
        else if (Ticks > 10 && input.LeftPressed && _page > 0)
        {
            Game.SwitchTo(new InstructionsScene(Game, _page - 1));
        }
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, "intro", 0.7f);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Instructions, 2)) / 2, 4, Strings.Instructions, Ui.Gold, 2);
        Ui.Header(c, 24, Strings.InstructionHeaders[_page], Ui.Sky);
        string text = Strings.InstructionPages(Game.IsMobile, Game.Settings.Parser)[_page];
        Ui.Paragraphs(c, text, 6, 40, 38, Color.White);
        c.TextCentered(200, Strings.Page(_page + 1, Pages), Ui.Sky);
        Ui.Blink(c, Ticks, 212, Strings.NextPage(Game.IsMobile));
    }
}
