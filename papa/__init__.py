import socket
from threading import Lock
from time import sleep
import logging

__author__ = 'Scott Maxwell'

log = logging.getLogger('papa.server')


class Papa(object):
    default_connection_string = 'tcp::20202'
    spawn_lock = Lock()
    spawned = False

    def __init__(self, connect_to=None):
        connect_to = connect_to or self.default_connection_string
        self.proto, self.location = utils.decode_socket_url(connect_to)
        if self.proto == 'udp':
            raise utils.Error('Unknown protocol: udp (must be "unix" or "tcp")')

        # Try to connect to an existing Papa
        self.sock = None
        try:
            self.sock = self._attempt_to_connect()
        except socket.error:
            from papa.server import daemonize_server
            with Papa.spawn_lock:
                if not Papa.spawned:
                    daemonize_server(connect_to)
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
        if self.proto == 'unix':
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.connect(self.location)
        return s

    def _do_command(self, command):
        if isinstance(command, list):
            command = ' '.join(command)
        if isinstance(command, str):
            command = command.encode()
        self.sock.sendall(command + b'\n')
        data = b''
        while not data.endswith(b'\n> '):
            data += self.sock.recv(1024)
        return data[:-3]

    def sockets(self):
        result = self._do_command(b'sockets')
        return result

    def processes(self):
        result = self._do_command(b'processes')
        return result

    def make_socket(self, name, host='', port=0,
                    family=socket.AF_INET, type=socket.SOCK_STREAM,
                    backlog=0, path=None, umask=None,
                    interface=None, so_reuseport=False):
        try:
            proto = utils.protocol_map[(family, type)]
        except KeyError:
            raise utils.Error('Invalid family/type pair')
        if not name:
            raise utils.Error('Socket requires a name')
        command = ['socket', name]
        if backlog:
            command.append('backlog=%d' % backlog)
        if proto == 'unix':
            if umask:
                command.append('umask=%d' % umask)
            if not path.startswith('/'):
                raise utils.Error('Socket path must be absolute')
            command.append('%s:%s' % (proto, path))
        else:
            if not port:
                raise utils.Error('Socket must have a non-zero port')
            if so_reuseport:
                command.append('reuseport=1')
            if interface:
                command.append('interface=%s' % interface)
            command.append('%s:%s:%d' % (proto, host, port))
        result = self._do_command(command)
        return result

    def make_process(self):
        pass

    def close_socket(self):
        pass

    def close_output_channel(self):
        pass

    def watch(self):
        pass


from papa import utils

if __name__ == '__main__':
    p = Papa()
    print(p.sockets())
    print(p.make_socket('uwsgi', port=8080))
    print(p.sockets())
    print(p.processes())
    print('Got it!')
