# ProxyPatternPool Documentation

This module provides two classes:

- `Proxy` a proxy class which forwards method calls to a wrapped
  possibly per-thread object.
- `Pool` a generic pool which allows to share resources between
  threads or the like.

## Proxy

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

## Pool

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
