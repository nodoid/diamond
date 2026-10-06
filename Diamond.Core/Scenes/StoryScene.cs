using Microsoft.Xna.Framework;
using Diamond.Core.Engine;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;

namespace Diamond.Core.Scenes;

/// <summary>Steven Smith's journal, then the shipwreck: the two pages before a new game.</summary>
public sealed class StoryScene : Scene
{
    private readonly Adventure _adventure;
    private readonly int _page;

    public StoryScene(DiamondGame game, Adventure adventure, int page = 0) : base(game)
    {
        _adventure = adventure;
        _page = page;
    }

    protected override void Update()
    {
        var input = Game.Input;
        if (input.LanguagePressed)
            Game.ToggleLanguage();
        if (input.BackPressed)
        {
            Game.PlayAdventure(_adventure);
            return;
        }
        if (Ticks > 15 && (input.ConfirmPressed || input.Taps.Count > 0))
        {
            if (_page == 0)
                Game.SwitchTo(new StoryScene(Game, _adventure, 1));
            else
                Game.PlayAdventure(_adventure);
        }
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, _page == 0 ? "intro" : "title", _page == 0 ? 0.55f : 0.6f);
        Ui.Header(c, 8, _page == 0 ? Strings.StoryHeader : Strings.Title, Ui.Gold);
        Ui.Paragraphs(c, _page == 0 ? Strings.Story : Strings.Story2, 6, 28, 38, _page == 0 ? new Color(255, 240, 210) : Color.White);
        Ui.Blink(c, Ticks, 212, Strings.NextPage(Game.IsMobile));
    }
}
