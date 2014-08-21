from papa.utils import wildcard_iter, Error

__author__ = 'Scott Maxwell'


def values_command(sock, args, instance_globals):
    """Return all values stored in Papa"""
    if 'values' in instance_globals:
        return '\n'.join(sorted('{0} {1}'.format(key, value) for key, value in wildcard_iter(instance_globals['values'], args)))


def set_command(sock, args, instance_globals):
    """Set or clear a named value. Pass no value to clear.

Examples:
    set count 5
    set count
"""
    values = instance_globals['values']
    with instance_globals['lock']:
        name = args.pop(0)
        if args:
            values[name] = ' '.join(args)
        else:
            values.pop(name, None)


def clear_command(sock, args, instance_globals):
    """Clear a named value or set of values. You cannot 'clear *'.

Examples:
    clear count
    clear circus.*
"""
    if not args or args == ['*']:
        raise Error('You cannot clear all variables')
    values = instance_globals['values']
    with instance_globals['lock']:
        for name, _ in wildcard_iter(values, args):
            del values[name]


def get_command(sock, args, instance_globals):
    """Get a named value.

Example:
    get count
"""
    with instance_globals['lock']:
        return instance_globals['values'].get(args[0])
