import os.path
import socket
from threading import Lock
from time import sleep
from subprocess import PIPE, STDOUT
from collections import namedtuple
import logging
import select
from papa.utils import string_type, recv_with_retry, send_with_retry

try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = -3

__author__ = 'Scott Maxwell'
__all__ = ['Papa', 'DEBUG_MODE_NONE', 'DEBUG_MODE_THREAD', 'DEBUG_MODE_PROCESS']

log = logging.getLogger('papa.client')
ProcessOutput = namedtuple('ProcessOutput', 'name timestamp data')


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


class Watcher(object):
    def __init__(self, papa_object):
        self.papa_object = papa_object
        self.connection = papa_object.connection
        self.exit_code = {}
        self._fileno = self.connection.sock.fileno()
        self._need_ack = False

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __bool__(self):
        return self.connection is not None

    def __len__(self):
        return 1 if self.connection is not None else 0

    def fileno(self):
        return self.connection.sock.fileno()

    @property
    def ready(self):
        try:
            select.select([self], [], [], 0)
            return True
        except Exception:
            return False

    def read(self):
        self.acknowledge()
        reply = {'out': [], 'err': [], 'closed': []}
        if self.connection:
            line = b''
            while True:
                line = self.connection.get_one_line_response(b'] ')
                split = line.split(':')
                if len(split) < 4:
                    break
                result_type, name, timestamp, data = split
                data = int(data)
                if result_type == 'closed':
                    self.exit_code[name] = data
                else:
                    data = self.connection.read_bytes(data + 1)[:-1]
                result = ProcessOutput(name, float(timestamp), data)
                reply[result_type].append(result)
            self._need_ack = line == '] '
            if not self._need_ack:
                self.connection.read_bytes(2)
                if not self.papa_object.connection:
                    self.papa_object.connection = self.connection
                else:
                    self.connection.close()
                self.connection = None
                return None
        return reply['out'], reply['err'], reply['closed']

    def acknowledge(self):
        if self._need_ack:
            send_with_retry(self.connection.sock, b'\n')
            self._need_ack = False

    def close(self):
        if self.connection:
            # if the server is waiting for an ack, we can
            if self._need_ack:
                send_with_retry(self.connection.sock, b'q\n')
                self._need_ack = False
                self.connection.get_full_response()

                # we can only recover the connection if we were able to send
                # the quit ack. otherwise close the connection and let the
                # socket die
                if not self.papa_object.connection:
                    self.papa_object.connection = self.connection
                else:
                    self.connection.close()
            else:
                self.connection.close()
            self.connection = None


class ClientCommandConnection(object):
    def __init__(self, family, location):
        self.family = family
        self.location = location
        self.sock = self._attempt_to_connect()
        self.data = b''

    def _attempt_to_connect(self):
        # Try to connect to an existing Papa
        sock = socket.socket(self.family, socket.SOCK_STREAM)
        if self.family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.connect(self.location)
            return sock
        except Exception:
            sock.close()
            raise

    def send_command(self, command):
        if isinstance(command, list):
            command = ' '.join(c.replace(' ', '\ ').replace('\n', '\ ') for c in command if c)
        command = b(command)
        send_with_retry(self.sock, command + b'\n')

    def do_command(self, command):
        self.send_command(command)
        return self.get_full_response()

    def get_full_response(self):
        data = self.data
        self.data = b''
        while not data.endswith(b'\n> '):
            new_data = recv_with_retry(self.sock)
            if not new_data:
                raise utils.Error('Lost connection')
            data += new_data

        data = s(data[:-3])
        # noinspection PyTypeChecker
        if data.startswith('Error:'):
            raise utils.Error(data[7:])
        return data

    def get_one_line_response(self, alternate_terminator=None):
        data = self.data
        while b'\n' not in data:
            if alternate_terminator and data.endswith(alternate_terminator):
                break
            new_data = recv_with_retry(self.sock)
            if not new_data:
                raise utils.Error('Lost connection')
            data += new_data

        if data.startswith(b'Error:'):
            self.data = data
            return self.get_full_response()

        data, self.data = data.partition(b'\n')[::2]
        return s(data)

    def read_bytes(self, size):
        data = self.data
        while len(data) < size:
            new_data = recv_with_retry(self.sock, size - len(data))
            if not new_data:
                raise utils.Error('Lost connection')
            data += new_data

        data, self.data = data[:size], data[size:]
        return data

    def push_newline(self):
        self.data = b'\n' + self.data

    def close(self):
        return self.sock.close()


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
        self.connection = None
        self.t = None
        try:
            self.connection = ClientCommandConnection(self.family, self.location)
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
                                log.info('Daemonizing Papa')
                                daemonize_server(port_or_path, fix_title=True)
                            Papa.spawned = True
                try:
                    self.connection = ClientCommandConnection(self.family, self.location)
                    break
                except Exception:
                    sleep(.1)
            if not self.connection:
                log.error('Could not connect to Papa in 5 seconds')
                raise utils.Error('Could not connect to Papa in 5 seconds')
        self.connection.get_full_response()

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if self._single_connection_mode and self.t and not exc_type:
            self.t.join()
            Papa.spawned = False

    def _make_extra_connection(self):
        for i in range(50):
            try:
                self.connection = ClientCommandConnection(self.family, self.location)
                break
            except Exception:
                sleep(.1)
        else:
            raise utils.Error('Could not connect to Papa in 5 seconds')
        self.connection.get_full_response()

    def _attempt_to_connect(self):
        # Try to connect to an existing Papa
        sock = socket.socket(self.family, socket.SOCK_STREAM)
        if self.family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect(self.location)
        return sock

    def _send_command(self, command):
        if not self.connection:
            self._make_extra_connection()
        self.connection.send_command(command)

    def _do_command(self, command):
        if not self.connection:
            self._make_extra_connection()
        return self.connection.do_command(command)

    @staticmethod
    def _make_socket_dict(socket_info):
        name, args = socket_info.partition(' ')[::2]
        args = dict(item.partition('=')[::2] for item in args.split(' '))
        for key in ('backlog', 'port', 'fileno'):
            if key in args:
                args[key] = int(args[key])
        return name, args

    def fileno(self):
        return self.connection.sock.fileno() if self.connection else None

    def list_sockets(self, *args):
        result = self._do_command(['l', 's'] + list(args))
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
        command = ['m', 's', name]
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

    def remove_sockets(self, *args):
        self._do_command(['r', 's'] + list(args))
        return True

    def list_values(self, *args):
        result = self._do_command(['l', 'v'] + list(args))
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

    def remove_values(self, *args):
        self._do_command(['r', 'v'] + list(args))
        return True

    @staticmethod
    def _make_process_dict(socket_info):
        name, arg_string = socket_info.partition(' ')[::2]
        args = {}
        last_key = None
        for item in arg_string.split(' '):
            key, delim, value = item.partition('=')
            if not delim and last_key:
                args[last_key] += ' ' + key
            else:
                last_key = key
                if key == 'pid':
                    value = int(value)
                elif key == 'started':
                    value = float(value)
                elif key in ('running', 'shell'):
                    value = value == 'True'
                args[key] = value
        return name, args

    def list_processes(self, *args):
        result = self._do_command(['l', 'p'] + list(args))
        if not result:
            return {}
        # noinspection PyTypeChecker
        return dict(self._make_process_dict(item) for item in result.split('\n'))

    def make_process(self, name, executable=None, args=None, env=None, working_dir=None, uid=None, gid=None, rlimits=None, stdout=None, stderr=None, bufsize=None, watch_immediately=None):
        command = ['m', 'p', name]
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
        if executable:
            command.append(executable)
        if args:
            if isinstance(args, string_type):
                command.append(args)
            else:
                try:
                    command.extend(args)
                except TypeError:
                    command.append(str(args))
        if watch_immediately:
            return self._do_watch(command)
        return self._make_process_dict(self._do_command(command))[1]

    def remove_processes(self, *args):
        self._do_command(['r', 'p'] + list(args))
        return True

    def watch_processes(self, *args):
        return self._do_watch(['w', 'p'] + list(args))

    def exit_if_idle(self):
        return self._do_command('exit-if-idle').startswith('Exiting')

    def _do_watch(self, command):
        self._send_command(command)
        self.connection.get_one_line_response()
        watcher = Watcher(self)
        self.connection = None
        return watcher

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

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
    # print('Sockets: {0}'.format(p.list_sockets()))
    # print('Socket uwsgi: {0}'.format(p.make_socket('uwsgi', interface='eth0')))
    # print('Sockets: {0}'.format(p.list_sockets()))
    # print('Socket chaussette: {0}'.format(p.make_socket('chaussette', path='/tmp/chaussette.sock')))
    # print('Sockets: {0}'.format(p.list_sockets()))
    # print('Socket uwsgi6: {0}'.format(p.make_socket('uwsgi6', family=socket.AF_INET6)))
    # print('Sockets: {0}'.format(p.list_sockets()))
    # try:
    #     print('Socket chaussette: {0}'.format(p.make_socket('chaussette')))
    # except Exception as e:
    #     print('Caught exception: {0}'.format(e))
    # print('Close chaussette: {0}'.format(p.remove_sockets('chaussette')))
    # print('Socket chaussette: {0}'.format(p.make_socket('chaussette')))
    # print('Sockets: {0}'.format(p.list_sockets()))
    print('Processes: {0}'.format(p.list_processes()))
    # print('Values: {0}'.format(p.list_values()))
    # print('Set aack: {0}'.format(p.set('aack', 'bar')))
    # print('Get aack: {0}'.format(p.get('aack')))
    # print('Get bar: {0}'.format(p.get('bar')))
    # print('Values: {0}'.format(p.list_values()))
    # print('Set bar: {0}'.format(p.set('bar', 'barry')))
    # print('Get bar: {0}'.format(p.get('bar')))
    # print('Values: {0}'.format(p.list_values()))
    # print('Set bar: {0}'.format(p.set('bar')))
    # print('Get bar: {0}'.format(p.get('bar')))
    # print('Values: {0}'.format(p.list_values()))
    # print('Set aack: {0}'.format(p.set('aack')))
    p.close()
    print('Killed papa')
