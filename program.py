import functools
from typing import *
import os
import re
from math import ceil
from MMath.mmath import Mat44
from OpenGL.GL.ARB.compute_variable_group_size import glDispatchComputeGroupSizeARB
from OpenGL.GL import *
from OpenGL.GL import shaders
from .core import HotReloadUtil
from .mesh import Buffer
from .texture import Texture

_programs = {}
_shaders = {}
_regexIncludes = re.compile(rb'^[ \t]*#include "([^"]+)"[ \t]*$', re.MULTILINE)
_textByFile = {}
_shaderWatcher = HotReloadUtil()


def _readWithIncludes(absPath: str, ioPaths: List[str]):
    ioPaths.append(absPath)

    # use cache
    if absPath in _textByFile:
        return _textByFile[absPath]

    # read file
    with open(absPath, 'rb') as fh:
        code = fh.read()

    # inline includes
    chunks = []
    cursor = 0
    for match in _regexIncludes.finditer(code):
        chunks.append(code[cursor:match.start()])
        chunks.append(_readWithIncludes(os.path.join(os.path.dirname(absPath), match.group().decode('utf8')), ioPaths))
        cursor = match.end()
    chunks.append(code[cursor:])

    # update code
    code = b'\n'.join(chunks)

    # fill cache and return
    _textByFile[absPath] = code

    # delete the string from the cache if any of its dependent files change
    _shaderWatcher.register(functools.partial(_textByFile.__delitem__, absPath), ioPaths)

    return chunks


def _compileStage(absPath: str, ioPaths: List[str]) -> int:
    if absPath in _shaders:
        return _shaders[absPath]

    ext = os.path.splitext(absPath)[-1]
    if ext == '.vert':
        enum = GL_VERTEX_SHADER
    elif ext == '.frag':
        enum = GL_FRAGMENT_SHADER
    elif ext == '.geo' or ext == '.geom':
        enum = GL_GEOMETRY_SHADER
    elif ext == '.compute':
        enum = GL_COMPUTE_SHADER
    else:
        raise ValueError('Unknown shader extension %s, could not derive shader stage to compile.' % ext)

    involvedFiles = []
    try:
        stage = shaders.compileShader(_readWithIncludes(absPath, involvedFiles), enum)
    except shaders.ShaderCompilationError as e:
        offset = e.args[0].find('): ', len('Shader compile failure (')) + 3
        errors = e.args[0][offset + 2:-1].encode('ascii').decode('unicode_escape')
        source = e.args[1][0].decode('utf8').splitlines()
        for errorLine in errors.splitlines():
            print(f'\033[0;31m{errorLine}\033[0m')
            ln = int(errorLine[2:errorLine.find(')', 2)]) - 1
            for i in range(ln - 2, ln + 3):
                if 0 <= i < len(source):
                    if i == ln:
                        print(f'\033[0;32m{source[i]}\033[0m')
                    else:
                        print(source[i])
        e.args = [f'Failed to compile shader at {absPath}. Details written to output.']
        raise
    _shaders[absPath] = stage

    # delete the shader from the cache if any of its dependent files change
    _shaderWatcher.register(functools.partial(_shaders.__delitem__, absPath), involvedFiles)
    ioPaths += involvedFiles

    return stage


def _compileProgram(ioPaths: List[str], *paths: str) -> int:
    assert paths
    paths = tuple(os.path.abspath(path) for path in paths)
    if paths in _programs:
        return _programs[paths]

    stages = [_compileStage(path, ioPaths) for path in paths]

    program = shaders.compileProgram(*stages)
    _programs[paths] = program

    # delete the program from the cache if any of its dependent files change
    _shaderWatcher.register(functools.partial(_programs.__delitem__, paths), ioPaths)

    return program


class Material(object):
    _activeProgram: int = None
    _activeMaterial: "Material" = None

    def __init__(self, *paths: str):
        # NOTE: If you add variables here, scroll down to __setattr__ and make sure they are not treated as uniforms!
        self._locations: Dict[str, int] = {}
        self._values: Dict[str, Any] = {}
        self._ssbos: Dict[int, Buffer] = {}
        self._texture_counter: int = 0
        self._paths = paths
        involvedFiles = []
        self._handle: int = _compileProgram(involvedFiles, *paths)

        # recompile the material if any of its dependent files change,
        # the stages and programs should already un-cache themselves before we hit this callback
        _shaderWatcher.register(self.recompile, involvedFiles)

    def recompile(self):
        # invalidate uniform locations
        self._locations.clear()
        # rebuild the program
        involvedFiles = []
        self._handle: int = _compileProgram(involvedFiles, *self._paths)
        # recompile the material if any of its dependent files change,
        # the stages and programs should already un-cache themselves before we hit this callback
        _shaderWatcher.updateFileList(self.recompile, involvedFiles)

    @staticmethod
    def unbind():
        Material._activeMaterial = None
        Material._activeProgram = None

    def setSSBO(self, loc: int, ssbo: Buffer):
        self._ssbos[loc] = ssbo
        if Material._activeMaterial == self:
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, loc, ssbo.handle)

    def uniformLocation(self, key: str):
        # cache _locations
        loc = self._locations.get(key, None)
        if loc is None:
            loc = glGetUniformLocation(self._handle, key)
            self._locations[key] = loc
        return loc

    def _setUniform(self, key: str, value: Any):
        # cache _locations
        loc = self.uniformLocation(key)
        if loc == -1:
            return
        # set value of right type
        if isinstance(value, Texture):
            glActiveTexture(GL_TEXTURE0 + self._texture_counter)
            value.bind()
            glUniform1i(loc, self._texture_counter)
            self._texture_counter += 1
        elif isinstance(value, tuple):
            if isinstance(value[0], int):
                if len(value) == 2:
                    glUniform2i(loc, *value)
                elif len(value) == 3:
                    glUniform3i(loc, *value)
                elif len(value) == 4:
                    glUniform4i(loc, *value)
                else:
                    raise ValueError()
            elif isinstance(value[0], float):
                if len(value) == 2:
                    glUniform2f(loc, *value)
                elif len(value) == 3:
                    glUniform3f(loc, *value)
                elif len(value) == 4:
                    glUniform4f(loc, *value)
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
        elif isinstance(value, Mat44):
            glUniformMatrix4fv(loc, 1, False, value.m)
        else:
            raise ValueError(key, value)

    def use(self):
        self._texture_counter = 0
        if Material._activeProgram != self._handle:
            Material._activeProgram = self._handle
            glUseProgram(self._handle)
        if Material._activeMaterial != self:
            Material._activeMaterial = self
            for key, value in self._values.items():
                self._setUniform(key, value)
            for loc, ssbo in self._ssbos.items():
                glBindBufferBase(GL_SHADER_STORAGE_BUFFER, loc, ssbo.handle)

    def __setattr__(self, key: str, value: Any):
        if key in ('_handle', '_paths', '_locations', '_texture_counter', '_values', '_ssbos'):
            super(Material, self).__setattr__(key, value)
            return
        self._values[key] = value
        if self == Material._activeMaterial:
            self._setUniform(key, value)


class ComputeMaterial(Material):
    def __init__(self, computePath: str):
        super().__init__(computePath)

    def dispatch(self, totalSizeOrNumWorkgroups: Tuple[int, int, int],
                 workGroupSize: Optional[Tuple[int, int, int]] = None):
        # make sure this material is used
        self.use()
        if workGroupSize is None:
            x, y, z = totalSizeOrNumWorkgroups
            glDispatchCompute(x, y, z)
        else:
            x = int(ceil(totalSizeOrNumWorkgroups[0] // workGroupSize[0]))
            y = int(ceil(totalSizeOrNumWorkgroups[1] // workGroupSize[1]))
            z = int(ceil(totalSizeOrNumWorkgroups[2] // workGroupSize[2]))
            glDispatchComputeGroupSizeARB(x, y, z, *workGroupSize)

    def dispatchAndWait(self, barriers: int, totalSizeOrNumWorkgroups: Tuple[int, int, int],
                        workGroupSize: Optional[Tuple[int, int, int]] = None):
        self.dispatch(totalSizeOrNumWorkgroups, workGroupSize)
        glMemoryBarrier(barriers)
