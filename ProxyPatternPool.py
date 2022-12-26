"""
Generic Proxy Pattern Pool for Python.

This code is public domain.
"""

from typing import Optional, Callable, Dict, Set, Any
from enum import Enum
from dataclasses import dataclass
import threading
import datetime
import time
import logging

# get module version
import pkg_resources as pkg  # type: ignore

__version__ = pkg.require("ProxyPatternPool")[0].version


log = logging.getLogger("ppp")


class Pool:
    """Thread-safe pool of something, created on demand.

    - fun: function to create objects on demand, called with the creation number.
    - max_size: maximum size of pool, 0 for unlimited.
    - min_size: minimum size of pool.
    - max_use: how many times to use a something, 0 for unlimited.
    - max_delay: remove objects if unused, 0.0 for unlimited.
    - close: name of "close" method to call, if any.
    """

    @dataclass
    class UseInfo:
        uses: int
        last: float

    def __init__(
        self,
        fun: Callable[[int], Any],
        max_size: int = 0,
        max_use: int = 0,
        min_size: int = 1,
        max_delay: float = 0.0,
        close: Optional[str] = None,
    ):
        self._lock = threading.RLock()
        self._fun = fun
        self._nobjs = 0
        self._nuses = 0
        self._ncreated = 0
        self._max_size = max_size
        self._min_size = min_size
        self._max_use = max_use
        self._max_delay = max_delay
        self._close = close
        # pool's content: available vs in use objects
        self._avail: Set[Any] = set()
        self._using: Set[Any] = set()
        # keep track of usage count and last return
        self._uses: Dict[Any, Pool.UseInfo] = dict()
        self._housekeeper: Optional[threading.Thread] = None
        if self._max_delay:
            self._housekeeper = threading.Thread(target=self._houseKeeping, daemon=True)
            self._housekeeper.start()

    def __str__(self):
        o, u, a, i = self._nobjs, self._nuses, len(self._avail), len(self._using)
        return f"o={o} u={u} a={a} i={i}"

    def _now(self) -> float:
        return datetime.datetime.timestamp(datetime.datetime.now())

    def _houseKeeping(self):
        """Housekeeping thread."""
        log.warning(f"housekeeper running every {self._max_delay}")
        while True:
            time.sleep(self._max_delay)
            log.debug(str(self))
            if self._nobjs <= self._min_size:
                continue
            with self._lock:
                now = self._now()
                for obj in list(self._avail):
                    if now - self._uses[obj].last >= self._max_delay:
                        self._del(obj)
                        if self._nobjs <= self._min_size:
                            break

    def __delete__(self):
        """This should be done automatically, but eventually."""
        with self._lock:
            self._using.clear()
            self._uses.clear()
            # FIXME what about _using?
            for obj in list(self._avail):
                self._del(obj)
            self._avail.clear()

    def get(self):
        """Get a object from the pool, possibly creating one if needed."""
        with self._lock:
            try:
                obj = self._avail.pop()
                self._using.add(obj)
                self._nuses += 1
                self._uses[obj].uses += 1
            except KeyError:  # nothing available
                if self._max_size and self._nobjs >= self._max_size:
                    raise Exception(f"object pool max size reached ({self._max_size})")
                log.debug(f"creating new obj with {self._fun}")
                obj = self._fun(self._ncreated)
                self._ncreated += 1
                self._nobjs += 1
                self._nuses += 1
                self._using.add(obj)
                self._uses[obj] = Pool.UseInfo(1, self._now())
            return obj

    def _del(self, obj):
        """Destroy this object."""
        if self._close and hasattr(obj, self._close):
            try:
                getattr(obj, self._close)()
            except Exception as e:
                log.warning(f"exception on {self._close}(): {e}")
        if obj in self._uses:
            del self._uses[obj]
        if obj in self._avail:
            self._avail.remove(obj)
        if obj in self._using:  # pragma: no cover
            self._using.remove(obj)
        del obj
        self._nobjs -= 1

    def ret(self, obj):
        """Return object to pool."""
        with self._lock:
            self._using.remove(obj)
            if self._max_use and self._uses[obj].uses >= self._max_use:
                self._del(obj)
            else:
                self._uses[obj].last = self._now()
                self._avail.add(obj)


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

    def __init__(
        self,
        obj: Any = None,
        set_name: str = "set",
        fun: Optional[Callable] = None,
        max_size: int = 0,
        max_use: int = 0,
        max_delay: float = 0.0,
        scope: Scope = Scope.AUTO,
        close: Optional[str] = None,
    ):
        """Constructor parameters:

        - set_name: provide another prefix for the "set" functions.
        - obj: object to be wrapped, can also be provided later.
        - fun: function to generated a per-thread/or-whatever wrapped object.
        - max_size: pool maximum size, 0 for unlimited, None for no pooling.
        - max_use: when pooling, how many times to reuse an object.
        - max_delay: when pooling, when to discard an unused object.
        - scope: level of sharing, default is to chose between SHARED and THREAD.
        - close: "close" method, if any.
        """
        # scope encodes the expected object unicity or multiplicity
        self._scope = (
            Proxy.Scope.SHARED if scope == Proxy.Scope.AUTO and obj else
            Proxy.Scope.THREAD if scope == Proxy.Scope.AUTO and fun else
            scope)  # fmt: skip
        self._pool_max_size = max_size
        self._pool_max_use = max_use
        self._pool_max_delay = max_delay
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
        assert self._scope in (Proxy.Scope.THREAD, Proxy.Scope.VERSATILE)
        self._fun = fun
        self._pool = \
            Pool(fun, self._pool_max_size, self._pool_max_use,
                 max_delay=self._pool_max_delay, close=self._close) \
                if self._pool_max_size is not None else None  # fmt: skip
        self._nobjs = 0
        if self._scope == Proxy.Scope.THREAD:
            self._local = threading.local()
        else:  # Proxy.Scope.VERSATILE
            from werkzeug.local import Local

            self._local = Local()
        return self

    def _set(
        self,
        obj: Any = None,
        fun: Optional[Callable[[int], Any]] = None,
        mandatory=True,
    ):
        """Set current wrapped object or generation function."""
        if obj and fun:
            raise Exception("Proxy cannot set both obj and fun")
        elif obj:
            return self._set_obj(obj)
        elif fun:
            return self._set_fun(fun)
        elif mandatory:
            raise Exception("Proxy must set either obj or fun")

    def _get_obj(self):
        """Get current wrapped object, possibly creating it."""
        # handle creation
        if self._fun and not hasattr(self._local, "obj"):
            if self._pool_max_size is not None:
                # sync on pool to extract a consistent nobjs
                with self._pool._lock:
                    self._local.obj = self._pool.get()
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
