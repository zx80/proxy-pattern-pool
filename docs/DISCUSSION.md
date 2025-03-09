# Discussion

The `ProxyPatternPool` module was initially rhetorical: because of the GIL
Python was very bad as a parallel language, so the point of creating threads
which would mostly not really run in parallel was moot, thus the point of having
a clever pool of stuff to be shared by these thread was even mooter!
However, as the GIL is scheduled to go away in the coming years, starting from
_Python 3.13_ (Fall 2024), it is starting to make sense to have such a thing!

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
  about database pool sizing (spoiler: small is beautiful: you want threads
  waiting for expensive resources used at full capacity rather than
  many expensive resources under used).

Example of resources to put in a pool: connections to databases, authentication
services (eg LDAP), search engine…

For a typical REST backend, most requests will require one DB connection, thus
having an in-process pool with less connections is not very usefull, and more is
useless as well, so we may only have _#conns == #threads_ which make sense.
The only point of having a pool is that the thread may be killed independently
and avoiding recreating connections in such cases.
