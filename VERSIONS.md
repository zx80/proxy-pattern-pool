# Proxy Pattern Pool Versions

## TODO

- more stats?

## 9.7 on ?

Fix detection of the debugging level status.
Add `_has_obj` method to test if an error occured on get.

## 9.6 on 2024-03-07

Add more guarded debugging traces.
Pass `pyright` and enable it in CI.
Add and use `ruff` instead of `flake8`.

## 9.5 on 2024-03-03

Collect and show more statistics.

## 9.4 on 2024-03-03

Improve stats output for semaphore.

## 9.3 on 2024-03-03

Improve collected stats.
Clean-up code, reducing loc significantly.

## 9.2 on 2024-03-02

Rework internals to minimize lock time.
Show timestamp in ISO format.

## 9.1 on 2024-03-02

Do not generate `"None"` but `None` on undefined semaphore stats.

## 9.0 on 2024-03-02

Add `delay` parameter for forcing house keeping round delays.
Add health check hook.
Rework and improve statistics.
Improve documentation.
Drop `close` and `max_delay` upward compatibility parameters.

## 8.5 on 2024-02-27

Add running time to stats.

## 8.4 on 2024-02-26

Add `stats` parameter and `stats` method to `Pool`.

## 8.3 on 2024-02-24

Add more stats.
Improve housekeeping resilience.

## 8.2 on 2024-02-21

Improved debugging information.

## 8.1 on 2024-02-21

Show more pool data.
Improve overall resilience in case of various errors.
Improve `Pool` documentation.

## 8.0 on 2024-02-20

Add `opener`, `getter`, `retter` and `closer` pool hooks.

## 7.4 on 2024-02-17

Fix `log_level` handling.

## 7.3 on 2024-02-17

Add `tracer` parameter to help debugging on pool objects.

## 7.2 on 2024-02-17

Add `log_level` parameter.
Add `pyright` (non yet working) check.

## 7.1 on 2024-02-17

On second thought, allow both warning and killing long running objects.

## 7.0 on 2024-02-17

Kill long running objects instead of just warning about them.

## 6.1 on 2023-11-19

Add Python _3.12_ tests.

## 6.0 on 2023-07-17

Add support for more `local` scopes: `WERKZEUG`, `EVENTLET`, `GEVENT`.

## 5.0 on 2023-06-16

Use `pyproject.toml` only.
Require Python *3.10* for simpler code.

## 4.0 on 2023-02-05

Add `max_using_delay` for warnings.
Add `with` support to both `Pool` and `Proxy` classes.
Add module-specific exceptions: `PoolException`, `ProxyException`.

## 3.0 on 2022-12-27

Wait for available objects when `max_size` is reached.
Add `min_size` parameter to `Proxy`.

## 2.1 on 2022-12-27

Ensure that pool always hold `min_size` objects.

## 2.0 on 2022-12-26

Add min size and max delay feature to `Pool`.

## 1.1 on 2022-11-12

Minor fixes for `mypy`.
Test with Python *3.12*.
Improved documentation.

## 1.0 on 2022-10-29

Add some documentation.

## 0.1 on 2022-10-28

Initial release with code extracted from `FlaskSimpleAuth`.
