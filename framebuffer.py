from OpenGL.GL import *
from .texture import Texture2D


class Framebuffer(object):
    screen_fbo = None
    screen_width = None
    screen_height = None

    def __init__(self, width, height, *cbo_info):
        self.width = width
        self.height = height
        self.fbo = None
        self.textures = []
        self._texture_bindings = []
        self.depth_texture = None
        self._depth_binding = None
        for channels, data_format in cbo_info:
            self.attach(Texture2D(width, height, channels, data_format), GL_TEXTURE_2D)

    def resize(self, width, height):
        self.width = width
        self.height = height
        for texture in self.textures:
            texture.resize(width, height)
        if self.depth_texture:
            self.depth_texture.resize(width, height)

    def __call__(self, openGLWidget):
        Framebuffer.screen_fbo = openGLWidget.defaultFramebufferObject()
        Framebuffer.screen_width = openGLWidget.width()
        Framebuffer.screen_height = openGLWidget.height()
        return self

    def __enter__(self):
        self.use()
        return self

    def __exit__(self, *args):
        self.unuse_all(Framebuffer.screen_width, Framebuffer.screen_height)

    def attach(self, cbo, gl_enum=GL_TEXTURE_2D):
        assert cbo.width == self.width and cbo.height == self.height

        if cbo.channels == GL_DEPTH_COMPONENT:
            assert self.depth_texture is None
            self.depth_texture = cbo
            self._depth_binding = gl_enum
            if self.fbo is not None:
                self.use(soft=True)
                cbo.ensure_initialized()
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, gl_enum, cbo.tex, 0)
                self.unuse_all()
        elif cbo.channels == GL_DEPTH_STENCIL:
            assert self.depth_texture is None
            self.depth_texture = cbo
            self._depth_binding = gl_enum
            if self.fbo is not None:
                self.use(soft=True)
                cbo.ensure_initialized()
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, gl_enum, cbo.tex, 0)
                self.unuse_all()
        else:
            if self.fbo is not None:
                self.use(soft=True)
                cbo.ensure_initialized()
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + len(self.textures), gl_enum, cbo.tex, 0)
                self.unuse_all()
            self.textures.append(cbo)
            self._texture_bindings.append(gl_enum)

    def iter_use_cube_faces(self):
        # use the Framebuffer to render into
        self.use()
        depth_attach = GL_DEPTH_STENCIL_ATTACHMENT if self.depth_texture and self.depth_texture.channels == GL_DEPTH_STENCIL else GL_DEPTH_ATTACHMENT
        # then for each face of a cube map re-bind all the textures as a different binding enum
        # (assuming self._texture_bindings and self._depth_binding only contain GL_TEXTURE_CUBE_MAP_POSITIVE_X)
        for face in range(6):
            for index, cbo in enumerate(self.textures):
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + index, self._texture_bindings[index] + face, cbo.tex, 0)
            if self.depth_texture:
                glFramebufferTexture2D(GL_FRAMEBUFFER, depth_attach, self._depth_binding + face, self.depth_texture.tex, 0)
            yield face

    def replace_attachment(self, index, cbo, gl_enum=GL_TEXTURE_2D):
        self.use(soft=True)
        cbo.ensure_initialized()
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + index, gl_enum, cbo.tex, 0)
        self.unuse_all()
        self.textures[index] = cbo
        self._texture_bindings[index] = gl_enum

    def ensure_initialized(self):
        if self.depth_texture:
            self.depth_texture.ensure_initialized()
        for cbo in self.textures:
            cbo.ensure_initialized()
        if self.fbo is not None:
            return

        self.fbo = glGenFramebuffers(1)
        self.use(soft=True)
        if self.depth_texture:
            if self.depth_texture.channels == GL_DEPTH_COMPONENT:
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, self._depth_binding, self.depth_texture.tex, 0)
            else:
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, self._depth_binding, self.depth_texture.tex, 0)
        for i, cbo in enumerate(self.textures):
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + i, self._texture_bindings[i], cbo.tex, 0)
        self.unuse_all()

    def use(self, soft=False):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        if not soft:
            glDrawBuffers(len(self.textures), tuple(GL_COLOR_ATTACHMENT0 + i for i in range(len(self.textures))))
            glViewport(0, 0, self.width, self.height)

    @staticmethod
    def unuse_all(screen_width=None, screen_height=None):
        """ Render to the screen. """
        assert Framebuffer.screen_fbo is not None
        glBindFramebuffer(GL_FRAMEBUFFER, Framebuffer.screen_fbo)
        if screen_width:
            glViewport(0, 0, screen_width, screen_height)
