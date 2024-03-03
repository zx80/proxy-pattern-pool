# Proxy Pattern Pool

Generic Proxy and Pool Classes for Python.

![Status](https://github.com/zx80/proxy-pattern-pool/actions/workflows/ppp.yml/badge.svg?branch=main&style=flat)
![Tests](https://img.shields.io/badge/tests-11%20✓-success)
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
- `log_level` set logging level, default *None* means no setting.
- `max_size` of pool, default _None_ means **no** pooling.
- `max_size` and _all_ other parameters are forwarded to `Pool`.

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
- `max_using_delay_kill` when to kill objects kept for a long time.
- `health_freq` run health check this every house keeper rounds.
- `hk_delay` force house keeping delay.
- `log_level` set logging level, default *None* means no setting.
- `opener` function to call when creating an object, default *None* means no call.
- `getter` function to call when getting an object, default *None* means no call.
- `retter` function to call when returning an object, default *None* means no call.
- `closer` function to call when discarding an object, default *None* means no call.
- `stats` function to call to generate a JSON-compatible structure for stats.
- `health` function to call to check for an available object health.
- `tracer` object debug helper, default *None* means less debug.

Objects are created on demand by calling `fun` when needed.

## Proxy Example

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

This module is rhetorical: because of the GIL Python is quite bad as a parallel
language, so the point of creating threads which will mostly not really run in
parallel is moot, thus the point of having a clever pool of stuff to be shared
by these thread is even mooter!

Shared object *must* be returned to the pool to avoid depleting resources.
This may require some active cooperation from the infrastructure which may
or may not be reliable. Consider monitoring your resources to detect unexpected
status, eg database connections remaining  _idle in transaction_ and the like.

See Also:

- [Psycopg Pool](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
  for pooling Postgres database connexions.
- [Eventlet db_pool](https://eventlet.net/doc/modules/db_pool.html)
  for pooling MySQL or Postgres database connexions.
- [Discussion](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
about database pool sizing (spoiler: small is beautiful).

## License

This code is [Public Domain](https://creativecommons.org/publicdomain/zero/1.0/).

## Versions

[Sources](https://github.com/zx80/proxy-pattern-pool),
[documentation](https://zx80.github.io/proxy-pattern-pool/) and
[issues](https://github.com/zx80/proxy-pattern-pool/issues)
are hosted on [GitHub](https://github.com).
Install [package](https://pypi.org/project/ProxyPatternPool/) from
[PyPI](https://pypi.org/).

### 9.5 on 2023-03-03

Collect and show more statistics.

### 9.4 on 2023-03-03

Improve stats output for semaphore.

### 9.3 on 2023-03-03

Improve collected stats.
Clean-up code, reducing loc significantly.

### 9.2 on 2023-03-02

Rework internals to minimize lock time.
Show timestamp in ISO format.

### 9.1 on 2024-03-02

Do not generate `"None"` but `None` on undefined semaphore stats.

### 9.0 on 2024-03-02

Add `delay` parameter for forcing house keeping round delays.
Add health check hook.
Rework and improve statistics.
Improve documentation.
Drop `close` and `max_delay` upward compatibility parameters.

### 8.5 on 2024-02-27

Add running time to stats.

### 8.4 on 2024-02-26

Add `stats` parameter and `stats` method to `Pool`.

### 8.3 on 2024-02-24

Add more stats.
Improve housekeeping resilience.

### 8.2 on 2024-02-21

Improved debugging information.

### 8.1 on 2024-02-21

Show more pool data.
Improve overall resilience in case of various errors.
Improve `Pool` documentation.

### 8.0 on 2024-02-20

Add `opener`, `getter`, `retter` and `closer` pool hooks.

### 7.4 on 2024-02-17

Fix `log_level` handling.

### 7.3 on 2024-02-17

Add `tracer` parameter to help debugging on pool objects.

### 7.2 on 2024-02-17

Add `log_level` parameter.
Add `pyright` (non yet working) check.

### 7.1 on 2024-02-17

On second thought, allow both warning and killing long running objects.

### 7.0 on 2024-02-17

Kill long running objects instead of just warning about them.

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

- more stats?
