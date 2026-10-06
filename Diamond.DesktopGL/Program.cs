using System;
using System.Runtime.InteropServices;
using Diamond.Core;

namespace Diamond.DesktopGL;

internal static class Program
{
    [DllImport("SDL2", CallingConvention = CallingConvention.Cdecl)]
    private static extern void SDL_RaiseWindow(IntPtr window);

    // macOS: [NSApp activateIgnoringOtherApps:YES], so the game takes the keyboard from the terminal.
    [DllImport("/usr/lib/libobjc.dylib")]
    private static extern IntPtr objc_getClass(string name);

    [DllImport("/usr/lib/libobjc.dylib")]
    private static extern IntPtr sel_registerName(string name);

    [DllImport("/usr/lib/libobjc.dylib", EntryPoint = "objc_msgSend")]
    private static extern IntPtr Send(IntPtr receiver, IntPtr selector);

    [DllImport("/usr/lib/libobjc.dylib", EntryPoint = "objc_msgSend")]
    private static extern void Send(IntPtr receiver, IntPtr selector, bool value);

    private static void ActivateMacApp()
    {
        var app = Send(objc_getClass("NSApplication"), sel_registerName("sharedApplication"));
        Send(app, sel_registerName("activateIgnoringOtherApps:"), true);
    }

    private static void Main(string[] args)
    {
        // MonoGame ships SDL under its platform file name; point "SDL2" at it (it is already loaded by then).
        NativeLibrary.SetDllImportResolver(typeof(Program).Assembly, (name, assembly, path) =>
        {
            if (name != "SDL2")
                return IntPtr.Zero;
            foreach (var file in new[] { "libSDL2-2.0.0.dylib", "libSDL2-2.0.so.0", "SDL2.dll" })
                if (NativeLibrary.TryLoad(file, assembly, path, out var handle))
                    return handle;
            return IntPtr.Zero;
        });
        using var game = new DiamondGame();
        // --capture <folder> [--mobile] [--lang fr|en] [--scale n] records the store screenshots.
        game.Capture = Core.Demo.CaptureDirector.FromArgs(args);
        // Started from a terminal, the window opens behind it without the keyboard: bring it to the front.
        game.FirstFrame = g =>
        {
            try
            {
                if (OperatingSystem.IsMacOS())
                    ActivateMacApp();
                SDL_RaiseWindow(g.Window.Handle);
            }
            catch (Exception)
            {
                // Not fatal: the player can still click the window.
            }
        };
        game.Run();
    }
}
