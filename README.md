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
  stats, tracing, health check… which makes it ideal to manage any kind
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
