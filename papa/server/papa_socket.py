import os
import os.path
import socket
import logging
from papa import utils
from papa.utils import partition_and_strip

__author__ = 'Scott Maxwell'

log = logging.getLogger('papa.server')


class PapaSocket(object):
    _sockets_by_name = {}
    _sockets_by_path = {}

    # noinspection PyShadowingBuiltins
    def __init__(self, name, family=None, type='stream', backlog=5,
                 path=None, umask=None,
                 host=None, port=0, interface=None, reuseport=False):

        self.name = name
        if family:
            self.family = utils.valid_families[family]
        else:
            self.family = socket.AF_UNIX if path else socket.AF_INET
        self.socket_type = utils.valid_types[type]
        self.backlog = int(backlog)
        self.path = self.umask = None
        self.host = self.port = self.interface = self.reuseport = None
        self.socket = None

        if self.family == socket.AF_UNIX:
            if not path or not os.path.isabs(path):
                raise utils.Error('Absolute path required for Unix sockets')
            self.path = path
            self.umask = None if umask is None else int(umask)
        else:
            self.host = host if host else '0.0.0.0' if interface else '127.0.0.1'
            self.port = int(port)
            self.interface = interface
            self.reuseport = reuseport if reuseport and hasattr(socket, 'SO_REUSEPORT') else False

    def __str__(self):
        data = [self.name,
                'family={0}'.format(utils.valid_families_by_number[self.family]),
                'type={0}'.format(utils.valid_types_by_number[self.socket_type])]
        if self.backlog is not None:
            data.append('backlog={0}'.format(self.backlog))
        if self.path is not None:
            data.append('path={0}'.format(self.path))
        if self.umask is not None:
            data.append('umask={0}'.format(self.umask))
        if self.host is not None:
            data.append('host={0}'.format(self.host))
        if self.port is not None:
            data.append('port={0}'.format(self.port))
        if self.interface is not None:
            data.append('interface={0}'.format(self.interface))
        if self.reuseport:
            data.append('reuseport={0}'.format(self.reuseport))
        return ' '.join(data)

    def __eq__(self, other):
        # compare all but reuseport, since reuseport might change state on
        # socket start
        return (
            self.name == other.name and
            self.family == other.family and
            self.socket_type == other.socket_type and
            self.backlog == other.backlog and
            self.path == other.path and
            self.umask == other.umask and
            self.host == other.host and
            (self.port == other.port or not self.port) and
            self.interface == other.interface
        )

    def start(self):
        existing = PapaSocket._sockets_by_name.get(self.name)
        if existing:
            if self == existing:
                self.socket = existing.socket
            else:
                raise utils.Error('Socket for {0} has already been created - {1}'.format(self.name, str(existing)))
        else:
            if self.family == socket.AF_UNIX:
                if self.path in PapaSocket._sockets_by_path:
                    raise utils.Error('Socket for {0} has already been created'.format(self.path))
                try:
                    os.unlink(self.path)
                except OSError:
                    if os.path.exists(self.path):
                        raise
                s = socket.socket(self.family, self.socket_type)
                try:
                    if self.umask is None:
                        s.bind(self.path)
                    else:
                        old_mask = os.umask(self.umask)
                        s.bind(self.path)
                        os.umask(old_mask)
                except socket.error as e:
                    raise utils.Error('Bind failed: {0}'.format(e))
                PapaSocket._sockets_by_path[self.path] = self
            else:
                s = socket.socket(self.family, self.socket_type)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if self.interface:
                    import IN
                    if hasattr(IN, 'SO_BINDTODEVICE'):
                        s.setsockopt(socket.SOL_SOCKET, IN.SO_BINDTODEVICE,
                                     self.interface + '\0')
                try:
                    s.bind((self.host, self.port))
                except socket.error as e:
                    raise utils.Error('Bind failed on {0}:{1}: {2}'.format(self.host, self.port, e))
                if not self.port:
                    self.port = s.getsockname()[1]

                if self.reuseport:
                    try:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                        s.close()
                        s = None
                    except socket.error:
                        self.reuseport = False
            s.listen(self.backlog)
            try:
                s.set_inheritable(True)
            except Exception:
                pass
            self.socket = s
            PapaSocket._sockets_by_name[self.name] = self
            log.info('Created socket %s', self)
        return self

    @classmethod
    def close(cls, name):
        try:
            p = cls._sockets_by_name[name]
        except KeyError:
            raise utils.Error('Socket {0} not found'.format(name))
        p.socket.close()
        log.info('Closed socket %s', p)
        if p.path:
            del cls._sockets_by_path[p.path]
        del cls._sockets_by_name[name]

    @classmethod
    def sockets(cls):
        return sorted('{0}'.format(s) for s in cls._sockets_by_name.values())


# noinspection PyUnusedLocal
def socket_command(sock, args):
    """Create a socket to be used by processes.
You need to specify a name, followed by name=value pairs for the connection
options. The name must not contain spaces.

Family and type options are:
    family - should be unix, inet, inet6 (default is unix if path is specified,
             of inet if no path)
    type - should be stream, dgram, raw, rdm or seqpacket (default is stream)
    backlog - specifies the listen backlog (default is 5)

Options for family=unix
    path - must be an absolute path (required)
    umask - override the current umask when creating the socket file

Options for family=inet or family=inet6
    port - if left out, the system will assign a port
    interface - only bind to a single ethernet adaptor
    host - you will usually want the default, which will be 127.0.0.1 if no
           interface it specified and 0.0.0.0 otherwise
    reuseport - on systems that support it, papa will create and bind a new
                socket for each process that uses this socket

The url must start with "tcp:", "udp:" or "unix:".
Examples:
    socket uwsgi port=8080
    socket chaussette path=/tmp/chaussette.sock
"""
    try:
        name, args = partition_and_strip(args)
        kwargs = dict(item.lower().partition('=')[::2] for item in args.split(' ')) if args else {}
        s = PapaSocket(name, **kwargs)
        return str(s.start())
    except Exception as e:
        return 'Error: {0}'.format(e)


# noinspection PyUnusedLocal
def close_socket_command(sock, args):
    try:
        PapaSocket.close(args)
        return 'ok'
    except Exception as e:
        return 'Error: {0}'.format(e)


# noinspection PyUnusedLocal
def sockets_command(sock, args):
    lines = PapaSocket.sockets()
    return '\n'.join(lines) if lines else 'No sockets'
