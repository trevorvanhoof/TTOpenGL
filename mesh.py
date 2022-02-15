import struct
import enum
from typing import *
from OpenGL.GL import *
from .core import GLObject


class VertexAttribute:
    class Semantic(enum.Enum):
        POSITION = 0
        NORMAL = 1
        TANGENT = 2
        TEXCOORD0 = 3
        TEXCOORD1 = 4
        TEXCOORD2 = 5
        TEXCOORD3 = 6
        TEXCOORD4 = 7
        TEXCOORD5 = 8
        TEXCOORD6 = 9
        TEXCOORD7 = 10
        BLENDINDICES = 11
        BLENDWEIGHT = 12
        COLOR0 = 13
        # COLOR# = COLOR0 + i

    class Size(enum.Enum):
        Single = 1
        Vec2 = 2
        Vec3 = 3
        Vec4 = 4

    class Type(enum.Enum):
        Float = GL_FLOAT

    def __init__(self, semantic, size, type):
        if isinstance(semantic, str):
            semantic = getattr(VertexAttribute.Semantic, semantic)
        self.semantic: Semantic = VertexAttribute.Semantic(semantic)
        self.size: Size = VertexAttribute.Size(size)
        self.type: Type = VertexAttribute.Type(type)

    def sizeInBytes(self):
        return {VertexAttribute.Type.Float: 4}[self.type] * self.size.value


class Buffer(GLObject):
    def __init__(self, target: int, data: Union[int, bytes, ctypes.Array], mode: int = GL_STATIC_DRAW):
        super().__init__()

        # data must be a ctypes array or bytes or int (representing size of buffer that is not initialized with data)
        self._target = target
        self._currentTarget = None

        if isinstance(data, int):
            self._size = data
            data = None
        elif isinstance(data, bytes):
            self._size = len(data)
        else:
            self._size = ctypes.sizeof(data)

        self._handle = glGenBuffers(1)
        self.bind()
        glBufferData(self._target, self._size, data, mode)
        self.unbind()

    @property
    def size(self):
        return self._size

    def bind(self, overrideTarget: Optional[int] = None):
        assert self._currentTarget is None, self._currentTarget
        target = self._target if overrideTarget is None else overrideTarget
        glBindBuffer(target, self._handle)
        self._currentTarget = target

    def unbind(self):
        assert self._currentTarget is not None
        glBindBuffer(self._currentTarget, 0)
        self._currentTarget = None

    @staticmethod
    def unbindTarget(target: int):
        glBindBuffer(target, 0)


class Mesh(object):
    def __init__(self,
                 attributeLayout: Iterable[VertexAttribute],
                 vertexBuffer: Buffer,
                 indexBuffer: Optional[Buffer] = None,
                 mode: int = GL_TRIANGLES,
                 indexType: int = GL_UNSIGNED_INT):
        self._vertexBuffer: Buffer = vertexBuffer
        self._indexBuffer: Optional[Buffer] = indexBuffer

        self._mode: int = mode
        self._indexType: int = indexType
        self._stride = sum(va.sizeInBytes() for va in attributeLayout)

        # initialize the VAO
        self._handle: int = glGenVertexArrays(1)
        glBindVertexArray(self._handle)
        vertexBuffer.bind(GL_ARRAY_BUFFER)
        if indexBuffer is not None:
            indexBuffer.bind(GL_ELEMENT_ARRAY_BUFFER)

            sz = {GL_UNSIGNED_BYTE: 1, GL_UNSIGNED_SHORT: 2, GL_UNSIGNED_INT: 4}[self._indexType]
            self._count: int = self._indexBuffer.size // sz
        else:
            self._count: int = self._vertexBuffer.size // self._stride

        # initialize the attribute bindings
        cursor = 0
        for va in attributeLayout:
            glVertexAttribPointer(va.semantic.value, va.size.value, va.type.value,
                                  False, self._stride, ctypes.c_void_p(cursor))
            glEnableVertexAttribArray(va.semantic.value)
            cursor += va.sizeInBytes()

        # clean up
        glBindVertexArray(0)
        vertexBuffer.unbind()
        if indexBuffer is not None:
            indexBuffer.unbind()

    @property
    def stride(self):
        return self._stride

    @property
    def vertexBuffer(self):
        return self._vertexBuffer

    @property
    def indexBuffer(self):
        return self._indexBuffer

    @property
    def mode(self):
        return self._mode

    def draw(self):
        glBindVertexArray(self._handle)
        if self._indexBuffer is None:
            # TODO: this count can not be properly bounds-checked right now,
            glDrawArrays(self._mode, 0, self._count)
        else:
            glDrawElements(self._mode, self._count, self._indexType, None)


class IndexedMesh(Mesh):
    def __init__(self, attributeLayout, vertexData, indexDataOrDrawCount,
                 mode: int = GL_TRIANGLES,
                 indexType: int = GL_UNSIGNED_INT):
        vbo = Buffer(GL_ARRAY_BUFFER, vertexData, GL_STATIC_DRAW)
        if not isinstance(indexDataOrDrawCount, int):
            ibo = Buffer(GL_ELEMENT_ARRAY_BUFFER, indexDataOrDrawCount, GL_STATIC_DRAW)
        else:
            ibo = None
        super().__init__(attributeLayout, vbo, ibo, mode, indexType)


def loadBinaryMesh(path):
    """
    See maya_mesh for the file format specification.
    """

    def u32(fh):
        return struct.unpack('<I', fh.read(4))[0]

    meshesByLayout = {}
    with open(path, 'rb') as fh:
        assert fh.read(4) == b'MSH\0', f'Unsupported file format for file "{path}".'
        fh.read(4)
        meshCount = u32(fh)
        for meshIndex in range(meshCount):
            nameLength = u32(fh)
            name = fh.read(nameLength).decode('utf8')
            materialNameLength = u32(fh)
            materialName = fh.read(materialNameLength).decode('utf8')
            attributeCount = u32(fh)
            attributeLayout = []
            key = []
            for attributeIndex in range(attributeCount):
                semanticId = u32(fh)
                numFloats = u32(fh)
                key.append((semanticId, numFloats))
                attributeLayout.append(VertexAttribute(VertexAttribute.Semantic(semanticId),
                                                       VertexAttribute.Size(numFloats),
                                                       VertexAttribute.Type.Float))
            key = tuple(key)
            numFloats = u32(fh)
            numInts = u32(fh)
            vboBlob = fh.read(numFloats * ctypes.sizeof(ctypes.c_float))
            sizeof_uint = ctypes.sizeof(ctypes.c_uint)
            iboBlob = fh.read(numInts * sizeof_uint)
            if key not in meshesByLayout:
                meshesByLayout[key] = attributeLayout, vboBlob, iboBlob
            else:
                prevLayout, prevVboBlob, prevIboBlob = meshesByLayout[key]
                indexData = (ctypes.c_uint * numInts)()
                ctypes.memmove(ctypes.pointer(indexData), iboBlob, ctypes.sizeof(indexData))
                offset = len(prevIboBlob) // sizeof_uint
                for j in range(numInts):
                    indexData[j] += offset
                meshesByLayout[key] = prevLayout, prevVboBlob + vboBlob, prevIboBlob + iboBlob
    return tuple(IndexedMesh(*args) for args in meshesByLayout.values())
