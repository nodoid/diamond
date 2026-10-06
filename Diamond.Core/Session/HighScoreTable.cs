using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace Diamond.Core.Session;

/// <summary>A place in the hall of fame: the score out of 100 and the moves taken.</summary>
public sealed record HighScoreEntry(int Score, int Moves, string Name)
{
    /// <summary>True when this result ranks above another (more points, or as many in fewer moves).</summary>
    public bool Beats(int score, int moves) => Score > score || (Score == score && Moves < moves);
}

/// <summary>The ten-place hall of fame, persisted as plain text.</summary>
public sealed class HighScoreTable
{
    public const int Capacity = 10;
    public const int NameLength = 5;
    private const string FileName = "halloffame.txt";

    private readonly List<HighScoreEntry> _entries = new();
    private readonly string _directory;

    public HighScoreTable(string directory)
    {
        _directory = directory;
        Reset();
    }

    public IReadOnlyList<HighScoreEntry> Entries => _entries;

    /// <summary>Fills the table with the default results.</summary>
    public void Reset()
    {
        _entries.Clear();
        for (int i = 0; i < Capacity; i++)
            _entries.Add(new HighScoreEntry(50 - i * 5, 300 + i * 25, "PFJ"));
    }

    public bool Qualifies(int score, int moves) =>
        score > 0 && (_entries.Count < Capacity || score > _entries[^1].Score ||
                      (score == _entries[^1].Score && moves < _entries[^1].Moves));

    /// <summary>Inserts a result, returning its rank (0 based) or -1 if it did not qualify.</summary>
    public int Add(int score, int moves, string name)
    {
        if (!Qualifies(score, moves))
            return -1;
        name = Sanitize(name);
        int index = _entries.FindIndex(e => !e.Beats(score, moves));
        if (index < 0)
            index = _entries.Count;
        _entries.Insert(index, new HighScoreEntry(score, moves, name));
        while (_entries.Count > Capacity)
            _entries.RemoveAt(_entries.Count - 1);
        return index;
    }

    public static string Sanitize(string name)
    {
        var chars = (name ?? string.Empty).ToUpperInvariant()
            .Where(c => (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == ' ' || c == '.')
            .Take(NameLength)
            .ToArray();
        var s = new string(chars).Trim();
        return s.Length == 0 ? "?????" : s;
    }

    public string Serialize() =>
        string.Join("\n", _entries.Select(e => $"{e.Score}\t{e.Moves}\t{e.Name}"));

    public void Deserialize(string text)
    {
        var parsed = new List<HighScoreEntry>();
        foreach (var line in (text ?? string.Empty).Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var parts = line.Split('\t');
            if (parts.Length == 3 && int.TryParse(parts[0], out int score) && int.TryParse(parts[1], out int moves) &&
                score >= 0 && moves >= 0)
                parsed.Add(new HighScoreEntry(Math.Min(score, 100), Math.Min(moves, 99999), Sanitize(parts[2])));
        }
        if (parsed.Count == 0)
            return;
        _entries.Clear();
        _entries.AddRange(parsed.OrderByDescending(e => e.Score).ThenBy(e => e.Moves).Take(Capacity));
    }

    public void Load()
    {
        try
        {
            string path = Path.Combine(_directory, FileName);
            if (File.Exists(path))
                Deserialize(File.ReadAllText(path));
        }
        catch (Exception)
        {
            // A corrupt or unreadable table falls back to defaults.
        }
    }

    public void Save()
    {
        try
        {
            Directory.CreateDirectory(_directory);
            File.WriteAllText(Path.Combine(_directory, FileName), Serialize());
        }
        catch (Exception)
        {
        }
    }
}
