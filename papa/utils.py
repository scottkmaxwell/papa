import socket

__author__ = 'Scott Maxwell'


class Error(RuntimeError):
    pass

protocol_map = {
    (socket.AF_INET, socket.SOCK_STREAM): 'tcp',
    (socket.AF_INET, socket.SOCK_DGRAM): 'udp',
}

if not hasattr(socket, 'AF_UNIX'):
    protocol_map[(socket.AF_UNIX, socket.SOCK_STREAM)] = 'unix'

valid_protocols = frozenset(protocol_map.values())


def decode_socket_url(url):
    proto, location = url.partition(':')[::2]
    proto = proto.lower()
    if proto not in valid_protocols:
        raise Error('Unknown protocol: %s (must be %s)' % (proto, ', '.join(valid_protocols)))
    while location and location[0] == '/':
        location = location[1:]
    if not location:
        raise Error('Bad location: %s' % location)
    if proto == 'unix':
        location = '/' + location
    else:
        host, port = location.partition(':')[::2]
        try:
            port = int(port)
        except Exception:
            raise RuntimeError('Must specify a numeric port. For example: %s:%s:8888' % (proto, host))

        if not host:
            host = '127.0.0.1'
        location = (host, port)
    return proto, location


def partition_and_strip(text, delimiter=' '):
    a, b = text.partition(delimiter)[::2]
    return a.strip(), b.strip()
