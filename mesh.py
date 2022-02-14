from typing import *
from OpenGL.GL import *
from core import GLObject


class VertexAttributeSemantic:
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
    COLOR0 = 11
    # COLOR# = COLOR0 + i


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


class MeshBase(object):
    def __init__(self, attributeLayout, drawCount, vertexBuffer, indexBuffer=None):
        self._vertexBuffer = vertexBuffer
        self._indexBuffer = indexBuffer

        # initialize the VAO
        self._handle = glGenVertexArrays(1)
        glBindVertexArray(self._handle)
        vertexBuffer.bind(GL_ARRAY_BUFFER)
        if indexBuffer is not None:
            indexBuffer.bind(GL_ELEMENT_ARRAY_BUFFER)

        # initialize the attribute bindings
        stride = 4 * sum(pair[1] for pair in attributeLayout)
        cursor = 0
        for semantic, numFloats in attributeLayout:
            glVertexAttribPointer(semantic, numFloats, GL_FLOAT, False, stride, ctypes.c_void_p(cursor))
            glEnableVertexAttribArray(semantic)
            cursor += numFloats * 4

        # clean up
        glBindVertexArray(0)
        vertexBuffer.unbind()
        if indexBuffer is not None:
            indexBuffer.unbind()

        # drawing args are globally modifiable
        # we would need to know the vertex stride when drawing unindexed
        self._count = drawCount
        self._mode = GL_TRIANGLES
        self._indexType = GL_UNSIGNED_INT

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, count):
        if self._indexBuffer is None:
            # TODO: this count can not be properly bounds-checked right now,
            pass
        else:
            numIndices = self._indexBuffer.size // {GL_UNSIGNED_BYTE: 1, GL_UNSIGNED_SHORT: 2, GL_UNSIGNED_INT: 4}[self._indexType]
            assert 0 <= count < numIndices
        self._count = count

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, glEnum):
        assert glEnum in (GL_POINTS, GL_LINES, GL_TRIANGLES, GL_LINE_STRIP, GL_LINE_LOOP, GL_TRIANGLE_STRIP, GL_TRIANGLE_FAN)
        self._mode = glEnum

    @property
    def indexType(self):
        return self._indexType

    @indexType.setter
    def indexType(self, glEnum):
        assert glEnum in (GL_UNSIGNED_BYTE, GL_UNSIGNED_SHORT, GL_UNSIGNED_INT)
        self._indexType = glEnum

    def draw(self):
        glBindVertexArray(self._handle)
        if self._indexBuffer is None:
            # TODO: this count can not be properly bounds-checked right now,
            glDrawArrays(self.mode, 0, self._count)
        else:
            glDrawElements(self.mode, self._count, self._indexType, None)


class StaticMesh(MeshBase):
    def __init__(self, attributeLayout, vertexData, indexDataOrDrawCount):
        if not isinstance(indexDataOrDrawCount, int):
            if isinstance(indexDataOrDrawCount, bytes):
                count = len(indexDataOrDrawCount) // 4
            else:
                count = ctypes.sizeof(indexDataOrDrawCount) // 4
            super().__init__(attributeLayout, count,
                             Buffer(GL_ARRAY_BUFFER, vertexData, GL_STATIC_DRAW),
                             Buffer(GL_ELEMENT_ARRAY_BUFFER, indexDataOrDrawCount, GL_STATIC_DRAW))
        else:
            count = indexDataOrDrawCount
            super().__init__(attributeLayout, count,
                             Buffer(GL_ARRAY_BUFFER, vertexData, GL_STATIC_DRAW))
