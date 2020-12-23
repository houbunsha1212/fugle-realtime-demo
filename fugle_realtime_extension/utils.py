class FugleExtensionUtils(object):

    atexit = __import__("atexit")

    def __init__(self, func, *args, **kwargs):
        self.func = func

        _cls = kwargs.pop("cls", None)
        if _cls:
            self.func.__annotations__ = {"self": _cls}

        if self.func.__annotations__:
            cls = next(iter(self.func.__annotations__.values()))
            self.func.__module__ = cls.__module__
            self.func.__qualname__ = f"{cls.__name__}.{self.func.__name__}"
            _func = self.functools.partial(self.func, cls)
            self.cls = cls
        else:
            _func = self.func
            self.cls = None

        if self.func.__annotations__:
            setattr(cls, self.func.__name__, _func)

        self._func = _func
        self.inspect = __import__("inspect")
        self.functools = __import__("functools")

    def __call__(self, *args, **kwargs):
        f = self.functools.partial(
            self._func,
            *[
                self.cls
                for _arg in self.inspect.getfullargspec(self._func).args
                if _arg == "self"
            ],
        )
        return f(*args, **kwargs)

    def expose(self):
        print(f"expose: {self.func.__name__}")
        return self

    @staticmethod
    def naive_injection(func=None, *args, **kwargs):
        if func:
            return FugleExtensionUtils(func, *args, **kwargs)
        return lambda func: FugleExtensionUtils(func, *args, **kwargs)

    @staticmethod
    def iife(func, *args, **kwargs):
        func(*args, **kwargs)
        return func

    @staticmethod
    def bind(instance, func, target=None):
        if target is None:
            target = func.__name__
        setattr(instance, target, func.__get__(instance, instance.__class__))
        return None

    @staticmethod
    def exit(func, *args, **kwargs):
        FugleExtensionUtils.atexit.register(func, *args, **kwargs)

