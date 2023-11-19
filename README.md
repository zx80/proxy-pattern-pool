# Proxy Pattern Pool

Generic Proxy and Pool Classes for Python.

![Status](https://github.com/zx80/proxy-pattern-pool/actions/workflows/ppp.yml/badge.svg?branch=main&style=flat)
![Tests](https://img.shields.io/badge/tests-9%20✓-success)
![Coverage](https://img.shields.io/badge/coverage-100%25-success)
![Issues](https://img.shields.io/github/issues/zx80/proxy-pattern-pool?style=flat)
![Python](https://img.shields.io/badge/python-3-informational)
![Version](https://img.shields.io/pypi/v/ProxyPatternPool)
![Badges](https://img.shields.io/badge/badges-8-informational)
![License](https://img.shields.io/pypi/l/proxypatternpool?style=flat)

This module provides two classes:

- `Proxy` implements the
  [proxy pattern](https://en.wikipedia.org/wiki/Proxy_pattern),
  i.e. all calls to methods on the proxy are forwarded to an internally wrapped
  object. This allows to solve the classic chicken-and-egg importation and
  initialization possibly circular-dependency issue with Python modules:

  ```python
  # File "database.py"
  db = Proxy()

  def init_app(config):
      db.set_obj(initialization from config)
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

  Call `db._ret_obj()` to return the object to the pool when done with it.

## Documentation

The `Proxy` class manages accesses to one or more objects, possibly using
a `Pool`, depending on the expected scope of said objects.

The `Proxy` constructors expects the following parameters:

- `obj` one *single* object `SHARED` between all threads.
- `fun` one function called for object creation, each time it is needed,
  for `THREAD` and `VERSATILE` scopes.
- `scope` object scope as defined by `Proxy.Scope`:
  - `SHARED` one shared object (process level)
  - `THREAD` one object per thread (`threading` implementation)
  - `WERKZEUG` one object per greenlet (`werkzeug` implementation)
  - `EVENTLET` one object per greenlet (`eventlet` implementation)
  - `GEVENT` one object per greenlet (`gevent` implementation)
  - `VERSATILE` same as `WERKZEUG`
  default is `SHARED` or `THREAD` depending on whether an object
  of a function was passed for the object.
- `set_name` the name of a function to set the proxy contents,
  default is `set`. This parameter allows to avoid collisions with
  the proxied methods.
  It is used as a prefix to have `set_obj` and `set_fun` functions
  which allow to reset the internal `obj` or `fun`.
- `max_size` maximum pool size for objects kept.
  *None* means no pooling, *0* means unlimited pool size (the default).
- `min_size` minimum pool size.
  This many is created on startup.
  Default is *1*.
- `max_use` how many times an object should be reused.
  default is *0* which means unlimited.
- `max_avail_delay` after which unused objects are discarded.
  default is *0.0* which means unlimited.
- `max_using_delay` warn when objects are being used for too long.
  default is *0.0* which means no warning.
- `close` name of the function to call when discarding an object,
  default is *None* means nothing is called.

When `max_size` is not *None*, a `Pool` is created to store the created
objects so as to reuse them. It is the responsability of the user to
return the object when not needed anymore by calling `_ret_obj` explicitely.
This is useful for code which keeps creating new threads, eg `werkzeug`.
For a database connection, a good time to do that is just after a `commit`.

The `Pool` class manage a pool of objects in a thread-safe way.
Its constructor expects the following parameters:

- `fun` how to create a new object; the function is passed the creation number.
- `max_size` maximum size of pool, *0* for unlimited.
- `min_size` minimum size of pool.
- `timeout` maximum time to wait for something.
- `max_use` after how many usage to discard an object.
- `max_avail_delay` when to discard an unused object.
- `max_using_delay` when to warn about object kept for a long time.
- `close` method to call when discarding an object, default is *None*.

Objects are created on demand by calling `fun` when needed.

## Example

Here is an example of a flask application with blueprints and a shared
resource.

First, a shared module holds a proxy to a yet unknown object:

```python
# file "Shared.py"
from ProxyPatternPool import Proxy 
stuff = Proxy()
def init_app(stuff):
    stuff.set_obj(stuff)
```

This shared object is used by module with a blueprint:

```python
# file "SubStuff.py"
from Flask import Blueprint
from Shared import stuff
sub = Blueprint(…)

@sub.get("/stuff")
def get_stuff():
    return str(stuff), 200
```

Then the application itself can load and initialize both modules in any order
without risk of having some unitialized stuff imported:

```python
# file "App.py"
from flask import Flask
app = Flask("stuff")

from SubStuff import sub
app.register_blueprint(sub, url_prefix="/sub")

import Shared
Shared.init_app("hello world!")
```

## Notes

This module is somehow rhetorical: because of the GIL Python is quite bad as a
parallel language, so the point of creating threads which will mostly not really
run in parallel is moot, thus the point of having a clever pool of stuff to be
shared by these thread is even mooter!

See Also:

- [Psycopg Pool](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
  for pooling Postgres database connexions.
- [Eventlet db_pool](https://eventlet.net/doc/modules/db_pool.html)
  for pooling MySQL or Postgres database connexions.
- [Discussion](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
  about database pool sizing.

## License

This code is [Public Domain](https://creativecommons.org/publicdomain/zero/1.0/).

## Versions

[Sources](https://github.com/zx80/proxy-pattern-pool),
[documentation](https://zx80.github.io/proxy-pattern-pool/) and
[issues](https://github.com/zx80/proxy-pattern-pool/issues)
are hosted on [GitHub](https://github.com).
Install [package](https://pypi.org/project/ProxyPatternPool/) from
[PyPI](https://pypi.org/).

### 6.1 on 2023-11-19

Add Python _3.12_ tests.

### 6.0 on 2023-07-17

Add support for more `local` scopes: `WERKZEUG`, `EVENTLET`, `GEVENT`.

### 5.0 on 2023-06-16

Use `pyproject.toml` only.
Require Python *3.10* for simpler code.

### 4.0 on 2023-02-05

Add `max_using_delay` for warnings.
Add `with` support to both `Pool` and `Proxy` classes.
Add module-specific exceptions: `PoolException`, `ProxyException`.

### 3.0 on 2022-12-27

Wait for available objects when `max_size` is reached.
Add `min_size` parameter to `Proxy`.

### 2.1 on 2022-12-27

Ensure that pool always hold `min_size` objects.

### 2.0 on 2022-12-26

Add min size and max delay feature to `Pool`.

### 1.1 on 2022-11-12

Minor fixes for `mypy`.
Test with Python *3.12*.
Improved documentation.

### 1.0 on 2022-10-29

Add some documentation.

### 0.1 on 2022-10-28

Initial release with code extracted from `FlaskSimpleAuth`.

## TODO

- add a method to delete the proxy?
- add an actual timeout feature?
- how to manage a return automatically?
