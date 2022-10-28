# Proxy Pattern Pool

Generic Proxy and Pool Classes for Python.

![Status](https://github.com/zx80/proxy-pattern-pool/actions/workflows/ppp.yml/badge.svg?branch=main&style=flat)
![Tests](https://img.shields.io/badge/tests-3%20✓-success)
![Coverage](https://img.shields.io/badge/coverage-100%25-success)
![Python](https://img.shields.io/badge/python-3-informational)
![Version](https://img.shields.io/pypi/v/ProxyPatternPool)
![Badges](https://img.shields.io/badge/badges-7-informational)
![License](https://img.shields.io/pypi/l/proxypatternpool?style=flat)

This module provides two classes:

- `Proxy` implements the
  [proxy pattern](https://en.wikipedia.org/wiki/Proxy_pattern),
  i.e. all calls to methods on the proxy are forwarded to an internally wrapped
  object. This allows to solve the classic chicken-and-egg importation and
  initialization issue with Python objects:

  ```python
  # File "database.py"
  db = Proxy()

  def init_app(config):
      db.set(initialization from config)
  ```

  ```python
  # File "app.py"
  import database
  from database import db  # db is a proxy to nothing
  …
  # delayed initialization
  database.init_app(config)

  # db is now a proxy to the initialized object
  ```

- `Pool` implements a thread-safe pool of things which can be used to store
  expensive-to-create objects such as database connections. The above proxy
  object creates a pool automatically depending on its parameters.

## Documentation

The `Proxy` class manages accesses to one or more objects, possibly using
a `Pool`, depending on the expected scope of objects.

The `Proxy` constructors expects the following parameters:

- `obj` one *single* object `SHARED` between all threads.
- `fun` one function called for object creation, each time it is needed,
  for `THREAD` and `VERSATILE` scopes.
- `scope` object scope as defined by `Proxy.Scope`:
  - `SHARED` one shared object (process level)
  - `THREAD` one object per thread
  - `VERSATILE` one object per sub-thread (eg greenlets)
  default is `SHARED` or `THREAD` depending on whether an object
  of a function was passed for the object.
- `set_name` the name of a function to set the proxy contents,
  default is `set`. This parameter allows to avoid collisions with
  the proxied methods.
  It is used as a prefix to have `set_obj` and `set_fun` functions.
- `max_size` maximum size of pool of objects kept.
  *None* means no pooling, *0* means unlimited pool size (the default).
- `max_use` how many times an object should be reused.
  default is *0* which means unlimited.
- `close` name of the function to call when discarding an object,
  default is *None* means nothing is called.

When `max_size` is not *None*, a `Pool` is created to store the created
objects so as to reuse them. It is the responsability of the user to
return the object when not needed anymore by calling `_ret_obj` explicitely.
For a database connection, a good time to do that is just after a `commit`.

The `Pool` class manage a pool of objects in a thread-safe way.
Its constructor expects the following parameters:

- `fun` how to create a new object; the function is passed the creation number.
- `max_size` size of pool, *0* for unlimited.
- `max_use` after how many usage to discard an object.
- `close` method to call when discarding an object, default is *None*.

Objects are created on demand by calling `fun` when needed.

## License

This code is public domain.

## Versions

### 0.1 on 2022-10-28

Initial release with code extracted from `FlaskSimpleAuth`.

## TODO

- `__enter__` and `__exit__`?
