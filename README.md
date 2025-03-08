# Proxy Pattern Pool

Generic Proxy and Pool classes for Python.

![Status](https://github.com/zx80/proxy-pattern-pool/actions/workflows/ppp.yml/badge.svg?branch=main&style=flat)
![Tests](https://img.shields.io/badge/tests-13%20✓-success)
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

  When an internal pool is used, method `_ret_obj` **must** be called to return
  the object to the pool when done with it.

- `Pool` implements a full-featured thread-safe pool of things which can be used
  to store expensive-to-create objects such as database connections, to be
  shared between threads for instance. The above proxy object creates a pool
  automatically depending on its parameters.

  This generic pool class can be used independently of the `Proxy` class.

  It provides numerous hooks to provide callbacks for creation, deletion,
  stats, tracing, health check… which make it ideal to manage any kind
  of expensive resources within a process.

  ```python
  import ProxyPatternPool as ppp

  # start a pool with 2 resources created by "fun"
  pool = ppp.Pool(
      fun = lambda n: f"expensive object {n}",
      min_size=2, max_size=2, timeout=0.5,
  )

  # get resources
  a = pool.get(); b = pool.get()  # max_size reached
  try:
      c = pool.get()  # will timeout after 0.5 seconds
      assert False
  except ppp.TimeOut:
      pass

  pool.ret(a); pool.ret(b);  # return resources

  pool.shutdown()
  del pool
  ```

## Documentation

### Proxy

Class `Proxy` manages accesses to one or more objects, possibly using
a `Pool`, depending on the expected scope of said objects.

The `Proxy` constructors expects the following parameters:

- `obj` a *single* object `SHARED` between all threads.
- `fun` a function called for object creation, each time it is needed,
  for all other scopes.
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
  the proxied methods, if necessary.
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

The proxy has a `_has_obj` method to test whether an object is available
without extracting anything from the pool: this is useful to test whether
returning the object is needed in some error handling pattern.

### Pool

Class `Pool` manages a pool of objects in a thread-safe way.
Its constructor expects the following parameters:

- `fun` how to create a new object; the function is passed the creation number.
- `max_size` maximum size of pool, *0* for unlimited (the default).
- `min_size` minimum size of pool, that many are created and maintained in advance.
- `timeout` maximum time to wait for something, only active under `max_size`.
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
def init_app(s):
    stuff.set_obj(s)
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
by these thread is even mooter! However, as the GIL is scheduled to go away
in the coming years, starting from _Python 3.13_, it might start to make sense
to have such a thing here!

In passing, it is interesting to note that the foremost
[driving motivation](https://peps.python.org/pep-0703/) for getting
read of the GIL is… _data science_. This tells something.
In the past, people interested in parallelism, i.e. performance, say myself,
would probably just turn away from this quite slow language.
People from the networking www world would be satisfied with the adhoc
asynchronous model, and/or just create many processes because
in this context the need to communicate between active workers is limited.
Now come the data scientist, who is not that interested in programming, is
happy with Python and its ecosystem, in particular with the various ML libraries
and the commodity of web-centric remote interfaces such as Jupyter. When
confronted with a GIL-induced performance issue, they are more interested at
fixing the problem than having to learn another language and port their stuff.

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

All software has bug, this is software, hence… Beware that you may lose your
hairs or your friends because of it. If you like it, feel free to send a
postcard to the author.

## Versions

[Sources](https://github.com/zx80/proxy-pattern-pool),
[documentation](https://zx80.github.io/proxy-pattern-pool/) and
[issues](https://github.com/zx80/proxy-pattern-pool/issues)
are hosted on [GitHub](https://github.com).
Install [package](https://pypi.org/project/ProxyPatternPool/) from
[PyPI](https://pypi.org/).
See [version details](VERSIONS.md).
