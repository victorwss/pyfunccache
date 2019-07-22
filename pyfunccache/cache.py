from functools import wraps
import datetime
import threading
from abc import ABC, abstractmethod
from typing import Callable, cast, Dict, Generic, Iterator, Optional, Sequence, Tuple, Type, TypeVar
from dataclasses import dataclass

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")
X = TypeVar("X")

class ResultLine(ABC, Generic[T]):
    def __init__(self) -> None:
        pass

    @property
    @abstractmethod
    def updated(self) -> Optional[datetime.datetime]:
        pass

    @property
    @abstractmethod
    def empty(self) -> bool:
        pass

    @property
    @abstractmethod
    def result(self) -> T:
        pass

class EmptyLine(ResultLine[T], Generic[T]):
    def __init__(self) -> None:
        pass

    @property
    def updated(self) -> Optional[datetime.datetime]:
        return None

    @property
    def empty(self) -> bool:
        return True

    @property
    def result(self) -> T:
        raise KeyError()

    def __eq__(self, other: object) -> bool:
        return type(other) == EmptyLine

class RaiseLine(ResultLine[T], Generic[T]):
    def __init__(self, raised: BaseException) -> None:
        self.__raised: BaseException = raised
        self.__updated: datetime.datetime = datetime.datetime.now()

    @property
    def updated(self) -> datetime.datetime:
        return self.__updated

    @property
    def empty(self) -> bool:
        return False

    @property
    def result(self) -> T:
        raise self.__raised

    def __eq__(self, other: object) -> bool:
        return type(other) == RaiseLine and cast(RaiseLine[T], other).__updated == self.__updated and cast(RaiseLine[T], other).__raised == self.__raised

class ReturnLine(ResultLine[T], Generic[T]):
    def __init__(self, returned: T) -> None:
        self.__returned: T = returned
        self.__updated: datetime.datetime = datetime.datetime.now()

    @property
    def updated(self) -> datetime.datetime:
        return self.__updated

    @property
    def empty(self) -> bool:
        return False

    @property
    def result(self) -> T:
        return self.__returned

    def __eq__(self, other: object) -> bool:
        return type(other) == ReturnLine and cast(ReturnLine[T], other).__updated == self.__updated and cast(ReturnLine[T], other).__returned == self.__returned

class Cache(ABC, Generic[K, V]):
    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def add_line(self, key: K, line: ResultLine[V]) -> None:
        pass

    def forget(self, key: K) -> None:
        self.add_line(key, EmptyLine[V]())

    def save(self, key: K, value: V) -> None:
        self.add_line(key, ReturnLine[V](value))

    def save_exception(self, key: K, ouch: BaseException) -> None:
        self.add_line(key, RaiseLine[V](ouch))

    def has_cached(self, key: K) -> bool:
        return not self.get_line(key).empty

    def get_cached(self, key: K) -> V:
        return self.get_line(key).result

    @abstractmethod
    def get_line(self, key: K) -> ResultLine[V]:
        pass

    def with_line(self, key: K, what: Callable[[ResultLine[V]], X]) -> X:
        return what(self.get_line(key))

    '''@abstractmethod
    def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        pass'''

class SimpleCache(Cache[K, V], Generic[K, V]):
    def __init__(self) -> None:
        self.__memo: Dict[K, ResultLine[V]] = {}

    def reset(self) -> None:
        self.__memo = {}

    def add_line(self, key: K, line: ResultLine[V]) -> None:
        if not line.empty:
            self.__memo[key] = line
        elif key in self.__memo:
            del self.__memo[key]

    def get_line(self, key: K) -> ResultLine[V]:
        if key not in self.__memo:
            self.__memo[key] = EmptyLine[V]()
        return self.__memo[key]

    '''def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        for k in self.__memo:
            yield k, self.__memo[k]'''

class ThreadLocalCache(Cache[K, V], Generic[K, V]):
    def __init__(self) -> None:
        self.__memo: threading.local = threading.local()

    def reset(self) -> None:
        self.__memo.t = {}

    def __ensure_t(self) -> Dict[K, ResultLine[V]]:
        if not hasattr(self.__memo, 't'):
            self.__memo.t = {}
        return cast(Dict[K, ResultLine[V]], self.__memo.t)

    def add_line(self, key: K, line: ResultLine[V]) -> None:
        t: Dict[K, ResultLine[V]] = self.__ensure_t()
        if not line.empty:
            t[key] = line
        elif key in t:
            del t[key]

    def get_line(self, key: K) -> ResultLine[V]:
        t: Dict[K, ResultLine[V]] = self.__ensure_t()
        if key not in t:
            t[key] = EmptyLine[V]()
        return t[key]

    '''def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        t: Dict[K, ResultLine[V]] = self.__ensure_t()
        for k in t:
            yield k, t[k]'''

class SyncCache(Cache[K, V], Generic[K, V]):
    def __init__(self) -> None:
        self.__full_lock: threading.RLock = threading.RLock()
        self.__delegate: SimpleCache[K, V] = SimpleCache[K, V]()

    def reset(self) -> None:
        with self.__full_lock:
            self.__delegate = SimpleCache[K, V]()

    def add_line(self, key: K, line: ResultLine[V]) -> None:
        with self.__full_lock:
            self.__delegate.add_line(key, line)

    def get_line(self, key: K) -> ResultLine[V]:
        with self.__full_lock:
            return self.__delegate.get_line(key)

    '''def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        with self.__full_lock:
            return self.__delegate.for_each_line()'''

class ConcurrentMutableResultLine(Generic[V]):
    def __init__(self) -> None:
        self.__lock: threading.RLock = threading.RLock()
        self.__line: ResultLine[V] = EmptyLine()

    def with_it(self, what: Callable[[ResultLine[V]], X]) -> X:
        with self.__lock:
            return what(self.__line)

    @property
    def line(self) -> ResultLine[V]:
        with self.__lock:
            return self.__line

    @line.setter
    def line(self, new: ResultLine[V]) -> None:
        with self.__lock:
            self.__line = new

class ConcurrentCache(Cache[K, V], Generic[K, V]):
    def __init__(self) -> None:
        self.__full_lock: threading.RLock = threading.RLock()
        self.__memo: Dict[K, ConcurrentMutableResultLine[V]] = {}

    def reset(self) -> None:
        with self.__full_lock:
            self.__memo = {}

    def __ensure_line(self, key: K) -> ConcurrentMutableResultLine[V]:
        with self.__full_lock:
            if key not in self.__memo:
                self.__memo[key] = ConcurrentMutableResultLine[V]()
            return self.__memo[key]

    def add_line(self, key: K, line: ResultLine[V]) -> None:
        self.__ensure_line(key).line = line

    def get_line(self, key: K) -> ResultLine[V]:
        return self.__ensure_line(key).line

    def with_line(self, key: K, what: Callable[[ResultLine[V]], X]) -> X:
        return self.__ensure_line(key).with_it(what)

    '''def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        with self.__full_lock:
            for k in self.__memo:
                yield k, self.__memo[k].line'''

class ExpiringCache(Cache[K, V], Generic[K, V]):
    def __init__(self, expiration: datetime.timedelta, delegate: Cache[K, V]) -> None:
        self.__expiration = expiration
        self.__delegate = delegate

    def reset(self) -> None:
        self.__delegate.reset()

    def add_line(self, key: K, line: ResultLine[V]) -> None:
        self.__delegate.add_line(key, line)

    def get_line(self, key: K) -> ResultLine[V]:
        line = self.__delegate.get_line(key)
        if not self.__is_expired(line): return line
        self.forget(key)
        return EmptyLine[V]()

    '''def for_each_line(self) -> Iterator[Tuple[K, ResultLine[V]]]:
        for k in self.__delegate.for_each_line():
            if not self.__is_expired(k[1]):
                yield k'''

    def __is_expired(self, line: ResultLine[V]) -> bool:
        u: Optional[datetime.datetime] = line.updated
        return u is None or u + self.__expiration < datetime.datetime.now()