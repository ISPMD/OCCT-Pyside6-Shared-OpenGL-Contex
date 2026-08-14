import ctypes

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QSurfaceFormat, QWindow
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from OCP.AIS import AIS_InteractiveContext
from OCP.Aspect import Aspect_DisplayConnection
from OCP.OpenGl import OpenGl_FrameBuffer, OpenGl_GraphicDriver
from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor
from OCP.V3d import V3d_Viewer
from OCP.Xw import Xw_Window


# -- Xlib helpers ----------------------------------------------------------

_libx11 = ctypes.CDLL("libX11.so.6")
_libx11.XResizeWindow.argtypes = [
    ctypes.c_void_p,  # Display*
    ctypes.c_ulong,   # Window (XID)
    ctypes.c_uint,    # width
    ctypes.c_uint,    # height
]
_libx11.XResizeWindow.restype = ctypes.c_int
_libx11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
_libx11.XSync.restype = ctypes.c_int
_libx11.XOpenDisplay.argtypes = [ctypes.c_char_p]
_libx11.XOpenDisplay.restype = ctypes.c_void_p


def _xresize_sync(display_ptr: int, xid: int, w: int, h: int) -> None:
    """Resize an X11 window synchronously, blocking until the X server
    has committed the new geometry. This is necessary before telling OCCT
    to redraw, so the drawable dimensions and the OCCT viewport are always
    in sync -- QWindow.resize() is async and causes stretched frames."""
    _libx11.XResizeWindow(
        ctypes.c_void_p(display_ptr),
        ctypes.c_ulong(xid),
        ctypes.c_uint(w),
        ctypes.c_uint(h),
    )
    _libx11.XSync(ctypes.c_void_p(display_ptr), ctypes.c_int(0))


def current_glx_context() -> int:
    libgl = ctypes.CDLL("libGL.so.1")
    libgl.glXGetCurrentContext.restype = ctypes.c_void_p
    ctx = libgl.glXGetCurrentContext()
    if not ctx:
        raise RuntimeError("No current GLX context")
    return ctx


def wrap_capsule(raw_ptr: int):
    new = ctypes.pythonapi.PyCapsule_New
    new.restype = ctypes.py_object
    new.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
    return new(raw_ptr, None, None)


# -- Widget ----------------------------------------------------------------

class OcctViewerWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        self.setFormat(fmt)

        self._hidden_window = None
        self._x11_display = None   # raw Display* kept open for XSync calls
        self._x11_wid = None       # XID of the hidden window
        self._driver = None
        self._viewer = None
        self._ais_context = None
        self._view = None
        self._gl_ctx = None
        self._initialized = False
        self._last_pos = None

        self.setFocusPolicy(Qt.StrongFocus)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self.update)
        self._render_timer.start()

    @property
    def context(self):
        """AIS_InteractiveContext -- None until initializeGL() has run."""
        return self._ais_context

    @property
    def view(self):
        """V3d_View -- None until initializeGL() has run."""
        return self._view

    def _device_size(self) -> QSize:
        dpr = self.devicePixelRatioF()
        return QSize(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))

    def initializeGL(self):
        size = self._device_size()

        self._hidden_window = QWindow()
        self._hidden_window.setSurfaceType(QWindow.OpenGLSurface)
        self._hidden_window.setFormat(self.format())
        self._hidden_window.setFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.BypassWindowManagerHint
        )
        self._hidden_window.resize(size.width(), size.height())
        self._hidden_window.create()

        self._x11_wid = int(self._hidden_window.winId())
        # Open a dedicated Display* for our synchronous XResizeWindow/XSync
        # calls. Sharing Qt's internal display connection is not safe since
        # Qt may be in the middle of its own XCB traffic.
        self._x11_display = _libx11.XOpenDisplay(None)
        if not self._x11_display:
            raise RuntimeError("XOpenDisplay failed")

        qt_native_ctx = current_glx_context()

        display = Aspect_DisplayConnection()
        self._driver = OpenGl_GraphicDriver(display, False)

        self._viewer = V3d_Viewer(self._driver)
        self._viewer.SetDefaultLights()
        self._viewer.SetLightOn()
        self._ais_context = AIS_InteractiveContext(self._viewer)

        xw_window = Xw_Window(display, self._x11_wid)
        self._view = self._viewer.CreateView()
        share_capsule = wrap_capsule(qt_native_ctx)
        self._view.SetWindow(xw_window, share_capsule)
        self._view.SetBackgroundColor(
            Quantity_Color(0.12, 0.12, 0.15, Quantity_TypeOfColor.Quantity_TOC_RGB)
        )

        self._gl_ctx = self._driver.GetSharedContext()
        self.makeCurrent()
        self._view.FitAll()
        self._initialized = True

    def resizeGL(self, w, h):
        if not self._initialized:
            return
        size = self._device_size()
        # Resize the X11 window synchronously so the server commits the
        # new drawable geometry before OCCT redraws. QWindow.resize() goes
        # through XCB asynchronously and causes a stretched frame.
        _xresize_sync(self._x11_display, self._x11_wid, size.width(), size.height())
        self.makeCurrent()
        self._view.MustBeResized()

    def paintGL(self):
        if not self._initialized:
            return

        target = OpenGl_FrameBuffer()
        if not target.InitWrapper(self._gl_ctx):
            return

        previous = self._gl_ctx.SetDefaultFrameBuffer(target)
        self._view.Redraw()
        self._gl_ctx.SetDefaultFrameBuffer(previous)
        self.makeCurrent()

    def _event_pos(self, event):
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def mousePressEvent(self, event):
        if not self._initialized:
            return
        pos = self._event_pos(event)
        self._last_pos = pos
        self._view.StartRotation(pos.x(), pos.y())

    def mouseMoveEvent(self, event):
        if not self._initialized or self._last_pos is None:
            return
        pos = self._event_pos(event)
        buttons = event.buttons()
        shift_held = bool(event.modifiers() & Qt.ShiftModifier)

        panning = (buttons & Qt.MiddleButton) or (
            (buttons & Qt.LeftButton) and shift_held
        )
        rotating = (buttons & Qt.LeftButton) and not shift_held

        if panning:
            dx = pos.x() - self._last_pos.x()
            dy = pos.y() - self._last_pos.y()
            self._view.Pan(dx, -dy)
        elif rotating:
            self._view.Rotation(pos.x(), pos.y())

        self._last_pos = pos

    def mouseReleaseEvent(self, event):
        self._last_pos = None

    def wheelEvent(self, event):
        if not self._initialized:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._view.SetZoom(factor)

    def mouseDoubleClickEvent(self, event):
        if not self._initialized:
            return
        self._view.FitAll()