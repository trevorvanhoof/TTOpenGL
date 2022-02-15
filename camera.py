import math
from MMath.mmath import Vec3, Mat44, ERotateOrder
from .core import TSignal


class Camera:
    def __init__(self):
        super().__init__()
        self.changed = TSignal()
        self._translate = Vec3()
        self._rotate = Vec3()  # in radians
        self._horizontalFieldOfViewDegrees = 72.0
        self.near = 0.1
        self.far = 100000.0

    @property
    def near(self):
        return self._near

    @property
    def far(self):
        return self._far

    @near.setter
    def near(self, value):
        self._near = value
        self.changed.emit()

    @far.setter
    def far(self, value):
        self._far = value
        self.changed.emit()

    @property
    def horizontalFieldOfViewDegrees(self):
        return self._horizontalFieldOfViewDegrees

    @horizontalFieldOfViewDegrees.setter
    def horizontalFieldOfViewDegrees(self, value):
        self._horizontalFieldOfViewDegrees = value
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
        hFovRad = math.radians(self._horizontalFieldOfViewDegrees)
        return Mat44.perspectiveX(hFovRad, aspectRatio, self.near, self.far)

    def cameraMatrix(self):
        t = self.translate
        r = self.rotate
        C = Mat44.translateRotate2(t, r, ERotateOrder.XYZ)
        return C


class ZUpCamera(Camera):
    def cameraMatrix(self):
        return super().cameraMatrix() * Mat44.rotateX(math.radians(90.0))
