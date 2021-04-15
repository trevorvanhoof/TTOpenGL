from OpenGL.GL import *
from .framebuffer import Framebuffer
import importlib
import os

if 'TTOpenGL_QT_MODULE' in os.environ:
    QtWidgets = importlib.import_module('QtWidgets', os.environ['TTOpenGL_QT_MODULE'])
else:
    from PySide2 import QtWidgets


class Viewport(QtWidgets.QOpenGLWidget):
    def __init__(self):
        super(Viewport, self).__init__()

    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        Framebuffer.screen_width = width
        Framebuffer.screen_height = height
        Framebuffer.screen_fbo = self.defaultFramebufferObject()

    def initializeGL(self):
        Framebuffer.screen_fbo = self.defaultFramebufferObject()
