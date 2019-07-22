import threading
import queue
from pytest import raises, mark # type: ignore
from typing import *
from pyfunccache.cache import *
from pyfunccache.memo import *
import time

T = TypeVar("T")

def k(x: int) -> Callable[[Callable[..., T]], MemoizedFunctionWrapper[T]]:

    def a(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, SimpleCache[CallParams, T]())

    def b(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, SimpleCache[CallParams, T]())

    def c(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, ThreadLocalCache[CallParams, T]())

    def d(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, SyncCache[CallParams, T]())

    def e(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, ConcurrentCache[CallParams, T]())

    def f(f: Callable[..., T]) -> MemoizedFunctionWrapper[T]:
        return memoize(f, True, ExpiringCache[CallParams, T](datetime.timedelta(seconds = 10), SimpleCache[CallParams, T]()))

    return [a, b, c, d, e, f][x]

pcaches: Sequence[int] = range(0, 6)

memi: int

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_function(i: int) -> None:

    mem = k(i)

    global memi
    memi = 0

    @mem
    def bar() -> int:
        global memi
        memi = memi + 1
        return memi

    assert memi == 0
    assert bar() == 1
    assert memi == 1
    assert bar() == 1
    assert memi == 1
    assert bar.forced() == 2
    assert memi == 2
    assert bar() == 2
    assert memi == 2
    assert bar.wrapped() == 3
    assert memi == 3
    assert bar() == 2
    assert memi == 3
    assert bar.forced() == 4
    assert memi == 4
    bar.cache.save(CallParams.create(None, (), {}), 999)
    assert bar() == 999
    assert memi == 4
    assert bar.forced() == 5
    assert memi == 5

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_static(i: int) -> None:

    mem = k(i)

    class Whoa:
        j: int = 0

        @mem
        @staticmethod
        def bar() -> int:
            Whoa.j = Whoa.j + 1
            return Whoa.j

    assert Whoa.j == 0
    assert Whoa.bar() == 1
    assert Whoa.j == 1
    assert Whoa.bar() == 1
    assert Whoa.j == 1
    assert Whoa.bar.forced() == 2
    assert Whoa.j == 2
    assert Whoa.bar() == 2
    assert Whoa.j == 2
    assert Whoa.bar.wrapped() == 3
    assert Whoa.j == 3
    assert Whoa.bar() == 2
    assert Whoa.j == 3
    assert Whoa.bar.forced() == 4
    assert Whoa.j == 4
    Whoa.bar.cache.save(CallParams.create(None, (), {}), 999)
    assert Whoa.bar() == 999
    assert Whoa.j == 4
    assert Whoa.bar.forced() == 5
    assert Whoa.j == 5

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_instance(i: int) -> None:

    mem = k(i)

    class Whoa:
        def __init__(self) -> None:
            self.j: int = 0

        @mem
        def bar(self) -> int:
            self.j = self.j + 1
            return self.j

    x = Whoa()
    assert x.j == 0
    assert x.bar() == 1
    assert x.j == 1
    assert x.bar() == 1
    assert x.j == 1
    assert x.bar.forced() == 2
    assert x.j == 2
    assert x.bar() == 2
    assert x.j == 2
    assert x.bar.wrapped() == 3
    assert x.j == 3
    assert x.bar() == 2
    assert x.j == 3
    assert x.bar.forced() == 4
    assert x.j == 4
    x.bar.cache.save(CallParams.create(x, (), {}), 999)
    assert x.bar() == 999
    assert x.j == 4
    assert x.bar.forced() == 5
    assert x.j == 5

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_instance_as_static(i: int) -> None:

    mem = k(i)

    class Whoa:
        def __init__(self) -> None:
            self.j: int = 0

        @mem
        def bar(self) -> int:
            self.j = self.j + 1
            return self.j

    x = Whoa()
    assert x.j == 0
    assert Whoa.bar(x) == 1
    assert x.j == 1
    assert Whoa.bar(x) == 1
    assert x.j == 1
    assert Whoa.bar.forced(x) == 2
    assert x.j == 2
    assert Whoa.bar(x) == 2
    assert x.j == 2
    assert Whoa.bar.wrapped(x) == 3
    assert x.j == 3
    assert Whoa.bar(x) == 2
    assert x.j == 3
    assert Whoa.bar.forced(x) == 4
    assert x.j == 4
    Whoa.bar.cache.save(CallParams.create(None, (x,), {}), 999)
    assert Whoa.bar(x) == 999
    assert x.j == 4
    assert Whoa.bar.forced(x) == 5
    assert x.j == 5

memy: int
memz: int

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_function_multiparam(i: int) -> None:

    mem = k(i)

    global memy
    memy = 0
    global memz
    memz = 0

    @mem
    def bar(q: int) -> int:
        if q == 0:
            global memy
            memy = memy + 1
            return memy
        global memz
        memz = memz + 1
        return memz

    assert memy == 0
    assert memz == 0
    assert bar(1) == 1
    assert memz == 1
    assert bar(1) == 1
    assert memz == 1
    assert bar.forced(1) == 2
    assert memz == 2
    assert bar(1) == 2
    assert memz == 2
    assert bar.wrapped(1) == 3
    assert memz == 3
    assert bar(1) == 2
    assert memz == 3
    assert bar(0) == 1
    assert memy == 1
    assert bar(0) == 1
    assert memy == 1
    assert bar.forced(0) == 2
    assert memy == 2
    assert bar.forced(1) == 4
    assert memz == 4
    bar.cache.save(CallParams.create(None, (1, ), {}), 999)
    assert bar(1) == 999
    assert memz == 4
    assert bar.forced(1) == 5
    assert memz == 5

@mark.parametrize("i", pcaches) # type: ignore
def test_memoize_instance_multiparam(i: int) -> None:

    mem = k(i)

    class Whoa:
        def __init__(self) -> None:
            self.j: int = 0
            self.k: int = 0

        @mem
        def bar(self, q: int) -> int:
            if q == 0:
                self.j = self.j + 1
                return self.j
            self.k = self.k + 1
            return self.k

    x = Whoa()
    y = Whoa()

    assert x.j == 0
    assert x.k == 0
    assert y.j == 0
    assert y.k == 0
    assert x.bar(0) == 1
    assert x.j == 1
    assert x.k == 0
    assert y.j == 0
    assert y.k == 0

    assert x.bar(0) == 1
    assert x.j == 1
    assert x.bar.forced(0) == 2
    assert x.j == 2
    assert x.bar(0) == 2
    assert x.j == 2
    assert x.bar.wrapped(0) == 3
    assert x.j == 3
    assert x.bar(0) == 2
    assert x.j == 3
    assert x.bar.forced(0) == 4
    assert x.j == 4
    x.bar.cache.save(CallParams.create(x, (0, ), {}), 999)
    assert x.bar(0) == 999
    assert x.j == 4
    assert x.bar.forced(0) == 5
    assert x.j == 5
    assert x.k == 0
    assert y.j == 0
    assert y.k == 0

    assert y.bar(1) == 1
    assert y.bar.forced(1) == 2
    assert y.bar.forced(1) == 3
    assert x.j == 5
    assert x.k == 0
    assert y.j == 0
    assert y.k == 3
