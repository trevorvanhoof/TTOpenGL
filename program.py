import os
from OpenGL.GL import *
from OpenGL.GL import shaders
from .texture import TextureBase


def _compile_program(self, *paths):
    key = []
    for path in paths:
        path = os.path.abspath(path).lower()  # normalize
        key.append(path)
    key = tuple(key)
    stages = []
    for path in paths:
        ext = os.path.splitext(path)[-1]
        if ext == '.vert':
            enum = GL_VERTEX_SHADER
        elif ext == '.frag':
            enum = GL_FRAGMENT_SHADER
        else:
            raise ValueError()
        with open(path) as fh:
            code = fh.read()
        stages.append(shaders.compileShader(code, enum))
    program = shaders.compileProgram(*stages)
    return program


class MaterialCore(object):
    def __init__(self):
        self._locations = {}
        self._values = {}
        self._texture_counter = 0

    def uniform_location(self, key):
        # cache _locations
        loc = self._locations.get(key, None)
        if loc is None:
            loc = glGetUniformLocation(self._program, key)
            self._locations[key] = loc
        return loc

    def _set_uniform(self, key, value):
        # cache _locations
        loc = self.uniform_location(key)
        if loc == -1:
            return
        # set value of right type
        if isinstance(value, TextureBase):
            glActiveTexture(GL_TEXTURE0 + self._texture_counter)
            value.use()
            glUniform1i(loc, self._texture_counter)
            self._texture_counter += 1
        elif isinstance(value, tuple):
            if isinstance(value[0], int):
                if len(value) == 2:
                    glUniform2i(loc, *value)
                elif len(value) == 3:
                    glUniform3i(loc, *value)
                else:
                    raise ValueError()
            elif isinstance(value[0], float):
                if len(value) == 2:
                    glUniform2f(loc, *value)
                elif len(value) == 3:
                    glUniform3f(loc, *value)
                elif len(value) == 16:
                    glUniformMatrix4fv(loc, 1, False, value)
                else:
                    raise ValueError()
            else:
                raise ValueError()
        elif isinstance(value, int):
            glUniform1i(loc, value)
        elif isinstance(value, float):
            glUniform1f(loc, value)
        else:
            raise ValueError(key, value)

    def use(self):
        self._use()
        self._texture_counter = 0
        for key, value in self._values.items():
            self._set_uniform(key, value)

    def _use(self):
        raise NotImplementedError()

    @property
    def _program(self):
        raise NotImplementedError()


class Material(MaterialCore):
    _active_material = None

    def __init__(self, *paths):
        super().__init__()
        key = []
        for path in paths:
            path = os.path.abspath(path).lower()  # normalize
            key.append(path)
        self._source_paths = tuple(key)
        self.__program = None

    @property
    def _program(self):
        return self.__program

    def _use(self):
        if Material._active_material != self:
            Material._active_material = self
            glUseProgram(self.__program)

    def ensure_initialized(self):
        # ensure the program is compiled in the cache
        self.__program = _compile_program(*self._source_paths)

    def __setattr__(self, key, value):
        if key in ('_Material__program', '_source_paths', '_locations', '_texture_counter', '_values'):
            super(MaterialCore, self).__setattr__(key, value)
            return
        self._values[key] = value
        if self == Material._active_material:
            self._set_uniform(key, value)
