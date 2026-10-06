using System;
using Diamond.Core;

namespace Diamond.WindowsDX;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        using var game = new DiamondGame();
        // --capture <folder> [--mobile] [--lang fr|en] [--scale n] records the store screenshots.
        game.Capture = Core.Demo.CaptureDirector.FromArgs(args);
        // Keyboard events from the window: every press (even a tap between two polls) and typed text.
        game.Window.KeyDown += (_, e) => game.KeyPressed(e.Key);
        game.Window.TextInput += (_, e) => game.CharacterTyped(e.Key, e.Character);
        game.Run();
    }
}
