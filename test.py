import pytest
import threading
import ProxyPatternPool as ppp

import logging
logging.basicConfig()
log = logging.getLogger("tests")

# app._ppp._log.setLevel(logging.DEBUG)
# app.log.setLevel(logging.DEBUG)
# log.setLevel(logging.DEBUG)
# app._ppp._initialize()

def test_proxy():
    v1, v2 = "hello!", "world!"
    r1 = ppp.Proxy(close="close")
    r1.set(v1)
    assert r1 == v1 and not r1 != v1
    assert r1.startswith("hell")
    r2 = ppp.Proxy(set_name="set_object")
    r2.set_object(v2)
    assert r2 == v2
    assert r2.endswith("ld!")
    r3 = ppp.Proxy("1")
    assert r3 == "1" and r3 != "one"
    assert r3.isdigit()
    assert repr("1") == repr(r3)


def test_proxy_threads():
    # thread local stuff
    def gen_data(i):
        return f"data: {i}"
    r = ppp.Proxy(fun=gen_data, max_size=None, close="close")
    assert r._nobjs == 0
    assert isinstance(r.__hash__(), int)
    assert r._nobjs == 1
    assert isinstance(r._local.obj, str)
    assert r == "data: 0"
    # another thread
    def run(i):
        assert r == f"data: {i}"
    t1 = threading.Thread(target=run, args=(1,))
    t1.start()
    t1.join()
    assert r._nobjs == 2
    t2 = threading.Thread(target=run, args=(2,))
    t2.start()
    t2.join()
    assert r._nobjs == 3
    # local one is still ok
    assert r == "data: 0"
    # FIXME thread objects are not really returned?
    # error
    try:
        r = ppp.Proxy(obj="hello", fun=gen_data)
        assert False, "should have raised an exception"
    except Exception as e:
        assert "Proxy cannot set both obj and fun" in str(e)
    try:
        r = ppp.Proxy(set_name="add")
        r.add()
        assert False, "missing parameter in previous call"
    except Exception as e:
        assert "Proxy must set either obj or fun" in str(e)
    # auto thread
    r = ppp.Proxy(close="close")
    r._set_fun(lambda i: i)
    assert str(r) == "0"
    # versatile
    r = ppp.Proxy(scope=ppp.Proxy.Scope.VERSATILE)
    r._set_fun(lambda i: i+10)
    assert str(r) == "10"


def test_proxy_pool():
    ref = ppp.Proxy(fun=lambda i: i, max_size=2)
    i = ref._get_obj()
    assert len(ref._pool._avail) == 0
    assert len(ref._pool._using) == 1
    assert ref._pool._nobjs == 1
    ref._ret_obj()
    i = ref._get_obj()
    assert len(ref._pool._avail) == 0
    assert len(ref._pool._using) == 1
    assert ref._pool._nobjs == 1
    # this should return the same object as we are in the same thread
    j = ref._get_obj()
    assert i == j
    ref._ret_obj()
    assert len(ref._pool._avail) == 1
    assert len(ref._pool._using) == 0
    assert ref._pool._nobjs == 1
    del ref


def test_proxy_pool_thread():
    ref = ppp.Proxy(fun=lambda i: i, max_size=2)
    # test with 2 ordered threads to grasp to objects from the pool
    import threading
    event = threading.Event()
    def run_1(i: int):
        r = str(ref)      # get previous object #0
        event.set()
        assert r == str(i)
        # ref._ret_obj()  # NOT RETURNED TO POOL
    def run_2(i: int):
        event.wait()
        r = str(ref)      # generate a new object #1
        assert r == str(i)
        # ref._ret_obj()  # NOT RETURNED TO POOL
    t1 = threading.Thread(target=run_1, args=(0,))
    t2 = threading.Thread(target=run_2, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    del t1
    del t2
    # use a 3rd reference to raise an pool max size exception
    try:
        ref._get_obj()   # failed attempt at generating #2
        assert False, "must reach max_size"
    except Exception as e:
        assert "pool max size reached" in str(e)
    del ref


def test_pool():
    # test max_use
    pool = ppp.Pool(fun = lambda i: i, max_size = 1, max_use = 2)
    i = pool.get()
    assert i == 0
    pool.ret(i)
    i = pool.get()
    assert i == 0
    pool.ret(i)
    i = pool.get()
    assert i == 1
    pool.ret(i)
    pool.__delete__()


def test_pool_class():
    # test with close and None
    class T:
        def __init__(self, count):
            self._count = count
        def close(self):
            self._count = None
            raise Exception("Oops!")
        def __str__(self):
            return f"T({self._count})"
    pool = ppp.Pool(fun = T, max_size = None, max_use = 1, close="close")
    t = pool.get()
    assert str(t) == "T(0)"
    pool.ret(t)
    t = pool.get()
    assert str(t) == "T(1)"
    pool.ret(t)
    pool.__delete__()
