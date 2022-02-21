"""
TTOpenGL - Wrapper types and utils between QOpenGLWidget and PyOpenGL.
Released under the MIT License:

Copyright 2021 Trevor van Hoof

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
from .framebuffer import RenderTarget
from .texture import Texture2DDescription, Texture3DDescription, TextureCubeDescription, \
    Texture2D, Texture3D, TextureCube, Channels, Format, Texture2DFileDescription
from .mesh import IndexedMesh, Mesh, Buffer, VertexAttribute, loadBinaryMesh
from .program import Material, ComputeMaterial
from .camera_control import CameraEventFilter
from. camera import Camera, ZUpCamera