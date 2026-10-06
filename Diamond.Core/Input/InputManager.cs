using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Input;
using Microsoft.Xna.Framework.Input.Touch;

namespace Diamond.Core.Input;

/// <summary>
/// Gathers keyboard, mouse, touch and game pad into a single per-frame view used by every scene.
/// Taps and clicks are reported in virtual Oric pixels.
/// </summary>
public sealed class InputManager
{
    private readonly bool _isMobile;
    private KeyboardState _prevKeys;
    private MouseState _prevMouse;
    private GamePadState _prevPad;
    private readonly List<Vector2> _taps = new();
    private readonly List<char> _typed = new();
    private readonly HashSet<Keys> _keyEvents = new();

    /// <summary>
    /// Records a key press reported by the window. Keys are also polled each frame, but a quick tap can
    /// start and end between two polls; this makes sure it still counts.
    /// </summary>
    public void KeyPressed(Keys key)
    {
        lock (_keyEvents)
            _keyEvents.Add(key);
    }

    public InputManager(bool isMobile)
    {
        _isMobile = isMobile;
        if (_isMobile)
            TouchPanel.EnabledGestures = GestureType.None;
    }

    public bool IsMobile => _isMobile;

    /// <summary>Walking: -1 left .. 1 right.</summary>
    public float MoveX { get; private set; }

    /// <summary>Walking: -1 towards the viewer .. 1 into the room.</summary>
    public float MoveZ { get; private set; }

    /// <summary>Mouse position in virtual pixels (desktop), for highlighting.</summary>
    public Vector2? Pointer { get; private set; }

    public bool ConfirmPressed { get; private set; }
    public bool BackPressed { get; private set; }
    public bool PausePressed { get; private set; }
    public bool UpPressed { get; private set; }
    public bool DownPressed { get; private set; }
    public bool LeftPressed { get; private set; }
    public bool RightPressed { get; private set; }
    public bool TakePressed { get; private set; }
    public bool UsePressed { get; private set; }
    public bool DropPressed { get; private set; }
    public bool NextSlotPressed { get; private set; }
    public int? SlotPressed { get; private set; }
    public bool LanguagePressed { get; private set; }
    public bool VolumePressed { get; private set; }
    public bool InstructionsPressed { get; private set; }

    /// <summary>A finger or the left mouse button is down (walk while held).</summary>
    public Vector2? Holding { get; private set; }

    /// <summary>New touches / clicks this frame, in virtual pixels.</summary>
    public IReadOnlyList<Vector2> Taps => _taps;

    /// <summary>Letters / digits typed this frame (name entry).</summary>
    public IReadOnlyList<char> Typed => _typed;

    public void Update(Func<Vector2, Vector2> toVirtual, bool isActive)
    {
        _taps.Clear();
        _typed.Clear();

        var keys = Keyboard.GetState();
        var pad = GamePad.GetState(PlayerIndex.One);
        bool Down(Keys k) => isActive && keys.IsKeyDown(k);
        HashSet<Keys> events;
        lock (_keyEvents)
        {
            events = new HashSet<Keys>(_keyEvents);
            _keyEvents.Clear();
        }
        bool Hit(Keys k) => isActive && ((keys.IsKeyDown(k) && !_prevKeys.IsKeyDown(k)) || events.Contains(k));
        bool PadHit(Buttons b) => pad.IsButtonDown(b) && !_prevPad.IsButtonDown(b);

        float kx = 0, kz = 0;
        if (Down(Keys.Left)) kx -= 1;
        if (Down(Keys.Right)) kx += 1;
        if (Down(Keys.Up)) kz += 1;
        if (Down(Keys.Down)) kz -= 1;
        var stick = pad.ThumbSticks.Left;
        if (Math.Abs(stick.X) > 0.25f) kx = stick.X;
        if (Math.Abs(stick.Y) > 0.25f) kz = stick.Y;
        if (pad.IsButtonDown(Buttons.DPadLeft)) kx = -1;
        if (pad.IsButtonDown(Buttons.DPadRight)) kx = 1;
        if (pad.IsButtonDown(Buttons.DPadUp)) kz = 1;
        if (pad.IsButtonDown(Buttons.DPadDown)) kz = -1;
        MoveX = kx;
        MoveZ = kz;

        LeftPressed = Hit(Keys.Left) || PadHit(Buttons.DPadLeft);
        RightPressed = Hit(Keys.Right) || PadHit(Buttons.DPadRight);
        UpPressed = Hit(Keys.Up) || PadHit(Buttons.DPadUp);
        DownPressed = Hit(Keys.Down) || PadHit(Buttons.DPadDown);

        bool confirm = Hit(Keys.Space) || Hit(Keys.Enter) || PadHit(Buttons.A) || PadHit(Buttons.Start);
        BackPressed = Hit(Keys.Escape) || PadHit(Buttons.Back);
        PausePressed = Hit(Keys.P) || PadHit(Buttons.Start);
        TakePressed = Hit(Keys.Space) || PadHit(Buttons.A);
        UsePressed = Hit(Keys.U) || Hit(Keys.Enter) || PadHit(Buttons.X);
        DropPressed = Hit(Keys.D) || PadHit(Buttons.B);
        NextSlotPressed = Hit(Keys.Tab) || PadHit(Buttons.RightShoulder) || PadHit(Buttons.Y);
        SlotPressed = Hit(Keys.D1) ? 0 : Hit(Keys.D2) ? 1 : Hit(Keys.D3) ? 2 : Hit(Keys.D4) ? 3 : null;
        LanguagePressed = Hit(Keys.L);
        VolumePressed = Hit(Keys.V);
        InstructionsPressed = Hit(Keys.I);

        // --- mouse (desktop only) ---
        Pointer = null;
        Holding = null;
        if (!_isMobile)
        {
            var mouse = Mouse.GetState();
            var v = toVirtual(new Vector2(mouse.X, mouse.Y));
            bool inside = v.X >= 0 && v.Y >= 0 && v.X < Graphics.Canvas.Width && v.Y < Graphics.Canvas.Height;
            if (inside && isActive)
                Pointer = v;
            bool click = isActive && inside && mouse.LeftButton == ButtonState.Pressed && _prevMouse.LeftButton == ButtonState.Released;
            if (click)
                _taps.Add(v);
            if (isActive && inside && mouse.LeftButton == ButtonState.Pressed)
                Holding = v;
            _prevMouse = mouse;
        }

        // --- touch ---
        var touches = TouchPanel.GetState();
        int pressed = 0;
        foreach (var t in touches)
        {
            var v = toVirtual(t.Position);
            if (t.State == TouchLocationState.Pressed || t.State == TouchLocationState.Moved)
                Holding = v;
            if (t.State != TouchLocationState.Pressed)
                continue;
            pressed++;
            _taps.Add(v);
        }
        if (touches.Count >= 3 && pressed > 0)
            PausePressed = true;

        // --- typed characters for name entry ---
        foreach (var k in keys.GetPressedKeys())
        {
            if (_prevKeys.IsKeyDown(k) || !isActive)
                continue;
            if (k >= Keys.A && k <= Keys.Z)
                _typed.Add((char)('A' + (k - Keys.A)));
            else if (k >= Keys.D0 && k <= Keys.D9)
                _typed.Add((char)('0' + (k - Keys.D0)));
            else if (k == Keys.Back)
                _typed.Add('\b');
        }

        ConfirmPressed = confirm;
        _prevKeys = keys;
        _prevPad = pad;
    }
}
