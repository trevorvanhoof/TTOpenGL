import time
from math import radians
from PySide6.QtCore import *
from PySide6.QtGui import *

from MMath.mmath import Mat44, Float4, Vec3, ERotateOrder


def TransformCore_localTransform(transform):
    return Mat44.translateRotate2(transform.translate, transform.rotate, ERotateOrder.XYZ)


class CameraEventFilter(QObject):
    def __init__(self, camera):
        # panning moves the pivot
        # pressing A moves the pivot to the center of the scene (using bounding boxes)
        # pressing F moves the pivot to the center of the selection (using bounding boxes)
        # scrolling zooms in and out
        # dragging while holding ALT tumbles around the pivot
        super().__init__()

        self.camera = camera
        self.dragAction = 0
        self.marqueeStart = None

        self.pivot = Float4(0.0, 0.0, 0.0, 1.0)
        self.angles = Vec3(radians(-22.5), radians(45.0), radians(0.0))
        self.distance = 10.0
        self.dragStart = None

        self.keys = {
            Qt.Key_W: 0,
            Qt.Key_A: 0,
            Qt.Key_S: 0,
            Qt.Key_D: 0,
            Qt.Key_Q: 0,
            Qt.Key_E: 0,
            Qt.Key_Left: 0,
            Qt.Key_Right: 0,
            Qt.Key_Up: 0,
            Qt.Key_Down: 0,
            Qt.Key_PageUp: 0,
            Qt.Key_PageDown: 0,
            Qt.Key_Home: 0,
            Qt.Key_End: 0,
            None: 0,  # modifier bitmask
        }

        self.tick = QTimer()
        self.tick.timeout.connect(self.flyTick)
        self.tick.start(1000 // 60)
        self.prevTime = time.time()

        self.updateCamera()

    def updateCamera(self):
        matrix = Mat44.rotate(self.angles[0], self.angles[1], 0.0, ERotateOrder.XYZ)
        matrix.cols[3] = matrix.cols[2] * Float4(self.distance) + self.pivot
        tmp = self.camera.changed.blockSignals(True)
        self.camera.translate = matrix.col3
        self.camera.rotate = self.angles
        self.camera.changed.blockSignals(tmp)
        self.camera.changed.emit()

    def eventFilter(self, obj, event):
        if isinstance(event, QWheelEvent):
            return self.wheelEvent(event)
        if isinstance(event, QMouseEvent):
            if event.type() == QEvent.MouseButtonPress:
                return self.mousePressEvent(event)
            if event.type() == QEvent.MouseButtonRelease:
                return self.mouseReleaseEvent(event)
            if event.type() == QEvent.MouseMove:
                return self.mouseMoveEvent(event)
        if isinstance(event, QKeyEvent):
            self.updateModifiers(event)
            if event.type() == QEvent.KeyPress:
                return self.keyPressEvent(event)
            if event.type() == QEvent.KeyRelease:
                return self.keyReleaseEvent(event)
        return False

    def wheelEvent(self, event):
        self.zoom(event)
        return True

    def keyPressEvent(self, event):
        if event.key() in self.keys:
            self.keys[event.key()] = 3
            return True
        return False

    def updateModifiers(self, event):
        ctrl = (event.modifiers() & Qt.ControlModifier) == Qt.ControlModifier
        shift = (event.modifiers() & Qt.ShiftModifier) == Qt.ShiftModifier
        alt = (event.modifiers() & Qt.AltModifier) == Qt.AltModifier
        self.keys[None] = (int(alt) << 2) | (int(ctrl) << 1) | int(shift)

    def keyReleaseEvent(self, event):
        if event.key() in self.keys:
            self.keys[event.key()] = 2
            return True
        return False

    def setCameraPosition(self, t):
        matrix = TransformCore_localTransform(self.camera)
        self.pivot = t - matrix.col2 * self.distance
        self.updateCamera()

    def setCameraRotation(self, r):
        # get current camera position
        matrix = TransformCore_localTransform(self.camera)
        where_it_was = matrix.col3
        # update rotation
        self.angles = r
        self.updateCamera()
        # get new camera position
        matrix = TransformCore_localTransform(self.camera)
        where_it_is = matrix.col3
        # apply the delta to the pivot to move it back into place
        self.pivot += where_it_was - where_it_is
        self.updateCamera()

    def flyTick(self):
        # react to key states
        currentTime = time.time()
        deltaTime = currentTime - self.prevTime
        self.prevTime = currentTime

        if self.keys[None] & 0b100:
            # Alt pressed, ignore fly mode
            return

        tx = float((self.keys[Qt.Key_D] & 1) - (self.keys[Qt.Key_A] & 1))
        ty = float((self.keys[Qt.Key_Q] & 1) - (self.keys[Qt.Key_E] & 1))
        tz = float((self.keys[Qt.Key_S] & 1) - (self.keys[Qt.Key_W] & 1))
        update = False
        if tx or ty or tz:
            matrix = TransformCore_localTransform(self.camera)
            moveSpeed = [8.0, 100.0, 1.0][self.keys[None] % 3]
            self.pivot += (matrix.col0 * tx + matrix.col1 * ty + matrix.col2 * tz) * deltaTime * moveSpeed
            update = True

        rx = float((self.keys[Qt.Key_Up] & 1) - (self.keys[Qt.Key_Down] & 1))
        ry = float((self.keys[Qt.Key_Left] & 1) - (self.keys[Qt.Key_Right] & 1))
        rz = float((self.keys[Qt.Key_Home] & 1) - (self.keys[Qt.Key_End] & 1))
        if rx or ry or rz:
            turnSpeed = [0.8, 4.0, 0.1][self.keys[None] % 3]
            r = self.angles
            r[0] += rx * deltaTime * turnSpeed
            r[1] += ry * deltaTime * turnSpeed
            r[2] += rz * deltaTime * turnSpeed
            self.setCameraRotation(r)
            update = False

        #fovSpeed = [30.0, 100.0, 10.0][self.keys[None] % 3]
        #fl = 0.0
        #fl -= self.keys[Qt.Key_PageUp] * deltaTime * fovSpeed
        #fl += self.keys[Qt.Key_PageDown] * deltaTime * fovSpeed
        #if fl:
        #    self.camera.focalLength = max(0.1, self.camera.focalLength + fl)

        if update:
            self.updateCamera()

        # drop key states
        for key in self.keys:
            if key is None:
                continue
            self.keys[key] &= 1

    def mousePressEvent(self, event):
        if event.modifiers() != Qt.AltModifier:
            if event.button() == Qt.LeftButton:
                self.dragAction = 4
                self.marqueeStart = event.pos()
            return True

        if event.button() == Qt.LeftButton:
            self.dragAction = 1
            self.tumble_start(event)
            return True

        if event.button() == Qt.MiddleButton:
            self.dragAction = 2
            self.pan_start(event)
            return True

        if event.button() == Qt.RightButton:
            self.dragAction = 3
            self.zoom_drag_start(event)
            return True

        return False

    def mouseMoveEvent(self, event):
        if self.dragAction == 1:
            self.tumble(event)
            return True

        if self.dragAction == 2:
            self.pan(event)
            return True

        if self.dragAction == 3:
            self.zoom_drag(event)
            return True

        return False

    def mouseReleaseEvent(self, _):
        if self.dragAction == 0:
            return False
        self.dragAction = 0
        return True

    def tumble_start(self, event):
        self.dragStart = event.pos(), self.angles[:]

    def pan_start(self, event):
        self.dragStart = event.pos(), Float4(*self.pivot.m), TransformCore_localTransform(self.camera).cols[:2]

    def tumble(self, event):
        delta = self.dragStart[0] - event.pos()
        self.angles[0] = self.dragStart[1][0] + delta.y() * 0.005
        self.angles[1] = self.dragStart[1][1] + delta.x() * 0.005
        self.updateCamera()

    def pan(self, event):
        delta = self.dragStart[0] - event.pos()
        self.pivot = self.dragStart[1] + self.dragStart[2][0] * Float4(delta.x() * 0.001 * self.distance) + self.dragStart[2][1] * Float4(-delta.y() * 0.001 * self.distance)
        self.updateCamera()

    def zoom_drag_start(self, event):
        self.dragStart = event.pos(), self.distance

    def zoom_drag(self, event):
        delta = self.dragStart[0] - event.pos()

        if abs(delta.x()) > abs(delta.y()):
            if delta.x() < 0:
                delta = delta.x() - abs(delta.y())
            else:
                delta = delta.x() + abs(delta.y())
        else:
            if delta.y() < 0:
                delta = delta.y() - abs(delta.x())
            else:
                delta = delta.y() + abs(delta.x())

        self.distance = self.dragStart[1] * pow(1.001, delta)
        self.updateCamera()

    def zoom(self, event):
        d = event.angleDelta().y() or event.angleDelta().x()
        self.distance *= pow(1.001, -d)
        self.updateCamera()
