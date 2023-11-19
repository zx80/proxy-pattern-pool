"""
Generic Proxy Pattern Pool for Python.

This code is public domain.
"""

from typing import Callable, Any
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager
import threading
import datetime
import time
import logging

# get module version
from importlib.metadata import version as pkg_version

__version__ = pkg_version("ProxyPatternPool")


log = logging.getLogger("ppp")


class PoolException(Exception):
    pass


class TimeOut(PoolException):
    pass


class ProxyException(Exception):
    pass


class Pool:
    """Thread-safe pool of something, created on demand.

    - fun: function to create objects on demand, called with the creation number.
    - max_size: maximum size of pool, 0 for unlimited.
    - min_size: minimum size of pool.
    - timeout: give-up waiting after this time, None for no timeout.
    - max_use: how many times to use a something, 0 for unlimited.
    - max_avail_delay: remove objects if unused for this secs, 0.0 for unlimited.
    - max_using_delay: warn if object is keept for more than this time, 0.0 for no warning.
    - close: name of "close" method to call, if any.
    """

    @dataclass
    class UseInfo:
        uses: int
        last_get: float
        last_ret: float

    def __init__(
        self,
        fun: Callable[[int], Any],
        max_size: int = 0,
        min_size: int = 1,
        timeout: float = None,
        max_use: int = 0,
        max_avail_delay: float = 0.0,
        max_using_delay: float = 0.0,
        close: str|None = None,
        # temporary upward compatibility
        max_delay: float = 0.0,
    ):
        # data attributes
        self._fun = fun
        self._nobjs = 0
        self._nuses = 0
        self._ncreated = 0
        self._max_size = max_size
        self._min_size = min_size
        self._timeout = timeout
        self._max_use = max_use
        self._max_avail_delay = max_avail_delay or max_delay
        self._max_using_delay = max_using_delay
        self._close = close
        # pool's content: available vs in use objects
        self._avail: set[Any] = set()
        self._using: set[Any] = set()
        # keep track of usage count and last ops
        self._uses: dict[Any, Pool.UseInfo] = {}
        # global pool re-entrant lock to manage attributes
        self._lock = threading.RLock()
        self._sem: threading.Semaphore|None = None
        if self._max_size:
            self._sem = threading.BoundedSemaphore(self._max_size)
        # create the minimum number of objects
        while self._nobjs < self._min_size:
            self._new()
        # start housekeeper thread if needed
        self._housekeeper: threading.Thread|None = None
        if self._max_avail_delay or self._max_using_delay:
            self._delay = self._max_avail_delay
            if not self._delay or \
               self._max_using_delay and self._delay > self._max_using_delay:  # fmt: skip
                self._delay = self._max_using_delay
            self._delay /= 2.0
        else:
            self._delay = 0.0
        if self._delay:
            self._housekeeper = threading.Thread(target=self._houseKeeping, daemon=True)
            self._housekeeper.start()

    def __str__(self):
        o, u, a, i = self._nobjs, self._nuses, len(self._avail), len(self._using)
        return f"o={o} u={u} a={a} i={i}"

    def _now(self) -> float:
        """Return now as a convenient float, in seconds."""
        return datetime.datetime.timestamp(datetime.datetime.now())

    def _houseKeeping(self):
        """Housekeeping thread."""
        log.info(f"housekeeper running every {self._delay}")
        while True:
            time.sleep(self._delay)
            log.debug(str(self))
            if self._nobjs <= self._min_size and not self._max_using_delay:
                # nothing to do this round
                continue
            with self._lock:
                now = self._now()
                if self._max_using_delay:
                    # warn about long running objects
                    long_running, long_time = 0, 0.0
                    for obj in list(self._using):
                        if now - self._uses[obj].last_get >= self._max_using_delay:
                            long_running += 1
                            long_time += now - self._uses[obj].last_get
                    if long_running:
                        # TODO what to do about these? force return?
                        log.warning(
                            f"long running objects: {long_running} ({long_time / long_running})"
                        )
                if self._max_avail_delay:
                    # close objects unused for too long
                    for obj in list(self._avail):
                        if now - self._uses[obj].last_ret >= self._max_avail_delay:
                            self._del(obj)
                            # stop deleting objects if min size is reached
                            if self._nobjs <= self._min_size:
                                break

    def __delete__(self):
        """This should be done automatically, but eventually."""
        with self._lock:
            # using should be empty
            self._using.clear()
            self._uses.clear()
            for obj in list(self._avail):
                self._del(obj)
            self._avail.clear()

    def _new(self):
        """Create a new available object."""
        log.debug(f"creating new obj with {self._fun}")
        with self._lock:
            if self._max_size and self._nobjs >= self._max_size:  # pragma: no cover
                raise PoolException(f"pool max size {self._max_size} reached")
            obj = self._fun(self._ncreated)
            self._ncreated += 1
            self._nobjs += 1
            self._avail.add(obj)
            now = self._now()
            self._uses[obj] = Pool.UseInfo(0, now, now)
            return obj

    def _del(self, obj):
        """Destroy this object."""
        with self._lock:
            if self._close and hasattr(obj, self._close):
                try:
                    getattr(obj, self._close)()
                except Exception as e:
                    log.error(f"exception on {self._close}(): {e}")
            if obj in self._uses:
                del self._uses[obj]
            if obj in self._avail:
                self._avail.remove(obj)
            if obj in self._using:  # pragma: no cover
                self._using.remove(obj)
            del obj
            self._nobjs -= 1

    def get(self, timeout=None):
        """Get a object from the pool, possibly creating one if needed."""
        while True:
            if self._sem:
                if not self._sem.acquire(timeout=timeout if timeout else self._timeout):
                    raise TimeOut(f"timeout after {timeout}")
            with self._lock:
                if len(self._avail) == 0:
                    self._new()
                obj = self._avail.pop()
                self._using.add(obj)
                self._nuses += 1
                self._uses[obj].uses += 1
                self._uses[obj].last_get = self._now()
                return obj

    def ret(self, obj):
        """Return object to pool."""
        with self._lock:
            if obj not in self._using:
                return
            self._using.remove(obj)
            if self._max_use and self._uses[obj].uses >= self._max_use:
                self._del(obj)
                if self._nobjs < self._min_size:
                    self._new()
            else:
                self._uses[obj].last_ret = self._now()
                self._avail.add(obj)
            if self._sem:
                self._sem.release()

    @contextmanager
    def obj(self, timeout=None):
        """Extract one object from the pool in a `with` scope."""
        try:
            o = self.get()
            yield o
        finally:
            self.ret(o)


class Proxy:
    """Proxy pattern class.

    The proxy forwards most method calls to the wrapped object, so that
    the reference can be imported even if the object is not created yet.

    ```python
    r = Proxy()
    o = …
    r.set(o)
    r.whatever(…) # behaves as o.whatever(…)
    ```

    The object may be thread-local or global depending on whether it is
    initialized directly or by providing a generation functions.
    The generation function is called on demand in each thread automatically.
    """

    class Local(object):
        """Dumb storage class for shared scope."""

        pass

    class Scope(Enum):
        """Granularity of object sharing.

        - SHARED: only one object, which should be thread safe.
        - THREAD: per-thread object, generated by a function.
        - VERSATILE: sub-thread-level object (eg greenlet), generated by a function.
        """

        AUTO = 0
        SHARED = 1
        THREAD = 2
        VERSATILE = 3
        WERKZEUG = 3
        GEVENT = 4
        EVENTLET = 5

    def __init__(
        self,
        obj: Any = None,
        set_name: str = "set",
        fun: Callable[[int], Any] = None,
        max_size: int = 0,
        min_size: int = 1,
        max_use: int = 0,
        max_avail_delay: float = 0.0,
        max_using_delay: float = 0.0,
        timeout: float = None,
        scope: Scope = Scope.AUTO,
        close: str|None = None,
        # temporary backward compatibility
        max_delay: float = 0.0,
    ):
        """Constructor parameters:

        - set_name: provide another prefix for the "set" functions.
        - obj: object to be wrapped, can also be provided later.
        - fun: function to generated a per-thread/or-whatever wrapped object.
        - max_size: pool maximum size, 0 for unlimited, None for no pooling.
        - min_size: pool minimum size.
        - max_use: when pooling, how many times to reuse an object.
        - max_avail_delay: when pooling, when to discard an unused object.
        - max_using_delay: when pooling, warn about long uses.
        - timeout: when pooling, how long to wait for an object.
        - scope: level of sharing, default is to chose between SHARED and THREAD.
        - close: "close" method, if any.
        """
        # scope encodes the expected object unicity or multiplicity
        self._scope = (
            Proxy.Scope.SHARED if scope == Proxy.Scope.AUTO and obj else
            Proxy.Scope.THREAD if scope == Proxy.Scope.AUTO and fun else
            scope)  # fmt: skip
        self._pool_max_size = max_size
        self._pool_min_size = min_size
        self._pool_max_use = max_use
        self._pool_max_avail_delay = max_avail_delay or max_delay
        self._pool_max_using_delay = max_using_delay
        self._pool_timeout = timeout
        self._close = close
        self._set(obj=obj, fun=fun, mandatory=False)
        if set_name and set_name != "_set":
            setattr(self, set_name, self._set)
            setattr(self, set_name + "_obj", self._set_obj)
            setattr(self, set_name + "_fun", self._set_fun)

    def _set_obj(self, obj):
        """Set current wrapped object."""
        log.debug(f"Setting proxy to {obj} ({type(obj)})")
        self._scope = Proxy.Scope.SHARED
        self._fun = None
        self._pool = None
        self._nobjs = 1
        self._local = self.Local()
        self._local.obj = obj
        return self

    def _set_fun(self, fun: Callable[[int], Any]):
        """Set current wrapped object generation function."""
        if self._scope == Proxy.Scope.AUTO:
            self._scope = Proxy.Scope.THREAD
        assert self._scope in (Proxy.Scope.THREAD, Proxy.Scope.VERSATILE,
            Proxy.Scope.WERKZEUG, Proxy.Scope.EVENTLET, Proxy.Scope.GEVENT)
        self._fun = fun
        self._pool = Pool(fun,
                          max_size=self._pool_max_size,
                          min_size=self._pool_min_size,
                          timeout=self._pool_timeout,
                          max_use=self._pool_max_use,
                          max_avail_delay=self._pool_max_avail_delay,
                          max_using_delay=self._pool_max_using_delay,
                          close=self._close) \
            if self._pool_max_size is not None else None  # fmt: skip
        self._nobjs = 0

        # local implementation (*event coverage skip for 3.12)
        if self._scope == Proxy.Scope.THREAD:
            self._local = threading.local()
        elif self._scope == Proxy.Scope.WERKZEUG:
            from werkzeug.local import Local

            self._local = Local()
        elif self._scope == Proxy.Scope.GEVENT:  # pragma: no cover
            from gevent.local import local  # type: ignore

            self._local = local()
        elif self._scope == Proxy.Scope.EVENTLET:  # pragma: no cover
            from eventlet.corolocal import local  # type: ignore

            self._local = local()
        else:  # pragma: no cover
            raise Exception(f"unexpected local scope: {self._scope}")

        return self

    def _set(
        self,
        obj: Any = None,
        fun: Callable[[int], Any]|None = None,
        mandatory=True,
    ):
        """Set current wrapped object or generation function."""
        if obj and fun:
            raise ProxyException("Proxy cannot set both obj and fun")
        elif obj:
            return self._set_obj(obj)
        elif fun:
            return self._set_fun(fun)
        elif mandatory:
            raise ProxyException("Proxy must set either obj or fun")

    def _get_obj(self, timeout=None):
        """Get current wrapped object, possibly creating it."""
        # handle creation
        if self._fun and not hasattr(self._local, "obj"):
            if self._pool_max_size is not None:
                # sync on pool to extract a consistent nobjs
                with self._pool._lock:
                    self._local.obj = self._pool.get(timeout=timeout)
                    self._nobjs = self._pool._nobjs
            else:  # no pool
                self._local.obj = self._fun(self._nobjs)
                self._nobjs += 1
        return self._local.obj

    # FIXME how to do that automatically when the thread/whatever ends?
    def _ret_obj(self):
        """Return current wrapped object to internal pool."""
        if self._pool_max_size is not None and hasattr(self._local, "obj"):
            self._pool.ret(self._local.obj)
            delattr(self._local, "obj")
        # else just ignore

    def __getattr__(self, item):
        """Forward everything unknown to contained object."""
        return self._get_obj().__getattribute__(item)

    @contextmanager
    def _obj(self, timeout=None):
        """Get a object in a `with` scope."""
        try:
            o = self._get_obj(timeout=timeout)
            yield o
        finally:
            self._ret_obj()

    # also forward a few special methods
    def __str__(self):
        return self._get_obj().__str__()

    def __repr__(self):
        return self._get_obj().__repr__()

    def __eq__(self, v):
        return self._get_obj().__eq__(v)

    def __ne__(self, v):
        return self._get_obj().__ne__(v)

    def __hash__(self):
        return self._get_obj().__hash__()
