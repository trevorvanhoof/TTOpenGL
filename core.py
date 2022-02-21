import os


class DescriptionBase(object):
    def validate(self):
        return


class GLObject(object):
    def __init__(self):
        self._handle: int = -1

    @property
    def handle(self) -> int:
        return self._handle


class HotReloadUtil(object):
    def __init__(self):
        self._paths = set()
        self.callbacks = []
        if 'TTOpenGL_DISABLE_HOTRELOAD' in os.environ:
            return
        from PySide6.QtCore import QFileSystemWatcher
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._sync)

    def _sync(self, path):
        # keep watching  the path
        # self._watcher.addPath(path)
        # call the path-specific callbacks
        for cb, paths in self.callbacks:
            if path in paths:
                cb()

    def register(self, changedCallback, paths):
        if 'TTOpenGL_DISABLE_HOTRELOAD' in os.environ:
            return
        self.callbacks.append((changedCallback, set(paths)))
        for path in paths:
            # only watch new paths
            if path not in self._paths:
                self._watcher.addPath(path)
                self._paths.add(path)

    def updateFileList(self, changedCallback, paths):
        for i, (cb, oldPaths) in enumerate(self.callbacks):
            if cb == changedCallback:
                self.callbacks[i] = cb, paths


class TSignal(object):
    def __init__(self):
        self.__callbacks = []
        self.__blocked = False

    def blockSignals(self, state):
        tmp = self.__blocked
        self.__blocked = state
        return tmp

    def emit(self, *args):
        if self.__blocked:
            return
        for callback in self.__callbacks:
            callback(*args)

    def connect(self, callback):
        self.__callbacks.append(callback)

    def disconnect(self, callback):
        self.__callbacks.remove(callback)
