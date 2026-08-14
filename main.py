import sys
import os

from PySide6.QtWidgets import QApplication, QMainWindow

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.AIS import AIS_Shape
from OCP.Graphic3d import Graphic3d_TypeOfShadingModel_Unlit
from OCP.Prs3d import Prs3d_LineAspect
from OCP.Aspect import Aspect_TOL_SOLID
from OCP.Quantity import Quantity_Color, Quantity_NOC_BLACK, Quantity_NOC_GOLDENROD, Quantity_TOC_RGB

from Viewer import OcctViewerWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCCT Viewer")
        self.resize(900, 650)

        self.viewer = OcctViewerWidget(self)
        self.setCentralWidget(self.viewer)

        self._scene_built = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._scene_built and self.viewer.context is not None:
            self._build_scene()
            self._scene_built = True

    def _build_scene(self):
        box = BRepPrimAPI_MakeBox(50.0, 50.0, 50.0).Shape()
        ais_shape = AIS_Shape(box)

        drawer = ais_shape.Attributes()
        drawer.SetShadingModel(Graphic3d_TypeOfShadingModel_Unlit)

        # Black edges, 3px wide
        drawer.SetFaceBoundaryDraw(True)
        drawer.SetFaceBoundaryAspect(
            Prs3d_LineAspect(
                Quantity_Color(Quantity_NOC_BLACK),
                Aspect_TOL_SOLID,
                3.0,
            )
        )

        self.viewer.context.Display(ais_shape, 1, 0, False)

        self.viewer.context.SetColor(
            ais_shape,
            Quantity_Color(Quantity_NOC_GOLDENROD),
            True,
        )

        self.viewer.view.FitAll()



def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.aboutToQuit.connect(lambda: os._exit(0))

    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()