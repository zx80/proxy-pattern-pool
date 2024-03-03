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
import json

# get module version
from importlib.metadata import version as pkg_version

__version__ = pkg_version("ProxyPatternPool")

log = logging.getLogger("ppp")

# should the pool be provided as well to some hooks?
FunHook = Callable[[int], Any]
PoolHook = Callable[[Any], None]
TraceHook = Callable[[Any], str]
StatsHook = Callable[[Any], dict[str, Any]]
HealthHook = Callable[[Any], bool]


class PPPException(Exception):
    """Common class for ProxyPatternPool exceptions."""
    pass


class PoolException(PPPException):
    """Common class for Pool exceptions."""
    pass


# NOTE this does not include the time to create a resource
class TimeOut(PoolException):
    """Timeout while acquiring a resource at the pool level."""
    pass


class ProxyException(PPPException):
    """Common class for Proxy exceptions."""
    pass


class Pool:
    """Thread-safe pool of something, created on demand.

    Mandatory parameter:
    - fun: function to create objects on demand, called with the creation number.

    Pool size management parameters:
    - max_size: maximum size of pool, 0 for unlimited.
    - min_size: minimum size of pool.

    Recycling parameters:
    - max_use: how many times to use an object, 0 for unlimited.
    - max_avail_delay: remove objects if unused for this secs, 0.0 for unlimited.
    - max_using_delay: warn if object is kept for more than this time, 0.0 for no warning.
    - max_using_delay_kill: kill if object is kept for more than this time, 0.0 for no killing.
    - delay: use this delay secs for house keeping rounds, 0 for computed default.
      the default delay computed based on previous delay.
    - health_freq: check health this every round, default is 1.

    Hook parameters:
    - opener: hook called on object creation.
    - getter: hook called on object pool extraction.
    - retter: hook called on object pool return.
    - closer: hook called on object destruction.
    - stats: hook called to generate per-object JSON-compatible stats.
    - tracer: hook called to generate debug information on an object.
    - health: hook called to check for an available object health.

    Miscellaneous parameters:
    - timeout: give-up waiting after this time, None for no timeout.
    - log_level: set logging level for local logger.

    The object life cycle is the following, with the corresponding hooks:

    - objects are created by calling ``fun``, after which ``opener`` is called.
    - when an object is extracted from the pool, ``getter`` is called.
    - when an object is returned to the pool, ``retter` is called.
    - when an object is removed from the pool, ``closer`` is called.

    Objects are created:

    - when the number of available object is below ``min_size``.
    - when an object is requested, none is available, and the number of objects
      is below ``max_size``.

    Objects are destroyed:

    - when ``health`` returns *False* on an house keeper round.
    - when they are unused for too long (``max_avail_delay``) and if the number
      of objects is strictly over ``min_size``.
    - when they are being used for too long (over ``max_using_delay_kill``).
    - when they reach the number of uses limit (``max_use``).
    - when ``__delete__`` is called.

    This infrastructure is not suitable for handling very short timeouts, and
    will not be very precise. The using timeout kill is expensive as the object is
    effectively destroyed (so for instance an underlying connection would be
    lost) and will have to be re-created. This is not a replacement for
    carefully designing and monitoring application resource usage.
    """

    @dataclass
    class UseInfo:
        uses: int
        last_get: float
        last_ret: float

    def __init__(
        self,
        fun: FunHook,
        max_size: int = 0,
        min_size: int = 1,
        timeout: float|None = None,
        # recycling
        max_use: int = 0,
        max_avail_delay: float = 0.0,
        max_using_delay: float = 0.0,
        max_using_delay_kill: float = 0.0,
        health_freq: int = 1,
        delay: float = 0.0,
        # hooks
        opener: PoolHook|None = None,
        getter: PoolHook|None = None,
        retter: PoolHook|None = None,
        closer: PoolHook|None = None,
        health: HealthHook|None = None,
        stats: StatsHook|None = None,
        tracer: TraceHook|None = None,
        log_level: int|None = None,
    ):
        # debugging
        if log_level is not None:
            log.setLevel(log_level)
        self._tracer = tracer
        self._started = datetime.datetime.now()
        self._started_ts = datetime.datetime.timestamp(self._started)
        # objects
        self._fun = fun
        # statistics
        self._nobjs = 0  # current number of objects
        self._nuses = 0  # currenly in use
        self._ncreating = 0  # total creation attempts
        self._ncreated = 0  # total created
        self._nhealth = 0  # health calls
        self._bad_health = 0  # bad health detected
        self._nkilled = 0  # long time using kills
        self._nborrows = 0  # object borrowed
        self._nreturns = 0  # object returned
        self._ndestroys = 0  # object actuall destroyed
        self._nrecycled = 0  # long time avail deletes
        self._hk_errors = 0  # house keeping errors
        self._hc_errors = 0  # heath check errors
        self._hk_rounds = 0  # number of house keeper rounds
        self._hc_rounds = 0  # number of house keeper rounds
        self._hk_time = 0.0  # cumulated time spent in house keeping
        self._hk_last = 0.0  # last time a house keeping round started
        # pool management
        self._timeout = timeout
        self._max_size = max_size
        self._min_size = min_size
        self._max_use = max_use  # when to recycle
        self._max_avail_delay = max_avail_delay
        self._max_using_delay_kill = max_using_delay_kill
        self._max_using_delay_warn = max_using_delay or max_using_delay_kill
        self._health_freq = health_freq
        if self._max_using_delay_kill and self._max_using_delay_warn > self._max_using_delay_kill:
            log.warning("inconsistent max_using_delay_warn > max_using_delay_kill")
        # hooks
        self._opener = opener
        self._getter = getter
        self._retter = retter
        self._closer = closer
        self._stats = stats
        self._health = health
        # pool's content: available vs in use objects
        self._avail: set[Any] = set()
        self._using: set[Any] = set()
        self._todel: set[Any] = set()
        # keep track of usage count and last ops
        self._uses: dict[Any, Pool.UseInfo] = {}
        # global pool re-entrant lock to manage "self" attributes
        self._lock = threading.RLock()
        self._sem: threading.Semaphore|None = None
        if self._max_size:
            self._sem = threading.BoundedSemaphore(self._max_size)
        # start housekeeper thread if needed
        self._housekeeper: threading.Thread|None = None
        if delay:
            self._delay = delay
        elif self._max_avail_delay or self._max_using_delay_warn:
            self._delay = self._max_avail_delay
            if not self._delay or \
               self._max_using_delay_warn and self._delay > self._max_using_delay_warn:  # fmt: skip
                self._delay = self._max_using_delay_warn
            self._delay /= 2.0
        else:
            self._delay = 60.0 if self._health else 0.0
        assert not (self._health and self._delay == 0.0)
        if self._delay:
            self._housekeeper = threading.Thread(target=self._houseKeeping, daemon=True)
            self._housekeeper.start()
        # try to create the minimum number of objects
        # NOTE on errors we keep on running, hoping that it will work later…
        self._fill()

    def stats(self):
        """Generate a JSON-compatible structure for stats."""

        # generate per-objet status depending on available hooks
        stats = self._stats if self._stats else self._tracer if self._tracer else str

        with self._lock:
            now = self._now()

            # generic info
            info = {
                # pool configuration
                "started": self._started.isoformat(),
                "min_size": self._min_size,
                "max_size": self._max_size,
                "delay": self._delay,
                "timeout": self._timeout,
                # pool status
                "sem": {"value": self._sem._value, "init": self._sem._initial_value} if self._sem else None,
                "navail": len(self._avail),
                "nusing": len(self._using),
                "ntodel": len(self._todel),
                "running": now - self._started_ts,
                "rel_hk_last": self._hk_last - now,
                "time_per_hk": self._hk_time / max(self._hk_rounds, 1),
                # counts
                "nobjs": self._nobjs,
                "ncreated": self._ncreated,
                "ncreating": self._ncreating,
                "nuses": self._nuses,
                "nkilled": self._nkilled,
                "nrecycled": self._nrecycled,
                "nborrows": self._nborrows,
                "nreturns": self._nreturns,
                "ndestroys": self._ndestroys,
                "nhealth": self._nhealth,
                "bad_health": self._bad_health,
                "hk_errors": self._hk_errors,
                "hc_errors": self._hc_errors,
                "hk_rounds": self._hk_rounds,
                "hc_rounds": self._hc_rounds,
            }

            # per-object info
            info["avail"] = []
            for obj in self._avail:
                info["avail"].append(stats(obj))

            info["using"] = []
            for obj in self._using:
                info["using"].append(stats(obj))

            return info

    def __str__(self):
        return json.dumps(self.stats())

    def _now(self) -> float:
        """Return now as a convenient float, in seconds."""
        return datetime.datetime.timestamp(datetime.datetime.now())

    def _hkRound(self):
        """Housekeeping round, under lock.

        Objects that are scheduled for destruction are moved to ``self._todel``
        so as to minimize the time passed here.
        """
        self._hk_rounds += 1
        now = self._now()

        if self._max_using_delay_warn:
            # warn/kill long running objects
            long_run, long_kill, long_time = 0, 0, 0.0
            for obj in list(self._using):
                running = now - self._uses[obj].last_get
                if running >= self._max_using_delay_warn:
                    long_run += 1
                    long_time += running
                if self._max_using_delay_kill and running >= self._max_using_delay_kill:
                    # we cannot just return the object because another thread may keep on using it.
                    long_kill += 1
                    self._nkilled += 1
                    self._out(obj)
                    self._todel.add(obj)
                    # killed objects where under using and sem
                    if self._sem:  # pragma: no cover
                        self._sem.release()
            if long_run or long_kill:
                delay = (long_time / long_run) if long_run else 0.0
                log.warning(f"long running objects: {long_run} ({delay} seconds, {long_kill} to kill)")

        if self._max_avail_delay and self._nobjs > self._min_size:
            # close spurious unused for too long objects
            for obj in list(self._avail):
                if now - self._uses[obj].last_ret >= self._max_avail_delay:
                    self._nrecycled += 1
                    self._out(obj)
                    self._todel.add(obj)
                    # stop deleting objects if min size is reached
                    if self._nobjs <= self._min_size:
                        break

    def _health_check(self):
        """Health check, not under lock, only called from the hk thread."""

        self._hc_rounds += 1
        with self._lock:
            objs = list(self._uses.keys())
        tracer = self._tracer or str

        # not under lock
        for obj in objs:
            if self._borrow(obj):
                healthy = True
                try:
                    self._nhealth += 1
                    healthy = self._health(obj)
                except Exception as e:  # pragma: no cover
                    self._hc_error += 1
                    log.error(f"health check error: {e}")
                finally:
                    self._return(obj)
                if not healthy:
                    log.error(f"bad health: {tracer(obj)}")
                    self._bad_health += 1
                    self._out(obj)
                    self._todel.add(obj)
            # else skipping obj in use

    def _houseKeeping(self):
        """Housekeeping thread."""

        log.info(f"housekeeper running every {self._delay}")

        while True:
            time.sleep(self._delay)
            self._hk_last = self._now()
            with self._lock:
                # normal round is done under lock, it must be fast!
                try:
                    if log.getEffectiveLevel() == logging.DEBUG:
                        log.debug(str(self))
                    self._hkRound()
                except Exception as e:  # pragma: no cover
                    self._hk_errors += 1
                    log.error(f"housekeeping round error: {e}")
            # health check is done out of locking
            if self._health and self._hk_rounds % self._health_freq == 0:
                self._health_check()
            # actual deletions
            self._empty()
            # possibly re-create objects
            self._fill()
            # update run time
            self._hk_time += self._now() - self._hk_last

    def _fill(self):
        """Create new available objects to reach min_size."""
        with self._lock:
            tocreate = self._min_size - self._nobjs
        if tocreate > 0:
            for _ in range(tocreate):
                # acquire a token to avoid overshooting max_size
                if self._sem and not self._sem.acquire(timeout=0.0):  # pragma: no cover
                    continue
                try:
                    self._new()
                except Exception as e:  # pragma: no cover
                    log.error(f"new object failed: {e}")
                if self._sem:
                    self._sem.release()

    def _empty(self):
        """Empty current todel."""
        with self._lock:
            destroys = list(self._todel)
            self._todel.clear()
            self._ndestroys += len(destroys)
        for obj in destroys:
            self._destroy(obj)

    def __delete__(self):
        """This should be done automatically, but eventually."""
        with self._lock:
            if self._using:  # pragma: no cover
                log.warning(f"deleting in-use objects: {len(self._using)}")
                for obj in list(self._using):
                    self._del(obj)
                self._using.clear()
            for obj in list(self._avail):
                self._del(obj)
            self._avail.clear()
            self._uses.clear()

    def _create(self):
        """Create a new object (low-level)."""
        log.debug(f"creating new obj with {self._fun}")
        with self._lock:
            self._ncreating += 1
        # this may fail
        obj = self._fun(self._ncreated)
        now = self._now()
        obj_info = Pool.UseInfo(0, now, now)
        with self._lock:
            self._ncreated += 1
            self._nobjs += 1
            self._uses[obj] = obj_info
        return obj

    def _new(self):
        """Create a new available object."""
        obj = self._create()
        # on success
        if self._opener:
            try:
                self._opener(obj)
            except Exception as e:
                log.error(f"exception in opener: {e}")
        with self._lock:
            self._avail.add(obj)
        return obj

    def _out(self, obj):
        """Remove an object from pool."""
        seen = False
        with self._lock:
            if obj in self._uses:
                seen = True
                del self._uses[obj]
            if obj in self._avail:
                seen = True
                self._avail.remove(obj)
            if obj in self._using:  # pragma: no cover
                seen = True
                self._using.remove(obj)
            if seen:
                self._nobjs -= 1
            # else possible double removal?

    def _destroy(self, obj):
        """Destroy an object."""
        if self._closer:
            try:
                self._closer(obj)
            except Exception as e:
                log.error(f"exception in closer: {e}")
        del obj

    def _del(self, obj):
        """Delete an object."""
        self._out(obj)
        self._destroy(obj)

    def _borrow(self, obj):
        """Borrow an existing object.

        This is a special get with does not get through getter or setter,
        for internal use such as house keeping, health check…

        If the object is not available, _None_ is returned, this is just best effort.
        """
        if self._sem and not self._sem.acquire(timeout=0.0):  # pragma: no cover
            return None
        with self._lock:
            if obj in self._avail:
                self._avail.remove(obj)
                self._using.add(obj)
                self._nborrows += 1
                return obj
            else:  # pragma: no cover
                return None

    def _return(self, obj):
        """Return borrowed object."""
        with self._lock:
            assert obj in self._using
            self._using.remove(obj)
            self._avail.add(obj)
            self._nreturns += 1
        if self._sem:  # pragma: no cover
            self._sem.release()

    def get(self, timeout=None):
        """Get a object from the pool, possibly creating one if needed."""
        # FIXME why while?
        while True:
            if self._sem:  # ensure that  we do not go over max_size
                # the acquired token will be released at the end of ret()
                if not self._sem.acquire(timeout=timeout if timeout else self._timeout):
                    raise TimeOut(f"timeout after {timeout}")
            with self._lock:
                if not self._avail:
                    try:
                        self._new()
                    except Exception as e:  # pragma: no cover
                        log.error(f"object creation failed: {e}")
                        if self._sem:
                            self._sem.release()
                        raise
                obj = self._avail.pop()
                self._using.add(obj)
                self._nuses += 1
                self._uses[obj].uses += 1
                self._uses[obj].last_get = self._now()
            if self._getter:
                try:
                    self._getter(obj)
                except Exception as e:
                    log.error(f"exception in getter: {e}")
            return obj

    def ret(self, obj):
        """Return object to pool."""
        if self._retter:
            try:
                self._retter(obj)
            except Exception as e:
                log.error(f"exception in retter: {e}")
        with self._lock:
            if obj not in self._using:
                # FIXME issue a warning on multiple ret calls?
                return
            if self._max_use and self._uses[obj].uses >= self._max_use:
                self._out(obj)
                self._todel.add(obj)
            else:
                self._using.remove(obj)
                self._avail.add(obj)
                self._uses[obj].last_ret = self._now()
        if self._sem:  # release token acquired in get()
            self._sem.release()
        self._empty()
        self._fill()

    @contextmanager
    def obj(self, timeout=None):
        """Extract one object from the pool in a `with` scope."""
        try:
            o = self.get(timeout)
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
        # proxy definition
        obj: Any = None,
        fun: FunHook|None = None,
        set_name: str = "set",
        scope: Scope = Scope.AUTO,
        log_level: int|None = None,
        # optional pool parameters
        max_size: int = 0,
        **kwargs,
    ):
        """Constructor parameters:

        - obj: object to be wrapped, can also be provided later.
        - set_name: provide another prefix for the "set" functions.
        - fun: function to generated a per-thread/or-whatever wrapped object.
        - max_size: pool maximum size, 0 for unlimited, None for no pooling.
        - log_level: set logging level for local logger.
        """
        # scope encodes the expected object unicity or multiplicity
        if log_level is not None:
            log.setLevel(log_level)
        self._scope = (
            Proxy.Scope.SHARED if scope == Proxy.Scope.AUTO and obj else
            Proxy.Scope.THREAD if scope == Proxy.Scope.AUTO and fun else
            scope)  # fmt: skip
        self._pool_max_size = max_size
        self._pool_kwargs = kwargs
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

    def _set_fun(self, fun: FunHook):
        """Set current wrapped object generation function."""
        if self._scope == Proxy.Scope.AUTO:
            self._scope = Proxy.Scope.THREAD
        assert self._scope in (Proxy.Scope.THREAD, Proxy.Scope.VERSATILE,
            Proxy.Scope.WERKZEUG, Proxy.Scope.EVENTLET, Proxy.Scope.GEVENT)
        self._fun = fun
        if self._pool_max_size is not None:
            self._pool = Pool(fun, max_size=self._pool_max_size, **self._pool_kwargs)
        else:
            self._pool = None
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
        fun: FunHook|None = None,
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
