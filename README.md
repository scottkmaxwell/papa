Summary
=======

**papa** is a process kernel. It contains both a client library and a server
component for creating sockets and launching processes from a stable parent
process.

Dependencies
============

Papa has no external dependencies, and it never will! It has been tested under the following Python versions:

- 2.6
- 2.7
- 3.2
- 3.3
- 3.4


Installation
============

    $> pip install papa


Purpose
=======

Sometimes you want to be able to start a process and have it survive on its own,
but you still want to be able to capture the output. You could daemonize it
and pipe the output to files, but that is a pain and lacks flexibility when it
comes to handling the output.

Process managers such as circus and supervisor are very good for starting and
stopping processes, and for ensuring that they are automatically restarted when
they die. However, if you need to restart the process manager, all of their
managed processes must be brought down as well. In this day of zero downtime,
that is no longer okay.

Papa is a process kernel. It has extremely limited functionality and it has zero
external dependencies. If I've done my job right, you should never need to
upgrade the papa package. There will probably be a few bug fixes before it is
really "done", but the design goal was to create something that did NOT do
everything, but only did the bare minimum required. The big process managers can
add the remaining features.

Papa has 3 types of things it manages:

- Sockets
- Values
- Processes

Here is what papa does:

- Create sockets and close sockets
- Set, get and clear named values
- Start processes and capture their stdout/stderr
- Allow you to retrieve the stdout/stderr of the processes started by papa
- Pass socket file descriptors and port numbers to processes as they start

Here is what it does NOT do:

- Stop processes
- Send signals to processes
- Restart processes
- Communicate with processes in any way other than to capture their output


Sockets
=======

By managing sockets, papa can manage interprocess communication. Just create a
socket in papa and then pass the file descriptor to your process to use it.
See the [Circus docs](http://circus.readthedocs.org/en/0.11.1/for-ops/sockets/)
for a very good description of why this is so useful.

Papa can create Unix, INET and INET6 sockets. By default it will create an INET
TCP socket on an OS-assigned port.

You can pass either the file descriptor (fileno) or the port of a socket to a
process by including a pattern like this in the process arguments:

- `$(socket.my_awesome_socket_name.fileno)`
- `$(socket.my_awesome_socket_name.port)`


Values
======

Papa has a very simple name/value pair storage. This works much like environment
variables. The values must be text, so if you want to store a complex structure,
you will need to encode and decode with something like the
[JSON module](https://docs.python.org/3/library/json.html).

The primary purpose of this facility is to store state information for your
process that will survive between restarts. For instance, a process manager can
store the current state that all of its managed processes are supposed to be in.
Then if the process manager is restarted, it can restore its internal state,
then go about checking to see if anything on the machine has changed. Are all
processes that should be running actually running?


Processes
=========

Processes can be started with or without output management. You can specify a
maximum size for output to be cached. Each started process has a management
thread in the Papa kernel watching its state and capturing output if necessary.


A Note on Naming (Namespacing)
==============================

Sockets, values and processes all have unique names. A name can only represent
one item per class. So you could have an "aack" socket, an "aack" value and an
"aack" process, but you cannot have two "aack" processes.

All of the monitoring commands support a final asterix as a wildcard. So you
can get a list of sockets whose names match "uwsgi*" and you would get any
socket that starts with "uwsgi".

One good naming scheme is to prefix all names with the name of your own
application. So, for instance, the Circus process manager can prefix all names
with "circus." and the Supervisor process manager can prefix all names with
"supervisor.". If you write your own simple process manager, just prefix it with
"tweeter." or "facebooklet." or whatever your project is called.

If you need to have multiple copies of something, put a number after a dot
for each of those as well. For instance, if you are starting 3 waitress
instances in circus, call them `circus.waitress.1`, `circus.waitress.2`, and
`circus.waitress.3`. That way you can query for all processes named `circus.*`
to see all processes managed by circus, or query for `circus.waitress.*` to
see all waitress processes managed by circus.


Starting the kernel
===================

There are two ways to start the kernel. You can run it as a process, or you can
just try to access it from the client library and allow it to autostart. The
client library uses a lock to ensure that multiple threads do not start the
server at the same time but there is currently no protection against multiple
processes doing so.

By default, the papa kernel process will communicate over port 20202. You can
change this by specifying a different port number or a path. By specifying a
path, a Unix socket will be used instead.

If you are going to be creating papa client instances in many places in your
code, you may want to just call `papa.set_default_port` or `papa.set_default_path`
once when your application is starting and then just instantiate the Papa object
with no parameters.


Telnet interface
================

Papa has been designed so that you can communicate with the process kernel
entirely without code. Just start the Papa server, then do this:

    telnet localhost 20202

You should get a welcome message and a prompt. Type "help" to get help. Type
"help process" to get help on the process command.

The most useful commands from a monitoring standpoint are:

- list sockets
- list processes
- list values

All of these can by used with no arguments, or can be followed by a list of
names, including wildcards. For instance, to see all of the values in the
circus and supervisor namespaces, do this:

    list values circus.* supervisor.*

You can abbreviate every command as short as you like. So "l p" means
"list processes" and "h l p" means "help list processes"


Creating a Connection
=====================

You can create either long-lived or short-lived connections to the Papa kernel.
If you want to have a long-lived connection, just create a Papa object to
connect and close it when done, like this:

    class MyObject(object):
        def __init__(self):
            self.papa = Papa()

        def start_stuff(self):
            self.papa.make_socket('uwsgi')
            self.papa.make_process('uwsgi', 'env/bin/uwsgi', args=('--ini', 'uwsgi.ini', '--socket', 'fd://$(socket.uwsgi.fileno)'), working_dir='/Users/aackbar/awesome', env=os.environ)
            self.papa.make_process('http_receiver', sys.executable, args=('http.py', '$(socket.uwsgi.port)'), working_dir='/Users/aackbar/awesome', env=os.environ)

        def close(self):
            self.papa.close()

If you want to just fire off a few commands and leave, it is better to use the
`with` mechanism like this:

    from papa import Papa
	
    with Papa() as p:
        print(p.list_sockets())
        print(p.make_socket('uwsgi', port=8080))
        print(p.list_sockets())
        print(p.make_process('uwsgi', 'env/bin/uwsgi', args=('--ini', 'uwsgi.ini', '--socket', 'fd://$(socket.uwsgi.fileno)'), working_dir='/Users/aackbar/awesome', env=os.environ))
        print(p.make_process('http_receiver', sys.executable, args=('http.py', '$(socket.uwsgi.port)'), working_dir='/Users/aackbar/awesome', env=os.environ))
        print(p.list_processes())

This will make a new connection, do a bunch of work, then close the connection.


Socket Commands
===============

There are 3 socket commands.

`p.list_sockets(*args)`
------------------

The `sockets` command takes a list of socket names to get info about. All of
these are valid:

- `p.list_sockets()`
- `p.list_sockets('circus.*')`
- `p.list_sockets('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

A `dict` is returned with socket names as keys and socket details as values.

`p.make_socket(name, host=None, port=None, family=None, socket_type=None, backlog=None, path=None, umask=None, interface=None, reuseport=None)`
-----------------------------------------------------------------------------------------------------------------------------------------------

All parameters are optional except for the name. To create a standard TCP socket
on port 8080, you can do this:

    p.make_socket('circus.uwsgi', port=8080)

To make a Unix socket, do this:

    p.make_socket('circus.uwsgi', path='/tmp/uwsgi.sock')

A path for a Unix socket must be an absolute path or `make_socket` will raise a
`papa.Error` exception.

You can also leave out the path and port to create a standard TCP socket with an
OS-assigned port. This is really handy when you do not care what port is used.

If you call `make_socket` with the name of a socket that already exists, papa
will return the original socket if all parameters match, or raise a `papa.Error`
exception if some parameters differ.

See the `make_sockets` method of the Papa object for other parameters.

`p.remove_sockets(*args)`
-----------------------

The `remove_sockets` command also takes a list of socket names. All of these are
valid:

- `p.remove_sockets('circus.*')`
- `p.remove_sockets('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

Removing a socket will prevent any future processes from using it, but any
processes that were already started using the file descriptor of the socket will
continue to use the copy they inherited.


Value Commands
==============

There are 4 value commands.

`p.list_values(*args)`
-----------------

The `list_values` command takes a list of values to retrieve. All of these are
valid:

- `p.list_values()`
- `p.list_values('circus.*')`
- `p.list_list_values('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

A `dict` will be returned with all matching names and values.

`p.set(name, value=None)`
-------------------------

To set a value, do this:

    p.set('circus.uswgi', value)

You can clear a single value by setting it to `None`.

`p.get(name)`
-------------

To retrieve a value, do this:

    value = p.get('circus.uwsgi')

If no value is stored by that name, `None` will be returned.

`p.remove_values(*args)`
----------------

To remove a value or values, do something like this:

- `p.remove_values('circus.*')`
- `p.remove_values('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

You cannot remove all variables so passing no names or passing `*` will raise
a `papa.Error` exception.


Process Commands
================

There are 4 process commands:

`p.list_processes(*args)`
--------------------

The `list_processes` command takes a list of process names to get info about.
All of these are valid:

- `p.list_processes()`
- `p.list_processes('circus.*')`
- `p.list_processes('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

A `dict` is returned with process names as keys and process details as values.

`p.make_process(name, executable, args=None, env=None, working_dir=None, uid=None, gid=None, rlimits=None, stdout=None, stderr=None, bufsize=None, watch_immediately=None)`
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Every process must have a unique `name` and an `executable`. All other
parameters are optional. The `make_process` method returns a `dict` that
contains the pid of the process.

The `args` parameter should be a tuple of command-line arguments. If you have
only one argument, papa conveniently supports passing that as a string.

You will probably want to pass `working_dir`. If you do not, the working
directory will be that of the papa kernel process.

By default, stdout and stderr are captured so that you can retrieve them
with the `watch` command. By default, the `bufsize` for the output is 1MB.

Valid values for `stdout` and `stderr` are `papa.DEVNULL` and `papa.PIPE` (the
default). You can also pass `papa.STDOUT` to `stderr` to merge the streams. 

If you pass `bufsize=0`, not output will be recorded. Otherwise, bufsize can be
the number of bytes, or a number followed by 'k', 'm' or 'g'. If you want a
2 MB buffer, you can pass `bufsize='2m'`, for instance. If you do not retrieve
the output quicky enough and the buffer overflows, older data is removed to make
room.

If you specify `uid`, it can be either the numeric id of the user or the
username string. Likewise, `gid` can be either the numeric group id or the
group name string.

If you want to specify `rlimits`, pass a `dict` with rlimit names and numeric
values. Valid rlimit names can be found in the `resources` module. Leave off the
`RLIMIT_` prefix. On my system, valid names are `as`, `core`, `cpu`, `data`,
`fsize`, `memlock`, `nofile`, `nproc`, `rss`, and `stack`.

    rlimit={'cpu': 2, 'nofile': 1024}

The `env` parameter also takes a `dict` with names and values. A useful trick is
to do `env=os.environ` to copy your environment to the new process.

If you want to run a Python application and you wish to use the same Python
executable as your client application, a useful trick is to pass `sys.executable`
as the `executable` and the path to the Python script as the first element of your
`args` tuple. If you have no other args, just pass the path as a string to
`args`.

    p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)

The final argument that needs mention is `watch_immediately`. If you pass `True`
for this, papa will make the process and return a `Watcher`. This is effectively
the same as doing `p.make_process(name, ...)` followed immediately by
`p.watch(name)`, but it has one fewer round-trip communication with the kernel.
If all you want to do is launch an application and monitor its output, this is
a good way to go.

`p.remove_processes(*args)`
--------------------------------

If you do not care about retrieving the output or the exit code for a process,
you can use `remove_processes` to tell the papa kernel to close the output
buffers and automatically remove the process from the process list when it
exits.

- `p.remove_processes('circus.logger')`
- `p.remove_processes('circus.uwsgi', 'circus.nginx.*', 'circus.logger')`

`p.watch_processes(*args)`
----------------

The `watch_processes` command returns a `Watcher` object for the specified process or
processes. That object uses a separate socket to retrieve the output of
the processes it is watching.

*Optimization Note:* Actually, it hijacks the socket of your `Papa`
object. If you issue any other commands to the `Papa` object that require a
connection to the kernel, the `Papa` object will silently create a new socket and
connect up for the additional commands. If you close the `Watcher` and the `Papa`
object has not already created a new connection, the socket will be returned to
the `Papa` object. So if you launch an application, use `watch` to grab all of
its output until it closes, then use the `set` command to update your saved
status, all of that can occur with a single connection.


The Watcher object
==================

When you use `watch_processes` or when you do `make_process` with
`watch_immediately=True`, you get back a `Watcher` object.

You can use watchers manually or with a context manager. Here is an example
without a context manager:

    class MyLogger(object):
        def __init__(self, watcher):
            self.watcher = watcher

        def save_stuff(self):
            if self.watcher and self.watcher.ready:
                out, err, closed = self.watcher.read()
                ... save it ...
                self.watcher.acknowledge()  # remove it from the buffer

        def close(self):
            self.watcher.close()

If you are running your logger in a separate thread anyway, you might want to
just use a context manager, like this:

    with p.watch_processes('aack') as watcher:
        while watcher:
            out, err, closed = watcher.read()  # block until something arrives
            ... save it ...
            watcher.acknowledge()  # remove it from the buffer

The `Watcher` object has a `fileno` method, so it can be used with `select.select`,
like this:

    watchers = []
    
    watchers.append(p.watch_processes('circus.uwsgi'))
    watchers.append(p.watch_processes('circus.nginx'))
    watchers.append(p.watch_processes('circus.mongos.*'))
    
    while watchers:
        ready_watchers = select.select(watchers, [], [])[0]  # wait for one of these
        for watcher in ready_watchers:  # iterate through all that are ready
            out, err, closed = watcher.read()
            ... save it ...
            watcher.acknowledge()
            if not watcher:  # if it is done, remove this watcher from the list
                watcher.close()
                del watchers[watcher]

Of course, in the above example it would have been even more efficient to just
use a single watcher, like this:

    with p.watch_processes('circus.uwsgi', 'circus.nginx', 'circus.mongos.*') as watcher:
        while watcher:
            out, err, closed = watcher.read()
            ... save it ...
            # watcher.acknowledge() - no need since watcher.read will do it for us

`w.ready`
---------

This property is `True` if the `Watcher` has data available to read on the socket.

`w.read()`
----------

Read will grab all waiting output from the `Watcher` and return a `tuple` of
`(out, err, closed)`. Each of these is an array of `papa.ProcessOutput` objects.
An output object is actually a `namedtuple` with 3 values: `name`, `timestamp`,
and `data`.

The `name` element is the `name` of the process. The `timestamp` is a `float` of
when the data was captured by the papa kernel. The `data` is a binary string if
found in either the `out` or `err` array. It is the exit code if found in the
`closed` array. Using all of these elements, you can write proper timestamps
into your logs, even if data was captured by the papa kernel minutes, hours or
days earlier.

The `read` method will block if no data is ready to read. If you do not want to
block, use either the `ready` property or a mechanism such as `select.select`
before calling `read`.

`w.acknowledge()`
-----------------

Just because your have read output from a process, the papa kernel cannot know
that you successfully logged it. Maybe you crashed or were shutdown before you
had the chance. So the papa kernel will hold onto the data until you acknowledge
receipt. This can be done either by calling `acknowledge`, or by doing a
subsequent `read` or a `close`.

`w.close()`
-----------

When you are done with a `Watcher`, be sure to close it. That will release the
socket and potentially even return the socket back to the original `Papa` object.
It will also send off a final `acknowledge` if necessary.

If you use a context manager, the `close` happens automatically.

`if watcher:`
-------------

A boolean check on the `Watcher` object will return `True` if it is still
active and `False` if it has received and acknowledged a close message from all
processes it is monitoring.

WARNING: There should be only one
---------------------------------

You will get very screwy results if you have multiple watchers for the same
process. Each will get the available data, then acknowledge receipt at some
point, removing that data from the queue. Based on timing, both will get
overlapping results, but neither is likely to get everything.


Shutting Down
=============

Papa is meant to be a long-lived process and it is meant to be usable by
multiple client apps. If you would like to shut Papa down, you can try
`p.exit_if_idle()`. This call will only exit Papa if there are no processes,
sockets or values. So if your app cleaned everything up and no other app is
using Papa, `exit_if_idle` will allow Papa to die. It will return `True` if
Papa has indicated that it will exit when the connection closes.

If you want to do a complete cleanup, kill all of your processes however you
like, then do:

    p.remove_processes('myapp.*')
    p.remove_sockets('myapp.*')
    p.remove_values('myapp.*')
    if p.exit_if_idle():
        print('Papa says it will shutdown!')

WARNING: If another process connects to Papa before the connection is closed,
Papa will remain open. The `exit_if_idle` command will drop the connection if
it returns True so this is a very narrow window of opportunity for failure.
