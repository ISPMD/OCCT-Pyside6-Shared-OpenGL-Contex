# OCCT V3d PySide6 Shared OpenGL-Context

I spent a long time trying to integrate a V3d viewer in Pyside6 from OCCT trough various bindings and have the default qwidgets keep their transparency over the OCCT embedded window with no luck. Finally figured out this method so i am sharing it in case anyone else needs it. 

I myself searched all over the internet and found no solution to this problem when i needed it.

First i tried embedding the viewer normally and creating custom widgets with masks - that worked but only for rounded corners, no internal transparency. After that i tried rendering the scene off-screen and grabbing the pixmap from the viewer and displaying it in a qwidget. it worked like a charm but was too slow for older hardware. On my newer PC I got max 120fps with vsync off. And finally figured this method out and jumped from 120fps to 900fps for a simple scene with vsync off.

You can use other renderers to sidestep this issue like three.js for web or the QT one, or Raylib, etc, but if u don't want to rebuild the already built functionality, this is one way of doing it.

This approach embeds the **OCCT V3d viewer inside a PySide6 `QOpenGLWidget`** while keeping normal Qt widgets usable as transparent overlays on top of the 3D viewport.

The main goal is to allow UI such as:

- Transparent panels
- Buttons
- Toolbars
- Selection controls
- CAD property panels
- Other `QWidget` overlays

to remain visible **above the OCCT viewport** without replacing the Qt rendering surface with a native OCCT window.

## Platform

This implementation is currently intended for:

**Linux Mint / Linux X11**

It uses X11-specific functionality (`Xw_Window`, Xlib, and GLX) to connect OCCT with the Qt OpenGL context.

The same general architecture can be adapted to other platforms, but the native window/context integration needs platform-specific implementations:

- **Linux/X11:** `Xw_Window` + Xlib + GLX
- **Windows:** Win32 window/context integration
- **macOS:** Cocoa/NSView + appropriate OpenGL integration

## Approach

The basic architecture is:

```text
PySide6 QOpenGLWidget
        │
        │ visible Qt surface
        ▼
Qt OpenGL context
        │
        │ shared with OCCT
        ▼
OCCT V3d_View
        │
        ▼
OCCT Xw_Window
        │
        ▼
Hidden native X11 QWindow
```

The important trick is that OCCT receives a **hidden native X11 window** through `Xw_Window`, while its OpenGL context is shared with the Qt context.

During `paintGL()`, OCCT's framebuffer is temporarily redirected to the framebuffer owned by the `QOpenGLWidget`:

Because the actual visible surface is still a normal `QOpenGLWidget`, Qt can continue compositing other widgets above it.


## Why this approach?

The key reason for using this method instead of simply embedding a native OCCT window is **Qt widget compositing**.

A native OCCT window can interfere with Qt's normal widget stacking and transparency. By rendering OCCT into the `QOpenGLWidget` framebuffer instead, the viewport remains part of the Qt widget hierarchy.

This makes transparent Qt overlays possible while still using the OCCT `V3d_View` renderer.

The X11-specific parts should be replaced with the equivalent native-window/context mechanisms when adapting this approach to Windows or macOS.
