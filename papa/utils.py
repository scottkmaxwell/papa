import socket
import sys
import select

__author__ = 'Scott Maxwell'

valid_families = dict((name[3:].lower(), getattr(socket, name))
                      for name in dir(socket)
                      if name.startswith('AF_') and getattr(socket, name))
valid_families_by_number = dict((value, name)
                                for name, value in valid_families.items())
valid_types = dict((name[5:].lower(), getattr(socket, name))
                   for name in dir(socket)
                   if name.startswith('SOCK_'))
valid_types_by_number = dict((value, name)
                             for name, value in valid_types.items())

PY2 = sys.version_info[0] < 3


class Error(RuntimeError):
    pass


if PY2:
    def cast_bytes(s, encoding='utf8'):
        """cast unicode or bytes to bytes"""
        # noinspection PyUnresolvedReferences
        if isinstance(s, unicode):
            return s.encode(encoding)
        return str(s)

    # noinspection PyUnusedLocal
    def cast_unicode(s, encoding='utf8', errors='replace'):
        """cast bytes or unicode to unicode.
          errors options are strict, ignore or replace"""
        # noinspection PyUnresolvedReferences
        if isinstance(s, unicode):
            return s
        # noinspection PyUnresolvedReferences
        return str(s).decode(encoding)

    # noinspection PyUnusedLocal
    def cast_string(s, errors='replace'):
        # noinspection PyUnresolvedReferences
        return s if isinstance(s, basestring) else str(s)

    # noinspection PyUnresolvedReferences
    string_type = basestring

else:
    def cast_bytes(s, encoding='utf8'):  # NOQA
        """cast unicode or bytes to bytes"""
        if isinstance(s, bytes):
            return s
        return str(s).encode(encoding)

    def cast_unicode(s, encoding='utf8', errors='replace'):  # NOQA
        """cast bytes or unicode to unicode.
          errors options are strict, ignore or replace"""
        if isinstance(s, bytes):
            return s.decode(encoding, errors=errors)
        return str(s)

    cast_string = cast_unicode
    string_type = str


def extract_name_value_pairs(args):
    var_dict = {}
    while args and '=' in args[0]:
        arg = args.pop(0)
        name, value = arg.partition('=')[::2]
        if value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        var_dict[name] = value
    return var_dict


def wildcard_iter(d, matches, required=False):
    if not matches or matches == '*':
        matched = set(d.keys())
    else:
        matched = set()
        for match in matches:
            if match and match[-1] == '*':
                match = match[:-1]
                if not match:
                    matched = set(d.keys())
                else:
                    for name in d.keys():
                        if name.startswith(match):
                            matched.add(name)
            elif match in d:
                matched.add(match)
            elif required:
                raise Error('{0} not found'.format(match))
    for name in matched:
        yield name, d[name]


def recv_with_retry(sock, size=1024):
    while True:
        try:
            return sock.recv(size)
        except socket.error as e:
            if e.errno == 35:
                select.select([sock], [], [])
            else:
                raise


def send_with_retry(sock, data):
    while data:
        try:
            sent = sock.send(data)
            if sent:
                data = data[sent:]
        except socket.error as e:
            if e.errno == 35:
                select.select([], [sock], [])
            else:
                raise
