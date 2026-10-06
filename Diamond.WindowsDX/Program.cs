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
        game.Run();
    }
}
