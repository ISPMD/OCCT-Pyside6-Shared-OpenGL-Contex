import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
)

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.AIS import AIS_Shape
from OCP.Graphic3d import Graphic3d_TypeOfShadingModel_Unlit
from OCP.Prs3d import Prs3d_LineAspect
from OCP.Aspect import Aspect_TOL_SOLID
from OCP.Quantity import (
    Quantity_Color,
    Quantity_NOC_BLACK,
    Quantity_NOC_GOLDENROD,
)

from Viewer import OcctViewerWidget


# ---------------------------------------------------------------------------
# Floating capsule top bar
# ---------------------------------------------------------------------------

class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("TopBar")

        self.setStyleSheet("""
            QFrame#TopBar {
                background: rgba(25, 25, 30, 215);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 24px;
            }

            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 220);
                border: none;
                border-radius: 17px;
                padding: 7px 16px;
                font-size: 13px;
            }

            QPushButton:hover {
                background: rgba(255, 255, 255, 25);
            }

            QPushButton:pressed {
                background: rgba(255, 255, 255, 40);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)

        for text in ["Select", "Measure", "View", "Fit"]:
            button = QPushButton(text)
            button.setCursor(Qt.PointingHandCursor)
            layout.addWidget(button)


# ---------------------------------------------------------------------------
# Floating panel
# ---------------------------------------------------------------------------

class FloatingPanel(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)

        self.setObjectName("FloatingPanel")

        self.setStyleSheet("""
            QFrame#FloatingPanel {
                background: rgba(25, 25, 30, 210);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 16px;
            }

            QLabel {
                color: rgba(255, 255, 255, 220);
                background: transparent;
            }

            QPushButton {
                background: rgba(255, 255, 255, 12);
                color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 8px;
                padding: 6px 10px;
            }

            QPushButton:hover {
                background: rgba(255, 255, 255, 25);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)

        layout.addWidget(title_label)

        self.content = QVBoxLayout()
        self.content.setSpacing(6)

        layout.addLayout(self.content)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OCCT Viewer")
        self.resize(900, 650)

        # ------------------------------------------------------------------
        # Overlay container
        # ------------------------------------------------------------------

        self.container = QWidget()
        self.setCentralWidget(self.container)

        # OCCT viewer
        self.viewer = OcctViewerWidget(self.container)
        self.viewer.setGeometry(self.container.rect())

        # ------------------------------------------------------------------
        # Top floating capsule
        # ------------------------------------------------------------------

        self.topbar = TopBar(self.container)

        self.topbar.adjustSize()

        topbar_width = 430
        topbar_height = 52

        self.topbar.setGeometry(
            (self.width() - topbar_width) // 2,
            18,
            topbar_width,
            topbar_height,
        )

        # ------------------------------------------------------------------
        # Left floating panel
        # ------------------------------------------------------------------

        self.left_panel = FloatingPanel("Model", self.container)

        self.left_panel.setFixedSize(190, 250)

        for text in [
            "Box",
            "Body",
            "Sketch",
            "Construction",
        ]:
            button = QPushButton(text)
            self.left_panel.content.addWidget(button)

        self.left_panel.move(18, 85)

        # ------------------------------------------------------------------
        # Right floating panel
        # ------------------------------------------------------------------

        self.right_panel = FloatingPanel("Properties", self.container)

        self.right_panel.setFixedSize(210, 220)

        self.right_panel.content.addWidget(QLabel("Selected object"))

        self.right_panel.content.addWidget(QLabel("Size"))

        size_button = QPushButton("50 × 50 × 50")
        self.right_panel.content.addWidget(size_button)

        self.right_panel.content.addWidget(QLabel("Display"))

        display_button = QPushButton("Shading")
        self.right_panel.content.addWidget(display_button)

        self.right_panel.move(
            self.container.width() - self.right_panel.width() - 18,
            85,
        )

        self._scene_built = False

    # ----------------------------------------------------------------------
    # Keep viewer and overlays positioned correctly
    # ----------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self.viewer.setGeometry(self.container.rect())

        # Top bar
        topbar_width = 430
        topbar_height = 52

        self.topbar.setGeometry(
            (self.container.width() - topbar_width) // 2,
            18,
            topbar_width,
            topbar_height,
        )

        # Left panel
        self.left_panel.move(
            18,
            85,
        )

        # Right panel
        self.right_panel.move(
            self.container.width()
            - self.right_panel.width()
            - 18,
            85,
        )

    # ----------------------------------------------------------------------
    # OCCT scene
    # ----------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)

        if (
            not self._scene_built
            and self.viewer.context is not None
        ):
            self._build_scene()
            self._scene_built = True

    def _build_scene(self):
        box = BRepPrimAPI_MakeBox(
            50.0,
            50.0,
            50.0,
        ).Shape()

        ais_shape = AIS_Shape(box)

        drawer = ais_shape.Attributes()

        drawer.SetShadingModel(
            Graphic3d_TypeOfShadingModel_Unlit
        )

        # Black edges, 3px wide
        drawer.SetFaceBoundaryDraw(True)

        drawer.SetFaceBoundaryAspect(
            Prs3d_LineAspect(
                Quantity_Color(Quantity_NOC_BLACK),
                Aspect_TOL_SOLID,
                3.0,
            )
        )

        self.viewer.context.Display(
            ais_shape,
            1,
            0,
            False,
        )

        self.viewer.context.SetColor(
            ais_shape,
            Quantity_Color(
                Quantity_NOC_GOLDENROD
            ),
            True,
        )

        self.viewer.view.FitAll()


def main():
    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(True)

    app.aboutToQuit.connect(
        lambda: os._exit(0)
    )

    win = MainWindow()
    win.show()

    app.exec()


if __name__ == "__main__":
    main()
