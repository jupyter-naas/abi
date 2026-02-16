from typing import Callable, Any


class LazyLoader:
    loaded: bool
    loader: Callable
    value: Any

    def __init__(self, loader: Callable):
        self.loaded = False
        self.loader = loader
        self.value = None

    def is_loaded(self):
        return self.loaded

    def __getattr__(self, name):
        if not self.loaded:
            self.value = self.loader()
            self.loaded = True
        return getattr(self.value, name)

    def __iter__(self):
        if not self.loaded:
            self.value = self.loader()
            self.loaded = True
        return iter(self.value)

    def __len__(self):
        if not self.loaded:
            self.value = self.loader()
            self.loaded = True
        return len(self.value)

    def __getitem__(self, key):
        if not self.loaded:
            self.value = self.loader()
            self.loaded = True
        return self.value[key]

    def __repr__(self):
        if not self.loaded:
            self.value = self.loader()
            self.loaded = True
        return repr(self.value)
