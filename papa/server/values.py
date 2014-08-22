from papa.utils import wildcard_iter, Error

__author__ = 'Scott Maxwell'


# noinspection PyUnusedLocal
def values_command(sock, args, instance):
    """Return all values stored in Papa"""
    instance_globals = instance['globals']
    with instance_globals['lock']:
        return '\n'.join(sorted('{0} {1}'.format(key, value) for key, value in wildcard_iter(instance_globals['values'], args)))


# noinspection PyUnusedLocal
def set_command(sock, args, instance):
    """Set or clear a named value. Pass no value to clear.

Examples:
    set count 5
    set count
"""
    instance_globals = instance['globals']
    values = instance_globals['values']
    with instance_globals['lock']:
        name = args.pop(0)
        if args:
            values[name] = ' '.join(args)
        else:
            values.pop(name, None)


# noinspection PyUnusedLocal
def clear_command(sock, args, instance):
    """Clear a named value or set of values. You cannot 'clear *'.

Examples:
    clear count
    clear circus.*
"""
    if not args or args == ['*']:
        raise Error('You cannot clear all variables')
    instance_globals = instance['globals']
    values = instance_globals['values']
    with instance_globals['lock']:
        for name, _ in wildcard_iter(values, args):
            del values[name]


# noinspection PyUnusedLocal
def get_command(sock, args, instance):
    """Get a named value.

Example:
    get count
"""
    instance_globals = instance['globals']
    with instance_globals['lock']:
        return instance_globals['values'].get(args[0])
