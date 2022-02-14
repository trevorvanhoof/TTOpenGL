from PySide6.QtCore import *
from MMath.mmath import Vec3, Mat44, ERotateOrder
import math


def angleOfView(focalLength, filmWidth: float = 35):  # https://forums.cgsociety.org/t/mel-angle-of-view/1572220
    radians = 2.0 * math.atan(float(filmWidth) / (2.0 * float(focalLength)))
    # print('Camera angle of view: ', math.degrees(radians))
    return radians


class Camera(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._translate = Vec3()
        self._rotate = Vec3()  # in radians
        self._focalLength = 41.509
        self.near = 0.1
        self.far = 100000.0

    @property
    def focalLength(self):
        return self._focalLength

    @focalLength.setter
    def focalLength(self, value):
        self._focalLength = value
        self.changed.emit()

    @property
    def translate(self):
        return self._translate

    @translate.setter
    def translate(self, value):
        self._translate = value
        self.changed.emit()

    @property
    def rotate(self):
        return self._rotate

    @rotate.setter
    def rotate(self, value):
        self._rotate = value
        self.changed.emit()

    def projectionMatrix(self, aspectRatio):
        hFovRad = angleOfView(self.focalLength, 42.666)
        return Mat44.perspectiveX(hFovRad, aspectRatio, self.near, self.far)

    def cameraMatrix(self):
        t = self.translate
        r = self.rotate
        C = Mat44.translateRotate2(t, r, ERotateOrder.XYZ)
        C *= Mat44.rotateX(math.radians(90.0))
        return C
