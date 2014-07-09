import os
import socket
import logging
from papa.utils import decode_socket_url, Error, partition_and_strip
from collections import namedtuple

__author__ = 'Scott Maxwell'

SocketInfo = namedtuple('SocketInfo', 'sock proto location name fileno')
log = logging.getLogger('papa.server')

sockets_by_name = {}
sockets_by_fileno = {}
unix_socket_by_path = {}


def make_socket(url, umask=None):
    proto, location = decode_socket_url(url)
    if proto == 'unix':
        if location in unix_socket_by_path:
            raise Error('Socket %s has already been created' % location)
        try:
            os.unlink(location)
        except OSError:
            if os.path.exists(location):
                raise
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(location)
        except socket.error as e:
            raise Error('Bind failed: %s' % e)
        unix_socket_by_path[location] = s
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM if proto == 'tcp' else socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(location)
            # noinspection PyStringFormat
            location = '%s:%d' % location
        except socket.error as e:
            raise Error('Bind failed: %s - %s' % (e, url))
    return s, proto, location


# noinspection PyUnusedLocal
def socket_command(sock, args):
    """Create a socket to be used by processes.
You need to specify a name and a url. The name must not contain spaces.
The url must start with "tcp:", "udp:" or "unix:".
Examples:
    socket uwsgi tcp://localhost:8080
    socket uwsgi unix:///tmp/uwsgi.sock
"""
    name, url = partition_and_strip(args)
    try:
        new_sock, proto, location = make_socket(url)
    except Exception as e:
        return str(e)
    log.info('Created socket %s' % args)
    fileno = new_sock.fileno()
    info = SocketInfo(new_sock, proto, location, name, fileno)
    sockets_by_name.setdefault(name, []).append(info)
    sockets_by_fileno[fileno] = info
    # Python 3.4 defaults to non-inheritable
    try:
        new_sock.set_inheritable(True)
    except Exception:
        pass
    return str(fileno)


# noinspection PyUnusedLocal
def close_socket_command(sock, args):
    if args in sockets_by_name:
        for info in sockets_by_name[args]:
            info.sock.close()
            logging.info('Closed socket %s %s://%s', info.name, info.proto, info.location)
            if info.proto == 'unix':
                del unix_socket_by_path[info.location]
            del sockets_by_fileno[info.fileno]
        del sockets_by_name[args]
    else:
        info = None
        try:
            fileno = int(args)
            info = sockets_by_fileno[fileno]
        except Exception:
            return 'Socket %s not found' % args
        info.sock.close()
        logging.info('Closed socket %s %s://%s', info.name, info.proto, info.location)
        if info.proto == 'unix':
            del unix_socket_by_path[info.location]
        sockets_by_name[info.name].remove(info)
        del sockets_by_fileno[fileno]
    return 'ok'


def sockets_command(sock, args):
    lines = ['%s %s:%s (%d)' % (info.name, info.proto, info.location, info.fileno) for name, sock_list in sockets_by_name.items() for info in sock_list]
    return '\n'.join(lines) if lines else 'No sockets'
