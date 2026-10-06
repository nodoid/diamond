using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Diamond.Core.Audio;
using Diamond.Core.Graphics;
using Diamond.Core.Localization;
using Diamond.Core.Oric;

namespace Diamond.Core.Scenes;

/// <summary>Main menu, worked with the cursor keys and SPACE, the mouse or a tap.</summary>
public sealed class MenuScene : Scene
{
    private const int MenuTop = 80;
    private const int ItemHeight = 13;
    private int _selected;

    private enum Item
    {
        Continue,
        NewGame,
        RestartPart2,
        Instructions,
        HallOfFame,
        Language,
        Parser,
        Volume,
        Quit,
    }

    public MenuScene(DiamondGame game) : base(game)
    {
    }

    private List<Item> Items()
    {
        var items = new List<Item>();
        if (Game.Current is { Ended: false })
            items.Add(Item.Continue);
        items.Add(Item.NewGame);
        if (Game.HasCheckpoint)
            items.Add(Item.RestartPart2);
        items.AddRange([Item.Instructions, Item.HallOfFame, Item.Language, Item.Parser, Item.Volume]);
        if (!Game.IsMobile)
            items.Add(Item.Quit);
        return items;
    }

    private string Text(Item item) => item switch
    {
        Item.Continue => Strings.Continue,
        Item.NewGame => Strings.NewGame,
        Item.RestartPart2 => Strings.RestartPart2,
        Item.Instructions => Strings.Instructions,
        Item.HallOfFame => Strings.HallOfFame,
        Item.Language => Strings.LanguageItem,
        Item.Parser => Strings.ParserItem(Game.Settings.Parser),
        Item.Volume => Strings.Volume + " : " + Strings.VolumeName(Game.Sound.Level),
        _ => Strings.Quit,
    };

    protected override void Update()
    {
        var input = Game.Input;
        var items = Items();
        if (input.LanguagePressed)
            Activate(Item.Language);
        if (input.VolumePressed)
            Activate(Item.Volume);
        if (input.InstructionsPressed)
            Activate(Item.Instructions);
        if (input.BackPressed)
        {
            if (Game.Current is { Ended: false })
                Game.ContinueGame();
            else
                Game.ShowTitle();
            return;
        }
        if (input.UpPressed)
            _selected = (_selected + items.Count - 1) % items.Count;
        if (input.DownPressed)
            _selected = (_selected + 1) % items.Count;

        if (input.Pointer is { } p && RowAt(p.Y, items.Count) is int hover)
            _selected = hover;
        foreach (var tap in input.Taps)
        {
            if (RowAt(tap.Y, items.Count) is int row)
            {
                _selected = row;
                Activate(items[row]);
                return;
            }
        }
        if (input.Taps.Count == 0 && input.ConfirmPressed)
            Activate(items[_selected]);
    }

    private static int? RowAt(float y, int count)
    {
        int row = (int)((y - MenuTop + 3) / ItemHeight);
        return y >= MenuTop - 3 && row >= 0 && row < count ? row : null;
    }

    private void Activate(Item item)
    {
        switch (item)
        {
            case Item.Continue:
                Game.ContinueGame();
                break;
            case Item.NewGame:
                Game.StartNewGame();
                break;
            case Item.RestartPart2:
                Game.RestartPart2();
                break;
            case Item.Instructions:
                Game.ShowInstructions();
                break;
            case Item.HallOfFame:
                Game.ShowHallOfFame();
                break;
            case Item.Language:
                Game.ToggleLanguage();
                Game.Sound.Play(Sfx.Menu);
                break;
            case Item.Parser:
                Game.ToggleParserMode();
                Game.Sound.Play(Sfx.Menu);
                break;
            case Item.Volume:
                Game.CycleVolume();
                break;
            default:
                Game.Quit();
                break;
        }
    }

    public override void Draw(Canvas c)
    {
        Ui.Backdrop(c, "title", 0.5f);
        TitleScene.DrawTitle(c, 8, Ticks);

        var items = Items();
        _selected = System.Math.Min(_selected, items.Count - 1);
        for (int i = 0; i < items.Count; i++)
        {
            string text = Text(items[i]);
            int y = MenuTop + i * ItemHeight;
            if (i == _selected)
            {
                float w = (text.Length + 2) * 6;
                c.ShadePolygon([new((Canvas.Width - w) / 2, y - 2), new((Canvas.Width + w) / 2, y - 2),
                        new((Canvas.Width + w) / 2, y + 9), new((Canvas.Width - w) / 2, y + 9)],
                    new Color(240, 196, 80), (_, yy) => 1.1f - 0.4f * (yy - y + 2) / 11f);
                c.TextCentered(y, text, new Color(30, 20, 60));
            }
            else
            {
                c.TextShadowed((Canvas.Width - Canvas.TextWidth(text)) / 2, y, text, i == 0 ? Ui.Gold : Color.White);
            }
        }
        if (items[_selected] == Item.Parser)
            c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.ParserHint(Game.Settings.Parser))) / 2, 66,
                Strings.ParserHint(Game.Settings.Parser), Ui.Leaf);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.Credit)) / 2, 204, Strings.Credit, Color.White);
        c.TextShadowed((Canvas.Width - Canvas.TextWidth(Strings.BasedOn)) / 2, 214, Strings.BasedOn, Ui.Leaf);
    }
}
