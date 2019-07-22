import threading
import queue
from pytest import raises, mark # type: ignore
from typing import *
from pyfunccache.cache import *
from pyfunccache.freeze import freeze
import time

T = TypeVar("T")
SI = Union[str, int]
K = Dict[str, Any]
P = Callable[[], Cache[K, SI]]

def p1() -> K:
    return cast(K, freeze({'i': 'foo', 'a': (), 'k': {'x': 'y', 'a': 'b'}}))

def p2() -> K:
    return cast(K, freeze({'i': 'xxx', 'a': (123, 'm'), 'k': {'a': 123, 'c': 444}}))

def p3() -> K:
    return cast(K, freeze({'i': 'foo', 'a': (), 'k': {'u': 444, 'n': [2, 4, 5]}}))

def p4() -> K:
    return cast(K, freeze({'i': 'xxx', 'a': (123, 'm'), 'k': {'u': {'a': 'b'}}}))

def p5() -> K:
    return cast(K, freeze({'i': 'foo', 'a': (123, 'm'), 'k': {True: 5, 'g': 'g'}}))

def save_cache_test(x: Cache[K, SI]) -> None:
    assert not x.has_cached(p1())
    with raises(KeyError) as xxx: x.get_cached(p1())

    x.save(p1(), 'a')

    assert x.has_cached(p1())
    assert x.get_cached(p1()) == 'a'

def save_exception_cache_test(x: Cache[K, SI]) -> None:
    e: ValueError = ValueError(':(')

    assert not x.has_cached(p1())
    with raises(KeyError) as xxx: x.get_cached(p1())

    x.save_exception(p1(), e)

    assert x.has_cached(p1())
    with raises(BaseException) as xe: x.get_cached(p1())
    assert xe.value is e

def save_many_cache_test(x: Cache[K, SI]) -> None:
    e: ValueError = ValueError(':(')
    f: ValueError = ValueError(':)')

    assert not x.has_cached(p1())
    with raises(KeyError) as xxx: x.get_cached(p1())

    x.save(p1(), 'a')
    x.save(p2(), 'b')
    x.save(p3(), 123)
    x.save_exception(p4(), e)
    x.save_exception(p5(), f)

    assert x.has_cached(p1())
    assert x.has_cached(p2())
    assert x.has_cached(p3())
    assert x.has_cached(p4())
    assert x.has_cached(p5())

    assert x.get_cached(p1()) == 'a'
    assert x.get_cached(p2()) == 'b'
    assert x.get_cached(p3()) == 123

    with raises(BaseException) as xe: x.get_cached(p4())
    assert xe.value is e
    with raises(BaseException) as xf: x.get_cached(p5())
    assert xf.value is f

def reset_cache_test(x: Cache[K, SI]) -> None:
    e: ValueError = ValueError(':(')
    f: ValueError = ValueError(':)')

    assert not x.has_cached(p1())
    with raises(KeyError) as xxx:
        x.get_cached(p1())

    x.save(p1(), 'a')
    x.save(p2(), 'b')
    x.save(p3(), 123)
    x.save_exception(p4(), e)
    x.save_exception(p5(), f)

    x.reset()

    assert not x.has_cached(p1())
    assert not x.has_cached(p2())
    assert not x.has_cached(p3())
    assert not x.has_cached(p4())
    assert not x.has_cached(p5())

    with raises(KeyError) as xxx: x.get_cached(p1())
    with raises(KeyError) as xxx: x.get_cached(p2())
    with raises(KeyError) as xxx: x.get_cached(p3())
    with raises(KeyError) as xxx: x.get_cached(p4())
    with raises(KeyError) as xxx: x.get_cached(p5())

def forget_cache_test(x: Cache[K, SI]) -> None:
    e: ValueError = ValueError(':(')
    f: ValueError = ValueError(':)')

    assert not x.has_cached(p1())
    with raises(KeyError) as xxx: x.get_cached(p1())

    x.save(p1(), 'a')
    x.save(p2(), 'b')
    x.save(p3(), 123)
    x.save_exception(p4(), e)
    x.save_exception(p5(), f)

    x.forget(p2())
    x.forget(p5())

    assert x.has_cached(p1())
    assert not x.has_cached(p2())
    assert x.has_cached(p3())
    assert x.has_cached(p4())
    assert not x.has_cached(p5())

    assert x.get_cached(p1()) == 'a'
    with raises(KeyError) as xxx: x.get_cached(p2())
    assert x.get_cached(p3()) == 123
    with raises(BaseException) as xe: x.get_cached(p4())
    assert xe.value is e
    with raises(KeyError) as xxx: x.get_cached(p5())

def expiring() -> ExpiringCache[K, SI]:
    return ExpiringCache[K, SI](datetime.timedelta(seconds = 10), SimpleCache[K, SI]())

caches: List[P] = [
    SimpleCache[K, SI],
    ThreadLocalCache[K, SI],
    SyncCache[K, SI],
    ConcurrentCache[K, SI],
    expiring
]

@mark.parametrize("cache", caches) # type: ignore
def test_save(cache: P) -> None:
    save_cache_test(cache())

@mark.parametrize("cache", caches) # type: ignore
def test_save_exception(cache: P) -> None:
    save_exception_cache_test(cache())

@mark.parametrize("cache", caches) # type: ignore
def test_save_many(cache: P) -> None:
    save_many_cache_test(cache())

@mark.parametrize("cache", caches) # type: ignore
def test_reset(cache: P) -> None:
    reset_cache_test(cache())

@mark.parametrize("cache", caches) # type: ignore
def test_forget(cache: P) -> None:
    forget_cache_test(cache())

@mark.timeout(1) # type: ignore
def test_ThreadLocalCache_isolation() -> None:
    x: ThreadLocalCache[K, SI] = ThreadLocalCache[K, SI]()
    p: queue.Queue[int] = queue.Queue()
    q: queue.Queue[int] = queue.Queue()
    r: queue.Queue[Any] = queue.Queue()

    def inner1() -> None:
        try:
            x.save(p1(), 'a')
            q.put(123)
            p.get()
            assert x.get_cached(p1()) == 'a'
        except BaseException as xxxx:
            r.put(xxxx)
        else:
            r.put(True)

    def inner2() -> None:
        try:
            x.save(p1(), 'b')
            p.put(123)
            q.get()
            assert x.get_cached(p1()) == 'b'
        except BaseException as xxxx:
            r.put(xxxx)
        else:
            r.put(True)

    t1 = threading.Thread(target = inner1)
    t2 = threading.Thread(target = inner2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert r.get() is True
    assert r.get() is True

@mark.timeout(1) # type: ignore
def test_ConcurrentCache_isolation() -> None:
    x: ConcurrentCache[K, SI] = ConcurrentCache[K, SI]()
    p: queue.Queue[int] = queue.Queue()
    q: queue.Queue[int] = queue.Queue()
    r: queue.Queue[Any] = queue.Queue()

    def inner1() -> None:
        try:
            x.save(p1(), 'a')
            q.put(123)
            p.get()
            assert x.has_cached(p1())
            assert x.get_cached(p1()) == 'b'
        except BaseException as xxxx:
            r.put(xxxx)
        else:
            r.put(True)

    def inner2() -> None:
        try:
            q.get()
            assert x.has_cached(p1())
            assert x.get_cached(p1()) == 'a'
            x.save(p1(), 'b')
            p.put(123)
        except BaseException as xxxx:
            r.put(xxxx)
        else:
            r.put(True)

    t1 = threading.Thread(target = inner1)
    t2 = threading.Thread(target = inner2)
    t2.start()
    t1.start()
    t1.join()
    t2.join()
    assert r.get() is True
    assert r.get() is True

def test_expiration() -> None:
    x: ExpiringCache[int, str] = ExpiringCache[int, str](datetime.timedelta(seconds = 1), SimpleCache[int, str]())
    x.save(123, 'a')
    assert x.has_cached(123)
    assert x.get_cached(123) == 'a'
    time.sleep(2)
    assert not x.has_cached(123)