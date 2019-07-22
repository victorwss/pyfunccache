from functools import wraps
import datetime
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, cast, Dict, Generic, Iterator, Optional, Sequence, Tuple, Type, TypeVar
from dataclasses import dataclass
from .cache import Cache, ConcurrentCache, ResultLine

R = TypeVar("R")

@dataclass(frozen = True)
class CallParams:
    real_self: Optional[object]
    args: Sequence[Any]
    kwargs: Dict[str, Any]

    @staticmethod
    def create(real_self: Optional[object], args: Sequence[Any], kwargs: Dict[str, Any]) -> "CallParams":
        return CallParams(CallParams.__freeze(real_self), CallParams.__freeze(args), CallParams.__freeze(kwargs))

    @staticmethod
    def __freeze(d: Any) -> Any:
        if isinstance(d, dict):
            return frozenset((key, CallParams.__freeze(value)) for key, value in d.items())
        elif isinstance(d, list):
            return tuple(CallParams.__freeze(value) for value in d)
        return d

class MemoizedFunction(Generic[R]):
    def __init__(self, real_self: Optional[object], wrapped: Callable[..., R], memoize_exceptions: bool, cache: Cache[CallParams, R]) -> None:

        if type(wrapped) is staticmethod:
            wrapped = cast(staticmethod, wrapped).__func__

        @wraps(wrapped)
        def wrapped_call(*args: Any, **kwargs: Any) -> R:
            if real_self is None:
                return wrapped(*args, **kwargs)
            return wrapped(real_self, *args, **kwargs)

        @wraps(wrapped)
        def forced(*args: Any, **kwargs: Any) -> R:
            f = CallParams.create(real_self, args, kwargs)
            def inner(line: ResultLine[R]) -> R:
                try:
                    rv: R = wrapped_call(*args, **kwargs)
                    cache.save(f, rv)
                    return rv
                except BaseException as x:
                    if not memoize_exceptions and not line.empty: return line.result
                    if memoize_exceptions: cache.save_exception(f, x)
                    raise x
            return cache.with_line(f, inner)

        @wraps(wrapped)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            f = CallParams.create(real_self, args, kwargs)
            def inner(line: ResultLine[R]) -> R:
                if line.empty:
                    return cast(R, forced(*args, **kwargs))
                return line.result
            return cache.with_line(f, inner)

        self.__real_self: object = real_self
        self.__forced: Callable[..., R] = forced
        self.__cache: Cache[CallParams, R] = cache
        self.__wrapped: Callable[..., R] = wrapped_call
        self.__wrapper: Callable[..., R] = wrapper

    @property
    def wrapped(self) -> Callable[..., R]:
         return self.__wrapped

    @property
    def cache(self) -> Cache[CallParams, R]:
         return self.__cache

    @property
    def forced(self) -> Callable[..., R]:
         return self.__forced

    def __call__(self, *args: Any, **kwargs: Any) -> R:
        return self.__wrapper(*args, **kwargs)

class MemoizedFunctionWrapper(Generic[R]):
    def __init__(self, wrapped: Callable[..., R], memoize_exceptions: bool, cache: Cache[CallParams, R]) -> None:
        self.__wrapped: Callable[..., R] = wrapped
        self.__memoize_exceptions: bool = memoize_exceptions
        self.__cache: Cache[CallParams, R] = cache

    def __get__(self, obj: Optional[object], objtype: Optional[object] = None) -> MemoizedFunction[R]:
        if self.__wrapped is None:
            raise AttributeError("unreadable attribute")
        return MemoizedFunction(obj, self.__wrapped, self.__memoize_exceptions, self.__cache)

    @property
    def wrapped(self) -> Callable[..., R]:
         return self.__get__(None, None).wrapped

    @property
    def cache(self) -> Cache[CallParams, R]:
         return self.__cache

    @property
    def forced(self) -> Callable[..., R]:
         return self.__get__(None, None).forced

    def __call__(self, *args: Any, **kwargs: Any) -> R:
        return self.__get__(None, None)(*args, **kwargs)

def memoize(wrapped: Callable[..., R], memoize_exceptions: bool, cache: Optional[Cache[CallParams, R]]) -> MemoizedFunctionWrapper[R]:
    if cache is None:
        cache = ConcurrentCache()
    return MemoizedFunctionWrapper(wrapped, memoize_exceptions, cache)