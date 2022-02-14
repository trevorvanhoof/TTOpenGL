"""
Cube map faces are ordered:
0: +X
1: -X
2: +Y
3: -Y
4: +Z
5: -Z
Note you can do:
'XYZ'[cubeFace>>1]
'+-'[cubeFace&1]
"""
from OpenGL.GL import *
import enum
import math
import os
from typing import *
from .core import DescriptionBase, GLObject


class Format(enum.Enum):
    Uint8 = GL_UNSIGNED_BYTE
    Float16 = GL_HALF_FLOAT
    Float32 = GL_FLOAT
    Depth = GL_FLOAT


class Channels(enum.Enum):
    R = GL_RED
    RG = GL_RG
    RGB = GL_RGB
    RGBA = GL_RGBA
    Depth = GL_DEPTH_COMPONENT
    R_I = GL_RED_INTEGER
    RG_I = GL_RG_INTEGER
    RGB_I = GL_RGB_INTEGER
    RGBA_I = GL_RGBA_INTEGER
    R_UI = GL_RED_INTEGER
    RG_UI = GL_RG_INTEGER
    RGB_UI = GL_RGB_INTEGER
    RGBA_UI = GL_RGBA_INTEGER


_cFormat = {
    Format.Uint8: ctypes.c_byte,
    Format.Float32: ctypes.c_float,
}

_cChannels = {
    Channels.R: 1,
    Channels.RG: 2,
    Channels.RGB: 3,
    Channels.RGBA: 4,
    Channels.Depth: 1,
    Channels.R_I: 1,
    Channels.RG_I: 2,
    Channels.RGB_I: 3,
    Channels.RGBA_I: 4,
    Channels.R_UI: 1,
    Channels.RG_UI: 2,
    Channels.RGB_UI: 3,
    Channels.RGBA_UI: 4
}

_internalFormatMap = {
    (Channels.R, Format.Uint8): GL_R8,
    (Channels.RG, Format.Uint8): GL_RG8,
    (Channels.RGB, Format.Uint8): GL_RGB8,
    (Channels.RGBA, Format.Uint8): GL_RGBA8,
    (Channels.R, Format.Float16): GL_R16F,
    (Channels.RG, Format.Float16): GL_RG16F,
    (Channels.RGB, Format.Float16): GL_RGB16F,
    (Channels.RGBA, Format.Float16): GL_RGBA16F,
    (Channels.R, Format.Float32): GL_R32F,
    (Channels.RG, Format.Float32): GL_RG32F,
    (Channels.RGB, Format.Float32): GL_RGB32F,
    (Channels.RGBA, Format.Float32): GL_RGBA32F,
    (Channels.Depth, Format.Float32): GL_DEPTH_COMPONENT,
    (Channels.R_I, Format.Uint8): GL_R8I,
    (Channels.RG_I, Format.Uint8): GL_RG8I,
    (Channels.RGB_I, Format.Uint8): GL_RGB8I,
    (Channels.RGBA_I, Format.Uint8): GL_RGBA8I,
    (Channels.R_UI, Format.Uint8): GL_R8UI,
    (Channels.RG_UI, Format.Uint8): GL_RG8UI,
    (Channels.RGB_UI, Format.Uint8): GL_RGB8UI,
    (Channels.RGBA_UI, Format.Uint8): GL_RGBA8UI,
}


class TextureDescriptionBase(DescriptionBase):
    @classmethod
    def glEnum(cls):
        raise NotImplementedError()

    def sizes(self) -> Tuple[int, ...]:
        raise NotImplementedError()

    def __init__(self,
                 channels: Channels = Channels.RGBA,
                 dataFormat: Format = Format.Uint8,
                 tiling: bool = True,
                 mipMaps: bool = False,
                 linearFiltering: bool = True):
        self.channels: Channels = channels
        self.dataFormat: Format = dataFormat
        self.tilingX: bool = tiling
        self.tilingY: bool = tiling
        self.mipMaps: bool = mipMaps
        self.linearFiltering: bool = linearFiltering

    def __call__(self):
        raise NotImplementedError()


class Texture2DDescription(TextureDescriptionBase):
    @classmethod
    def glEnum(cls):
        return GL_TEXTURE_2D

    def sizes(self) -> Tuple[int, ...]:
        return self.width, self.height

    def __init__(self, width: int, height: int, data: Union[None, bytes, List[bytes]] = None, channels=Channels.RGBA,
                 dataFormat=Format.Uint8, tiling=True, mipMaps=False, linearFiltering=True):
        super().__init__(channels, dataFormat, tiling, mipMaps, linearFiltering)
        self.width: int = width
        self.height: int = height
        # data can be a list of mip map datas, or just a mip0 data
        self.data: Union[None, bytes, List[bytes]] = data

    def validate(self):
        _validateData(self, self.data, self.width, self.height)

    def __call__(self):
        return Texture2D(self)


class Texture2DFileDescription(TextureDescriptionBase):
    @classmethod
    def glEnum(cls):
        return GL_TEXTURE_2D

    def sizes(self) -> Tuple[int, ...]:
        raise NotImplementedError()

    def __init__(self, filePath: str, channels: Channels = Channels.RGBA, dataFormat: Format = Format.Uint8,
                 tiling: bool = True, mipMaps: bool = False, linearFiltering: bool = True):
        super().__init__(channels, dataFormat, tiling, mipMaps, linearFiltering)
        self.filePath: str = filePath

    def validate(self):
        assert os.path.exists(self.filePath)
        # We may lift this restriction for certain file types later
        assert self.channels in (
            Channels.RGB, Channels.RGBA, Channels.RGB_I, Channels.RGBA_I, Channels.RGB_UI, Channels.RGBA_UI)
        assert self.dataFormat == Format.Uint8

    def convert(self) -> Texture2DDescription:
        self.validate()
        from PySide6.QtGui import QImage
        img = QImage(self.filePath)
        n = _cChannels[self.channels]
        if n == 3:
            img = img.convertToFormat(QImage.Format_RGB888)
        elif n == 4:
            img = img.convertToFormat(QImage.Format_RGBA8888)
        else:
            raise RuntimeError()
        # noinspection PyTypeChecker
        bits: memoryview = img.constBits()
        # noinspection PyTypeChecker
        byts: bytes = bits.tobytes()
        desc = Texture2DDescription(img.width(), img.height(), byts, self.channels, Format.Uint8,
                                    self.tilingX, self.mipMaps, self.linearFiltering)
        desc.tilingY = self.tilingY
        return desc

    def __call__(self):
        return self.convert()()


def _validateData(description: TextureDescriptionBase,
                  data: Union[None, bytes, List[bytes], List[List[bytes]]],
                  *size: int):
    if data is not None:
        bytesPerPixel = ctypes.sizeof(_cFormat[description.dataFormat]) * _cChannels[description.channels]
        if isinstance(data, list):
            assert len(data) > 0
            if not description.mipMaps:
                assert len(data) == 1
            prevBlobSize = None
            for level, blob in enumerate(data):
                blobSize = bytesPerPixel
                for sz in size:
                    blobSize *= max(1, sz >> level)
                assert blobSize != prevBlobSize, f'Identical mip levels found, was previous level 1 pixel?:' \
                                                 f' {prevBlobSize == bytesPerPixel}'
                assert len(blob) == blobSize
                prevBlobSize = blobSize
        else:
            blobSize = bytesPerPixel
            for sz in description.sizes():
                blobSize *= sz
            assert len(data) == blobSize


class TextureCubeDescription(TextureDescriptionBase):
    @classmethod
    def glEnum(cls):
        return GL_TEXTURE_CUBE_MAP

    def sizes(self) -> Tuple[int, ...]:
        return self.size,

    def __init__(self, size: int, data: Union[None, List[bytes], List[List[bytes]]] = None, channels=Channels.RGBA,
                 dataFormat=Format.Uint8, tiling=True, mipMaps=False, linearFiltering=True):
        super().__init__(channels, dataFormat, tiling, mipMaps, linearFiltering)
        self.size: int = size
        # data can be 6 lists of mip map datas, or just 6 mip0 datas
        self.data: Union[None, List[bytes], List[List[bytes]]] = data

    def validate(self):
        if self.data is not None:
            assert len(self.data) == 6
            for i in range(6):
                assert len(self.data[i]) == len(self.data[0])
                _validateData(self, self.data[i], self.size)

    def __call__(self):
        return TextureCube(self)


class Texture3DDescription(TextureDescriptionBase):
    @classmethod
    def glEnum(cls):
        return GL_TEXTURE_3D

    def sizes(self) -> Tuple[int, ...]:
        return self.width, self.height, self.depth

    def __init__(self, width: int, height: int, depth: int, data: Union[None, bytes, List[bytes]] = None,
                 channels=Channels.RGBA, dataFormat=Format.Uint8, tiling=True, mipMaps=False, linearFiltering=True):
        super().__init__(channels, dataFormat, tiling, mipMaps, linearFiltering)
        self.tilingZ: bool = tiling
        self.width: int = width
        self.height: int = height
        self.depth: int = depth
        # data can be a list of mip map datas, or just a mip0 data
        self.data: Union[None, bytes, List[bytes]] = data

    def validate(self):
        _validateData(self, self.data, self.width, self.height, self.depth)

    def __call__(self):
        return Texture3D(self)


def _data(description: Union[None, Texture2DDescription, TextureCubeDescription, Texture3DDescription], mipLevel: int,
          cubeFace: int = -1) -> Optional[bytes]:
    if description is None:
        return
    if description.data is None:
        return
    data = description.data
    if description.glEnum() == GL_TEXTURE_CUBE_MAP:
        assert 0 <= cubeFace < 6
        data = data[cubeFace]
    else:
        assert cubeFace == -1
    if isinstance(data, list):
        if 0 <= mipLevel < len(data):
            return data[mipLevel]
    elif mipLevel == 0:
        return data


def _numMipLevels(*size: int) -> int:
    return int(math.log2(max(size))) + 1


def _texImage2D(target: int, internalFormat: int, width: int, height: int, channels: int, dataFormat: int,
                data: Optional[bytes], resizable: bool):
    if resizable:
        glTexImage2D(target, 0, internalFormat, width, height, 0, channels, dataFormat, data)
    else:
        glTexStorage2D(target, 1, internalFormat, width, height)
        if data is not None:
            glTexSubImage2D(target, 0, 0, 0, width, height, channels, dataFormat, data)


def _texImage3D(target: int, internalFormat: int, width: int, height: int, depth: int, channels: int, dataFormat: int,
                data: Optional[bytes], resizable: bool):
    if resizable:
        glTexImage3D(target, 0, internalFormat, width, height, depth, 0, channels, dataFormat, data)
    else:
        glTexStorage3D(target, 1, internalFormat, width, height, depth)
        if data is not None:
            glTexSubImage3D(target, 0, 0, 0, width, height, depth, channels, dataFormat, data)


class Texture(GLObject):
    def __init__(self, description: TextureDescriptionBase):
        super().__init__()
        if isinstance(description, Texture2DFileDescription):
            description = description.convert()
        description.validate()
        self._glEnum: int = description.glEnum()
        self._handle: int = glGenTextures(1)
        self.bind()
        if description.linearFiltering:
            if not description.mipMaps:
                glTexParameteri(self._glEnum, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(self._glEnum, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            else:
                glTexParameteri(self._glEnum, GL_TEXTURE_MAG_FILTER, GL_LINEAR_MIPMAP_LINEAR)
                glTexParameteri(self._glEnum, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        else:
            if not description.mipMaps:
                glTexParameteri(self._glEnum, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(self._glEnum, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            else:
                glTexParameteri(self._glEnum, GL_TEXTURE_MAG_FILTER, GL_NEAREST_MIPMAP_LINEAR)
                glTexParameteri(self._glEnum, GL_TEXTURE_MIN_FILTER, GL_NEAREST_MIPMAP_LINEAR)
        glTexParameteri(self._glEnum, GL_TEXTURE_WRAP_S, GL_REPEAT if description.tilingX else GL_CLAMP_TO_EDGE)
        glTexParameteri(self._glEnum, GL_TEXTURE_WRAP_T, GL_REPEAT if description.tilingY else GL_CLAMP_TO_EDGE)
        self._channels: Channels = description.channels
        self._dataFormat: Format = description.dataFormat
        self._mipMaps: bool = description.mipMaps
        self._resizable: bool = description.data is None
        if isinstance(description, Texture3DDescription):
            glTexParameteri(self._glEnum, GL_TEXTURE_WRAP_R, GL_REPEAT if description.tilingZ else GL_CLAMP_TO_EDGE)
        self._size: Tuple[int, ...] = description.sizes()
        self._allocate(description)

    @property
    def size(self):
        return self._size

    @property
    def resizable(self) -> bool:
        return self._resizable

    @property
    def channels(self) -> Channels:
        return self._channels

    @property
    def glEnum(self) -> int:
        return self._glEnum

    @property
    def numMipLevels(self) -> int:
        return _numMipLevels(*self._size)

    def _setImageAndGenerateMips(self, internalFormat: int, description: Optional[TextureDescriptionBase] = None):
        raise NotImplementedError()

    def _uploadMips(self, description: TextureDescriptionBase):
        raise NotImplementedError()

    def setPixels(self, mipLevel: int, data: bytes, cubeMapFace: int = -1):
        raise NotImplementedError()

    def _allocate(self, description: Optional[TextureDescriptionBase] = None):
        internalFormat = _internalFormatMap[(self._channels, self._dataFormat)]
        # upload mip0 and generate mips
        self._setImageAndGenerateMips(internalFormat, description)
        # resizeable textures do not upload any data
        if description is None or not self._mipMaps:
            return
        # copy data into mips
        self._uploadMips(description)

    def resize(self, *size: int):
        assert len(size) == len(self._size), 'Wrong number of arguments when resizing %s' % self._glEnum
        assert self._resizable, 'Can not resize textures that were initialized from data, it would clear the data'
        self._size = size
        self.bind()
        self._allocate()

    def numPixels(self, mipLevel: int = 0) -> int:
        r = 1
        for sz in self._size:
            r *= max(1, sz >> mipLevel)
        return r

    def readPixels(self, buffer: Any = None, readAsFormat: Optional[Format] = None, mipLevel: int = 0) -> Any:
        self.bind()
        assert 0 <= mipLevel < _numMipLevels(*self._size)
        if buffer is None:
            buffer = (_cFormat[readAsFormat or self._dataFormat.value] * (
                    self.numPixels(mipLevel) * _cChannels[self._channels.value]))()
        glGetTexImage(self._glEnum, 0, self._channels.value, readAsFormat or self._dataFormat.value, buffer)
        return buffer

    def bind(self):
        glBindTexture(self._glEnum, self._handle)


class Texture2D(Texture):
    @property
    def width(self) -> int:
        return self._size[0]

    @property
    def height(self) -> int:
        return self._size[1]

    def _setImageAndGenerateMips(self, internalFormat: int, description: Optional[TextureDescriptionBase] = None):
        _texImage2D(self._glEnum, internalFormat, self._size[0], self._size[1], self._channels.value,
                    self._dataFormat.value, _data(description, 0), self._resizable)
        # allocate mipmaps
        if self._mipMaps:
            glGenerateMipmap(self._glEnum)

    def _uploadMips(self, description: Texture2DDescription):
        # copy data into mips
        mipLevels = _numMipLevels(*self._size)
        for level in range(1, mipLevels):
            data = _data(description, level)
            if data:
                width, height = tuple(max(1, sz >> level) for sz in self._size)
                glTexSubImage2D(self._glEnum, level, 0, 0, width, height, self._channels.value, self._dataFormat.value,
                                data)

    def setPixels(self, mipLevel: int, data: bytes, cubeMapFace: int = -1):
        assert 0 <= mipLevel < _numMipLevels(*self._size)
        assert cubeMapFace == -1
        self.bind()
        width, height = tuple(max(1, sz >> mipLevel) for sz in self._size)
        glTexSubImage2D(self._glEnum, mipLevel, 0, 0, width, height, self._channels.value, self._dataFormat.value, data)


class Texture3D(Texture):
    @property
    def width(self) -> int:
        return self._size[0]

    @property
    def height(self) -> int:
        return self._size[1]

    @property
    def depth(self) -> int:
        return self._size[2]

    def _setImageAndGenerateMips(self, internalFormat: int, description: Optional[TextureDescriptionBase] = None):
        _texImage3D(self._glEnum, internalFormat, self._size[0], self._size[1], self._size[2], self._channels.value,
                    self._dataFormat.value, _data(description, 0), self._resizable)
        # allocate mipmaps
        if self._mipMaps:
            glGenerateMipmap(self._glEnum)

    def _uploadMips(self, description: Texture3DDescription):
        # copy data into mips
        mipLevels = _numMipLevels(*self._size)
        for level in range(1, mipLevels):
            data = _data(description, level)
            if data:
                width, height, depth = tuple(max(1, sz >> level) for sz in self._size)
                glTexSubImage3D(self._glEnum, level, 0, 0, width, height, depth, self._channels.value,
                                self._dataFormat.value, data)

    def setPixels(self, mipLevel: int, data: bytes, cubeMapFace: int = -1):
        assert cubeMapFace == -1
        self.bind()
        width, height, depth = tuple(max(1, sz >> mipLevel) for sz in self._size)
        glTexSubImage3D(self._glEnum, mipLevel, 0, 0, width, height, depth, self._channels.value,
                        self._dataFormat.value, data)


class TextureCube(Texture):
    @property
    def width(self) -> int:
        return self._size[0]

    @property
    def height(self) -> int:
        return self._size[0]

    def _setImageAndGenerateMips(self, internalFormat: int, description: Optional[TextureDescriptionBase] = None):
        internalFormat = _internalFormatMap[(self._channels, self._dataFormat)]
        for face in range(6):
            # allocate mip0
            _texImage2D(GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, internalFormat, self._size[0], self._size[0],
                        self._channels.value, self._dataFormat.value, _data(description, 0, face), self._resizable)
            # allocate mipmaps
            if self._mipMaps:
                glGenerateMipmap(GL_TEXTURE_CUBE_MAP_POSITIVE_X + face)

    def _uploadMips(self, description: TextureCubeDescription):
        # copy data into mips
        mipLevels = _numMipLevels(*self._size)
        for face in range(6):
            for level in range(1, mipLevels):
                data = _data(description, level, face)
                if data:
                    size = max(1, self._size[0] >> level)
                    glTexSubImage2D(GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, 0, 0, size, size,
                                    self._channels.value, self._dataFormat.value, data)

    def setPixels(self, mipLevel: int, data: bytes, cubeMapFace: int = -1):
        assert 0 <= cubeMapFace < 6
        self.bind()
        size = tuple(max(1, sz >> mipLevel) for sz in self._size)[0]
        glTexSubImage2D(GL_TEXTURE_CUBE_MAP_POSITIVE_X + cubeMapFace, mipLevel, 0, 0, size, size,
                        self._channels.value, self._dataFormat.value, data)
