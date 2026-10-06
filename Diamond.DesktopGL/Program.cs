using Diamond.Core;

namespace Diamond.DesktopGL;

internal static class Program
{
    private static void Main(string[] args)
    {
        using var game = new DiamondGame();
        // --capture <folder> [--mobile] [--lang fr|en] [--scale n] records the store screenshots.
        game.Capture = Core.Demo.CaptureDirector.FromArgs(args);
        game.Run();
    }
}
