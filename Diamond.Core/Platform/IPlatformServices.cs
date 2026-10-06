using System.Globalization;
using Microsoft.Xna.Framework;

namespace Diamond.Core.Platform;

/// <summary>Services a platform head can supply to the shared game.</summary>
public interface IPlatformServices
{
    bool IsMobile { get; }

    /// <summary>Directory where high scores and settings are stored.</summary>
    string DataDirectory { get; }

    /// <summary>Two-letter ISO code of the device language ("fr", "en"...), used for the first run.</summary>
    string SystemLanguage { get; }

    /// <summary>Exit the application (ignored where the platform forbids it).</summary>
    void Quit(Game game);
}

/// <summary>Defaults suitable for desktop builds.</summary>
public class DesktopPlatformServices : IPlatformServices
{
    public virtual bool IsMobile => false;

    public virtual string DataDirectory
    {
        get
        {
            string root = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
            if (string.IsNullOrEmpty(root))
                root = System.AppContext.BaseDirectory;
            return System.IO.Path.Combine(root, "Diamond");
        }
    }

    public virtual string SystemLanguage => CultureInfo.CurrentUICulture.TwoLetterISOLanguageName;

    public virtual void Quit(Game game) => game.Exit();
}
