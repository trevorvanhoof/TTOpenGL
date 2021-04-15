from OpenGL.GL import *


class Format:
    Uint8 = GL_UNSIGNED_BYTE
    Float16 = GL_HALF_FLOAT
    Float32 = GL_FLOAT
    Depth = GL_FLOAT


class Channels:
    R = GL_RED
    RG = GL_RG
    RGB = GL_RGB
    RGBA = GL_RGBA
    Depth = GL_DEPTH_COMPONENT


_cFormat = {
    Format.Uint8: ctypes.c_byte,
    Format.Float32: ctypes.c_float,
}

_cChannels = {
    Channels.R: 1,
    Channels.RG: 2,
    Channels.RGB: 3,
    Channels.RGBA: 4,
    Channels.Depth: 1
}

_internalFormatMap = {
    (GL_RED, GL_UNSIGNED_BYTE): GL_R8,
    (GL_RG, GL_UNSIGNED_BYTE): GL_RG8,
    (GL_RGB, GL_UNSIGNED_BYTE): GL_RGB8,
    (GL_RGBA, GL_UNSIGNED_BYTE): GL_RGBA8,
    (GL_RED, GL_HALF_FLOAT): GL_R16F,
    (GL_RG, GL_HALF_FLOAT): GL_RG16F,
    (GL_RGB, GL_HALF_FLOAT): GL_RGB16F,
    (GL_RGBA, GL_HALF_FLOAT): GL_RGBA16F,
    (GL_RED, GL_FLOAT): GL_R32F,
    (GL_RG, GL_FLOAT): GL_RG32F,
    (GL_RGB, GL_FLOAT): GL_RGB32F,
    (GL_RGBA, GL_FLOAT): GL_RGBA32F,
    (GL_DEPTH_COMPONENT, GL_FLOAT): GL_DEPTH_COMPONENT,
}


class TextureBase(object):
    def __init__(self, channels=Channels.RGBA, data_format=Format.Uint8):
        self.channels = channels
        self.data_format = data_format
        self.tex = None
        self._tiling = GL_REPEAT

    def ensure_initialized(self):
        if self.tex is None:
            self._initialize()

    @classmethod
    def _gl_enum(cls):
        return GL_TEXTURE_2D

    def setTiling(self, tiling=True):
        self._tiling = GL_REPEAT if tiling else GL_CLAMP_TO_EDGE
        if self.tex is not None:
            self.use()
            glTexParameteri(self._gl_enum(), GL_TEXTURE_WRAP_R, self._tiling)
            glTexParameteri(self._gl_enum(), GL_TEXTURE_WRAP_S, self._tiling)
            glTexParameteri(self._gl_enum(), GL_TEXTURE_WRAP_T, self._tiling)

    def _initialize(self):
        self.tex = glGenTextures(1)
        self.use()
        glTexParameteri(self._gl_enum(), GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_R, self._tiling)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, self._tiling)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, self._tiling)

    def use(self):
        glBindTexture(self._gl_enum(), self.tex)


class Texture2D(TextureBase):
    def __init__(self, width, height, channels=Channels.RGBA, data_format=Format.Uint8, data=None):
        super(Texture2D, self).__init__(channels, data_format)
        self.width = width
        self.height = height
        self.data = data

    def resize(self, width, height):
        self.width = width
        self.height = height
        if self.tex is not None:
            self.use()
            self._allocate()

    def _allocate(self):
        glTexImage2D(GL_TEXTURE_2D, 0, _internalFormatMap[(self.channels, self.data_format)], self.width, self.height, 0, self.channels, self.data_format, self.data)

    def _initialize(self):
        super(Texture2D, self)._initialize()
        self._allocate()

    def read_pixels(self, buffer=None, read_as_format=None):
        self.use()
        if buffer is None:
            buffer = (_cFormat[read_as_format or self.data_format] * (self.width * self.height * _cChannels[self.channels]))()
        glGetTexImage(GL_TEXTURE_2D, 0, self.channels, read_as_format or self.data_format, buffer)
        return buffer
