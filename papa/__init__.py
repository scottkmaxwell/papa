import sys
import os.path
import socket
from threading import Lock
from time import sleep
from subprocess import PIPE, STDOUT
import logging
from papa.utils import string_type

try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = -3

__author__ = 'Scott Maxwell'
__all__ = ['Papa', 'DEBUG_MODE_NONE', 'DEBUG_MODE_THREAD', 'DEBUG_MODE_PROCESS']

log = logging.getLogger('papa.server')


def wrap_trailing_slash(value):
    value = str(value)
    if value[-1] == '\\':
        value = '"{0}"'.format(value)
    return value


def append_if_not_none(container, **kwargs):
    for key, value in kwargs.items():
        if value is not None:
            value = wrap_trailing_slash(value)
            container.append('{0}={1}'.format(key, value))


class Papa(object):
    _debug_mode = False
    _single_connection_mode = False
    _default_port_or_path = 20202

    spawn_lock = Lock()
    spawned = False

    def __init__(self, port_or_path=None):
        port_or_path = port_or_path or self._default_port_or_path
        if isinstance(port_or_path, str):
            if not hasattr(socket, 'AF_UNIX'):
                raise NotImplementedError('Unix sockets are not supported on'
                                          ' this platform')
            if not os.path.isabs(port_or_path):
                raise utils.Error('Path to Unix socket must be absolute.')
            self.family = socket.AF_UNIX
            self.location = port_or_path
        else:
            self.family = socket.AF_INET
            self.location = ('127.0.0.1', port_or_path)

        # Try to connect to an existing Papa
        self.sock = None
        self.t = None
        try:
            self.sock = self._attempt_to_connect()
        except Exception:
            for i in range(50):
                if not Papa.spawned:
                    with Papa.spawn_lock:
                        if not Papa.spawned:
                            if self._debug_mode:
                                from papa.server import socket_server
                                from threading import Thread
                                t = Thread(target=socket_server, args=(port_or_path, self._single_connection_mode))
                                t.daemon = True
                                t.start()
                                self.t = t
                            else:
                                from papa.server import daemonize_server
                                daemonize_server(port_or_path)
                            Papa.spawned = True
                try:
                    self.sock = self._attempt_to_connect()
                    break
                except Exception:
                    sleep(.1)
            else:
                raise utils.Error('Could not connect to Papa in 5 seconds')
        header = b''
        # noinspection PyTypeChecker
        while not header.endswith(b'\n> '):
            header = self.sock.recv(1024)

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if self._single_connection_mode:
            self.t.join()
            Papa.spawned = False

    def _attempt_to_connect(self):
        # Try to connect to an existing Papa
        sock = socket.socket(self.family, socket.SOCK_STREAM)
        if self.family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect(self.location)
        return sock

    def _do_command(self, command):
        if isinstance(command, list):
            command = ' '.join(c.replace(' ', '\ ') for c in command if c)
        command = b(command)
        self.sock.sendall(command + b'\n')
        data = b''
        while True:
            new_data = self.sock.recv(1024)
            if not new_data:
                data = s(data).strip()
                break
            data += new_data
            # noinspection PyTypeChecker
            if data.endswith(b'\n> '):
                data = s(data[:-3])
                break
        # noinspection PyTypeChecker
        if data.startswith('Error:'):
            raise utils.Error(data[7:])
        return data

    @staticmethod
    def _make_socket_dict(socket_info):
        name, args = socket_info.partition(' ')[::2]
        args = dict(item.partition('=')[::2] for item in args.split(' '))
        for key in ('backlog', 'port'):
            if key in args:
                args[key] = int(args[key])
        return name, args

    def sockets(self, *args):
        result = self._do_command(['sockets'] + list(args))
        if not result:
            return {}
        # noinspection PyTypeChecker
        return dict(self._make_socket_dict(item) for item in result.split('\n'))

    def make_socket(self, name, host=None, port=None,
                    family=None, socket_type=None,
                    backlog=None, path=None, umask=None,
                    interface=None, reuseport=None):
        if not name:
            raise utils.Error('Socket requires a name')
        command = ['socket', name]
        if family is not None:
            try:
                family_name = utils.valid_families_by_number[family]
                command.append('family={0}'.format(family_name))
            except KeyError:
                raise utils.Error('Invalid socket family')
        if socket_type is not None:
            try:
                type_name = utils.valid_types_by_number[socket_type]
                command.append('type={0}'.format(type_name))
            except KeyError:
                raise utils.Error('Invalid socket type')
        append_if_not_none(command, backlog=backlog)
        if path:
            if not path[0] == '/' or path[-1] in '/\\':
                raise utils.Error('Socket path must be absolute to a file')
            command.append('path={0}'.format(path))
            append_if_not_none(command, umask=umask)
        else:
            append_if_not_none(command, host=host, port=port, interface=interface)
            if reuseport:
                command.append('reuseport=1')
        return self._make_socket_dict(self._do_command(command))[1]

    def close_socket(self, *args):
        self._do_command(['close', 'socket'] + list(args))
        return True

    def values(self, *args):
        result = self._do_command(['values'] + list(args))
        if not result:
            return {}
        # noinspection PyTypeChecker
        return dict(item.partition(' ')[::2] for item in result.split('\n'))

    def set(self, name, value=None):
        command = ['set', name]
        if value:
            command.append(value)
        self._do_command(command)

    def get(self, name):
        result = self._do_command(['get', name])
        return result or None  # do it this way so that '' becomes None

    def clear(self, *args):
        self._do_command(['clear'] + list(args))
        return True

    @staticmethod
    def _make_process_dict(socket_info):
        name, args = socket_info.partition(' ')[::2]
        args = dict(item.partition('=')[::2] for item in args.split(' '))
        for key in ('pid',):
            if key in args:
                args[key] = int(args[key])
        return name, args

    def processes(self, *args):
        result = self._do_command(['processes'] + list(args))
        if not result:
            return {}
        # noinspection PyTypeChecker
        return dict(self._make_process_dict(item) for item in result.split('\n'))

    def make_process(self, name, cmd, args=None, env=None, working_dir=None, uid=None, gid=None, rlimits=None, stdout=None, stderr=None, bufsize=None, watch_immediately=None):
        command = ['process', name]
        append_if_not_none(command, working_dir=working_dir, uid=uid, gid=gid, bufsize=bufsize)
        if watch_immediately:
            command.append('watch=1')
        if bufsize != 0:
            if stdout is not None:
                if stdout == DEVNULL:
                    command.append('stdout=0')
                elif stdout != PIPE:
                    raise utils.Error('stdout must be DEVNULL or PIPE')
            if stderr is not None:
                if stderr == DEVNULL:
                    command.append('stderr=0')
                elif stderr == STDOUT:
                    command.append('stderr=stdout')
                elif stderr != PIPE:
                    raise utils.Error('stderr must be DEVNULL, PIPE or STDOUT')
        if env:
            for key, value in env.items():
                command.append('env.{0}={1}'.format(key, wrap_trailing_slash(value)))
        if rlimits:
            for key, value in rlimits.items():
                command.append('rlimit.{0}={1}'.format(key.lower(), value))
        command.append(cmd)
        if args:
            if isinstance(args, string_type):
                command.append(args)
            else:
                try:
                    command.extend(args)
                except TypeError:
                    command.append(str(args))
        return self._make_process_dict(self._do_command(command))[1]

    def close_output_channels(self, *args):
        self._do_command(['close', 'output'] + list(args))
        return True

    def watch(self, *args):
        command = ['watch'] + list(args)
        result = self._do_command(command)
        return result

    def close(self):
        self.sock.close()

    @classmethod
    def set_debug_mode(cls, mode=True, quit_when_connection_closed=False):
        cls._debug_mode = mode
        if quit_when_connection_closed:
            cls._single_connection_mode = True

    @classmethod
    def set_default_port(cls, port):
        cls._default_port_or_path = port

    @classmethod
    def set_default_path(cls, path):
        cls._default_port_or_path = path


def set_debug_mode(mode=True, quit_when_connection_closed=False):
    return Papa.set_debug_mode(mode, quit_when_connection_closed)


def set_default_port(port):
    return Papa.set_default_port(port)


def set_default_path(path):
    return Papa.set_default_path(path)

from papa import utils
s = utils.cast_string
b = utils.cast_bytes
Error = utils.Error

if __name__ == '__main__':
    set_debug_mode(quit_when_connection_closed=True)
    p = Papa()
    print('Sockets: {0}'.format(p.sockets()))
    print('Socket uwsgi: {0}'.format(p.make_socket('uwsgi', interface='eth0')))
    print('Sockets: {0}'.format(p.sockets()))
    print('Socket chaussette: {0}'.format(p.make_socket('chaussette', path='/tmp/chaussette.sock')))
    print('Sockets: {0}'.format(p.sockets()))
    print('Socket uwsgi6: {0}'.format(p.make_socket('uwsgi6', family=socket.AF_INET6)))
    print('Sockets: {0}'.format(p.sockets()))
    try:
        print('Socket chaussette: {0}'.format(p.make_socket('chaussette')))
    except Exception as e:
        print('Caught exception: {0}'.format(e))
    print('Close chaussette: {0}'.format(p.close_socket('chaussette')))
    print('Socket chaussette: {0}'.format(p.make_socket('chaussette')))
    print('Sockets: {0}'.format(p.sockets()))
    print('Processes: {0}'.format(p.processes()))
    print('Values: {0}'.format(p.values()))
    print('Set aack: {0}'.format(p.set('aack', 'bar')))
    print('Get aack: {0}'.format(p.get('aack')))
    print('Get bar: {0}'.format(p.get('bar')))
    print('Values: {0}'.format(p.values()))
    print('Set bar: {0}'.format(p.set('bar', 'barry')))
    print('Get bar: {0}'.format(p.get('bar')))
    print('Values: {0}'.format(p.values()))
    print('Set bar: {0}'.format(p.set('bar')))
    print('Get bar: {0}'.format(p.get('bar')))
    print('Values: {0}'.format(p.values()))
    print('Set aack: {0}'.format(p.set('aack')))
    p.close()
    print('Killed papa')
