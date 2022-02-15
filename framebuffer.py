from typing import *
from contextlib import contextmanager
from OpenGL.GL import *
from .core import GLObject
from .texture import Texture, Channels


class RenderTarget(GLObject):
    def __init__(self, width: int, height: int, resizable: bool = False):
        super().__init__()
        self._handle: int = glGenFramebuffers(1)
        self._resizable = resizable
        self._width = width
        self._height = height
        self._textures = []
        self._depthTextureId = -1

    def resize(self, width: int, height: int):
        assert self._resizable
        if width == self._width and height == self._height:
            return
        self._width = width
        self._height = height
        for texture in self._textures:
            texture.resize(width, height)

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self._handle)
        numCbos = len(self._textures) - int(self._depthTextureId != -1)
        glDrawBuffers(numCbos, tuple(GL_COLOR_ATTACHMENT0 + i for i in range(numCbos)))
        glViewport(0, 0, self._width, self._height)

    @staticmethod
    def unbind(screenBackbufferHandle: int, screenWidth: int, screenHeight: int):
        glBindFramebuffer(GL_FRAMEBUFFER, screenBackbufferHandle)
        glViewport(0, 0, screenWidth, screenHeight)

    @contextmanager
    def renderInto(self, screenBackbufferHandle: int, screenWidth: int, screenHeight: int):
        self.bind()
        yield
        self.unbind(screenBackbufferHandle, screenWidth, screenHeight)

    def replace(self, colorBufferIndex, texture: Texture):
        glBindFramebuffer(GL_FRAMEBUFFER, self._handle)

        if colorBufferIndex == -1:
            assert texture.channels == Channels.Depth
            assert self._depthTextureId != -1
            self._textures[self._depthTextureId] = texture
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, texture.glEnum, texture.handle, 0)
            return

        assert texture.channels != Channels.Depth
        index = colorBufferIndex
        if self._depthTextureId != -1 and index >= self._depthTextureId:
            index += 1
        assert 0 <= index < len(self._textures), index
        self._textures[index] = texture
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + colorBufferIndex, texture.glEnum, texture.handle, 0)

    def attach(self, texture: Texture):
        assert texture.resizable == self._resizable
        glBindFramebuffer(GL_FRAMEBUFFER, self._handle)
        if texture.channels == Channels.Depth:
            self._depthTextureId = len(self._textures)
            self._textures.append(texture)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, texture.glEnum, texture.handle, 0)
        else:
            cboId = len(self._textures)
            if self._depthTextureId != -1:
                cboId -= 1
            self._textures.append(texture)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + cboId, texture.glEnum, texture.handle, 0)

    def depthBuffer(self) -> Optional[Texture]:
        if self._depthTextureId == -1:
            return None
        return self._textures[self._depthTextureId]

    def colorBuffer(self, index: int) -> Optional[Texture]:
        if self._depthTextureId != -1 and index >= self._depthTextureId:
            index += 1
        assert 0 <= index < len(self._textures)
        return self._textures[index]
