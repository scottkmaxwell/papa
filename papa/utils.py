import socket

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


class Error(RuntimeError):
    pass


def partition_and_strip(text, delimiter=' '):
    a, b = text.partition(delimiter)[::2]
    return a.strip(), b.strip()
