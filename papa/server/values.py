from papa.utils import partition_and_strip

__author__ = 'Scott Maxwell'

_values = {}


def values_command(sock, args):
    """Return all values stored in Papa"""
    return '\n'.join(sorted('{0} {1}'.format(key, value) for key, value in _values.items()))


def set_command(sock, args):
    """Set or clear a named value. Pass no value to clear.

Examples:
    set count 5
    set count
"""
    name, value = partition_and_strip(args)
    if value:
        _values[name] = value
    else:
        _values.pop(name, None)


def get_command(sock, args):
    """Get a named value.

Example:
    get count
"""
    return _values.get(args)
