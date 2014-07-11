import os.path
import socket
from threading import Lock
from time import sleep
import logging

__author__ = 'Scott Maxwell'

log = logging.getLogger('papa.server')


class Papa(object):
    default_port_or_path = 20202
    spawn_lock = Lock()
    spawned = False

    def __init__(self, port_or_path=None):
        port_or_path = port_or_path or self.default_port_or_path
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
        try:
            self.sock = self._attempt_to_connect()
        except socket.error:
            from papa.server import daemonize_server
            with Papa.spawn_lock:
                if not Papa.spawned:
                    daemonize_server(port_or_path)
                    Papa.spawned = True
            for i in range(50):
                try:
                    self.sock = self._attempt_to_connect()
                    break
                except socket.error:
                    sleep(.1)
            else:
                raise utils.Error('Could not connect to Papa in 5 seconds')
        header = b''
        while not header.endswith(b'\n> '):
            header = self.sock.recv(1024)

    def _attempt_to_connect(self):
        # Try to connect to an existing Papa
        sock = socket.socket(self.family, socket.SOCK_STREAM)
        if self.family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect(self.location)
        return sock

    def _do_command(self, command):
        if isinstance(command, list):
            command = ' '.join(command)
        command = b(command)
        self.sock.sendall(command + b'\n')
        data = b''
        while not data.endswith(b'\n> '):
            data += self.sock.recv(1024)
        data = s(data[:-3])
        if data.startswith('Error:'):
            raise utils.Error(data[7:])
        return data

    @staticmethod
    def _make_socket_dict(socket_info):
        name, args = socket_info.partition(' ')[::2]
        return name, dict(item.partition('=')[::2] for item in args.split(' '))

    def sockets(self):
        result = self._do_command(b'sockets')
        if not result:
            return {}
        return dict(self._make_socket_dict(item) for item in result.split('\n'))

    def make_socket(self, name, host=None, port=None,
                    family=None, socket_type=None,
                    backlog=None, path=None, umask=None,
                    interface=None, so_reuseport=None):
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
        if backlog is not None:
            command.append('backlog={0}'.format(backlog))
        if path:
            if not path.startswith('/'):
                raise utils.Error('Socket path must be absolute')
            command.append('path={0}'.format(path))
            if umask:
                command.append('umask={0}'.format(umask))
        else:
            if host:
                command.append('host={0}'.format(host))
            if port:
                command.append('port={0}'.format(port))
            if so_reuseport:
                command.append('reuseport=1')
            if interface:
                command.append('interface={0}'.format(interface))
        return self._make_socket_dict(self._do_command(command))[1]

    def close_socket(self, name):
        self._do_command(['close socket', name])
        return True

    def values(self):
        result = self._do_command(b'values')
        if not result:
            return {}
        return dict(item.partition(' ')[::2] for item in result.split('\n'))

    def set(self, name, value=None):
        command = ['set', name]
        if value:
            command.append(value)
        self._do_command(command)

    def get(self, name):
        result = self._do_command(['get', name])
        return result or None

    def processes(self):
        result = self._do_command(b'processes')
        if not result:
            return {}
        return result

    def make_process(self):
        pass

    def close_output_channels(self, name):
        self._do_command(['close output', name])
        return True

    def watch(self):
        pass


from papa import utils
s = utils.cast_string
b = utils.cast_bytes

if __name__ == '__main__':
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
    print('Close chaussette: {0}'.format(p.close_socket('chaussette')))
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
