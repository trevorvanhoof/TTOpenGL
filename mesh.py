from OpenGL.GL import *


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


class StaticMesh(object):
    def __init__(self, name, attributeLayout, vertexData, indexData):
        self.name = name
        self.attributeLayout = attributeLayout
        self.vertexData = vertexData
        self.indexData = indexData
        self.vao = None
        self.vertexBuffer = None
        self.indexBuffer = None
        self.indexCount = len(indexData) // 4

    def ensure_initialized(self):
        if self.vao is not None:
            return
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        self.vertexBuffer, self.indexBuffer = glGenBuffers(2)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertexBuffer)
        glBufferData(GL_ARRAY_BUFFER, len(self.vertexData), self.vertexData, GL_STATIC_DRAW)
        stride = 4 * sum(pair[1] for pair in self.attributeLayout)
        cursor = 0
        for semantic, numFloats in self.attributeLayout:
            glVertexAttribPointer(semantic, numFloats, GL_FLOAT, False, stride, ctypes.c_void_p(cursor))
            glEnableVertexAttribArray(semantic)
            cursor += numFloats * 4
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.indexBuffer)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, len(self.indexData), self.indexData, GL_STATIC_DRAW)

    def draw(self):
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.indexCount, GL_UNSIGNED_INT, None)
