import socket
import sys

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


def partition_and_strip(text, delimiter=' '):
    a, b = text.partition(delimiter)[::2]
    return a.strip(), b.strip()


if PY2:
    def cast_bytes(s, encoding='utf8'):
        """cast unicode or bytes to bytes"""
        if isinstance(s, unicode):
            return s.encode(encoding)
        return str(s)

    # noinspection PyUnusedLocal
    def cast_unicode(s, encoding='utf8', errors='replace'):
        """cast bytes or unicode to unicode.
          errors options are strict, ignore or replace"""
        if isinstance(s, unicode):
            return s
        return str(s).decode(encoding)

    # noinspection PyUnusedLocal
    def cast_string(s, errors='replace'):
        return s if isinstance(s, basestring) else str(s)

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
