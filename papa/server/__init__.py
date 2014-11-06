import os
import sys
import socket
from threading import Thread, Lock
import logging
import resource
import papa
from papa.utils import Error, cast_bytes, cast_string, recv_with_retry, send_with_retry
from papa.server import papa_socket, values, proc
import atexit
try:
    # noinspection PyPackageRequirements
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None

__author__ = 'Scott Maxwell'

try:
    from argparse import ArgumentParser
except ImportError:
    from optparse import OptionParser

    class ArgumentParser(OptionParser):
        def add_argument(self, *args, **kwargs):
            return self.add_option(*args, **kwargs)

        # noinspection PyShadowingNames
        def parse_args(self, args=None, values=None):
            return OptionParser.parse_args(self, args, values)[0]

log = logging.getLogger('papa.server')


class CloseSocket(Exception):
    def __init__(self, final_message=None):
        self.final_message = final_message
        super(CloseSocket, self).__init__(self)


# noinspection PyUnusedLocal
def quit_command(sock, args, instance):
    """Close the client socket"""
    raise CloseSocket('ok\n')


# noinspection PyUnusedLocal
def exit_if_idle_command(sock, args, instance):
    """Exit papa if there are no processes, sockets or values"""
    instance_globals = instance['globals']
    if not is_idle(instance_globals):
        return "not idle"
    instance_globals['exit_if_idle'] = True
    raise CloseSocket('Exiting papa!\n> ')


# noinspection PyUnusedLocal
def help_command(sock, args, instance):
    """Show help info"""
    if args:
        try:
            help_for = lookup_command(args, allow_partials=True)
        except Error as e:
            return '{0}\n'.format(e)
        return help_for['__doc__'].strip() if isinstance(help_for, dict) else help_for.__doc__
    return """Possible commands are:
    make socket - Create a socket to be used by processes
    remove sockets - Close and remove sockets by name or file number
    list sockets - List sockets by name or file number
    -----------------------------------------------------
    make process - Launch a process
    remove processes - Stop recording the output of processes by name or PID
    list processes - List processes by name or PID
    watch processes - Start receiving the output of a processes by name or PID
    -----------------------------------------------------
    set - Set a named value
    get - Get a named value
    list values - List values by name
    remove processes - Remove values by name
    -----------------------------------------------------
    quit - Close the client session
    exit-if-idle Exit papa if there are no processes, sockets or values
    help - Type "help <cmd>" for more information

NOTE: All of these commands may be abbreviated. Type at least one character of
      each word. The rest are optional.

After a 'watch' command, just enter '-' and a return to receive more output.
"""


remove_doc = """
Remove the socket, value or process output channel.

You can remove process output channels by name or PID
Examples:
    remove process 3698
    remove process nginx

You can remove sockets by name or file number
Examples:
    remove sockets uwsgi
    remove socket 10

You can remove values by name
Examples:
    remove values uwsgi.*
    remove value aack

All commands can be abbreviated as much as you like, so the above can also be:
    r process 3698
    rem proc nginx
    r sockets uwsgi
    r s 10
    r v uwsgi.*
    re val aack
"""

list_doc = """
List sockets, processes or values.

You can list processes by name or PID
Examples:
    list process 3698
    list processes nginx.*

You can list sockets by name or file number
Examples:
    list socket 10
    list sockets uwsgi.*

You can list values by name
Examples:
    list values uwsgi.*

All commands can be abbreviated as much as you like, so the above can also be:
    l process 3698
    lis proc nginx.*
    l s 10
    l sockets uwsgi.*
    li val uwsgi.*
"""

make_doc = """
Make a new socket or process.

Do 'help make process' or 'help make socket' for details.
"""

watch_doc = """
Watch processes.

You can watch processes by name or PID
Examples:
    watch processes 3698
    watch processes nginx.*

All commands can be abbreviated as much as you like, so the above can also be:
    w process 3698
    wat proc nginx.*
"""


top_level_commands = {
    'list': {
        'sockets': papa_socket.sockets_command,
        'processes': proc.processes_command,
        'values': values.values_command,
        '__doc__': list_doc
    },
    'make': {
        'socket': papa_socket.socket_command,
        'process': proc.process_command,
        '__doc__': make_doc
    },
    'remove': {
        'sockets': papa_socket.close_socket_command,
        'processes': proc.close_output_command,
        'values': values.remove_command,
        '__doc__': remove_doc
    },
    'watch': {
        'processes': proc.watch_command,
        '__doc__': watch_doc
    },
    'set': values.set_command,
    'get': values.get_command,
    'quit': quit_command,
    'exit-if-idle': exit_if_idle_command,
    'help': help_command,
}


def lookup_command(args, commands=top_level_commands, primary_command=None, allow_partials=False):
    cmd = args.pop(0).lower()
    if cmd not in commands:
        for item in sorted(commands):
            if item.startswith(cmd):
                cmd = item
                if cmd == 'exit-if-idle':
                    raise Error('You cannot abbreviate "exit-if-idle"')
                break
        else:
            if primary_command:
                raise Error('Bad "{0}" command. The following word must be one of: {1}'.format(primary_command, ', '.join(sorted(command for command in commands if not command.startswith('__')))))
            else:
                raise Error('Unknown command "{0}"'.format(cmd))

    result = commands[cmd]
    if isinstance(result, dict):
        if args:
            if primary_command:
                cmd = ' '.join((primary_command, cmd))
            return lookup_command(args, result, cmd, allow_partials)
        if not allow_partials:
            raise Error('"{0}" must be followed by one of: {1}'.format(cmd, ', '.join(sorted(command for command in result if not command.startswith('__')))))
    return result


class ServerCommandConnection(object):
    def __init__(self, sock):
        self.sock = sock
        self.data = b''

    def readline(self):
        while not b'\n' in self.data:
            new_data = recv_with_retry(self.sock)
            if not new_data:
                raise socket.error('done')
            self.data += new_data

        one_line, self.data = self.data.partition(b'\n')[::2]
        return cast_string(one_line).strip()


def chat_with_a_client(sock, addr, instance_globals, container):
    connection = ServerCommandConnection(sock)
    instance = {'globals': instance_globals, 'connection': connection}
    try:
        sock.send(b'Papa is home. Type "help" for commands.\n> ')

        while True:
            one_line = connection.readline()
            args = []
            acc = ''
            if one_line:
                for arg in one_line.split(' '):
                    if arg:
                        if arg[-1] == '\\':
                            acc += arg[:-1] + ' '
                        else:
                            acc += arg
                            args.append(acc.strip())
                            acc = ''
                if acc:
                    args.append(acc)

                try:
                    command = lookup_command(args)
                except Error as e:
                    reply = 'Error: {0}\n'.format(e)
                else:
                    try:
                        reply = command(sock, args, instance) or '\n'
                    except CloseSocket as e:
                        if e.final_message:
                            send_with_retry(sock, cast_bytes(e.final_message))
                        break
                    except papa.utils.Error as e:
                        reply = 'Error: {0}\n'.format(e)
                    except Exception as e:
                        reply = 'Error: {0}\n'.format(e)

                if reply[-1] != '\n':
                    reply += '\n> '
                else:
                    reply += '> '
                reply = cast_bytes(reply)
            else:
                reply = b'> '
            send_with_retry(sock, reply)
    except socket.error:
        pass

    try:
        sock.close()
    except socket.error:
        pass

    if container:
        thread_object = container[0]
        instance_globals['active_threads'].remove(thread_object)
        instance_globals['inactive_threads'].append((addr, thread_object))


def cleanup(instance_globals):
    if 'lock' in instance_globals:
        papa_socket.cleanup(instance_globals)


def is_idle(instance_globals):
    with instance_globals['lock']:
        return not instance_globals['processes']\
               and not instance_globals['sockets']['by_name']\
               and not instance_globals['sockets']['by_path']\
               and not instance_globals['values']


def socket_server(port_or_path, single_socket_mode=False):
    instance_globals = {
        'processes': {},
        'sockets': {'by_name': {}, 'by_path': {}},
        'values': {},
        'active_threads': [],
        'inactive_threads': [],
        'lock': Lock(),
        'exit_if_idle': False,
    }
    def local_cleanup():
        cleanup(instance_globals)
    atexit.register(local_cleanup)
    try:
        if isinstance(port_or_path, str):
            try:
                os.unlink(port_or_path)
            except OSError:
                if os.path.exists(port_or_path):
                    raise
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.bind(port_or_path)
            except socket.error as e:
                raise Error('Bind failed: {0}'.format(e))
        else:
            location = ('127.0.0.1', port_or_path)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(location)
            except socket.error as e:
                raise Error('Bind failed or port {0}: {1}'.format(port_or_path, e))
    except Exception as e:
        log.error(e)
        sys.exit(1)

    s.listen(5)
    log.info('Listening')
    while True:
        try:
            sock, addr = s.accept()
            log.info('Started client session with %s:%d', addr[0], addr[1])
            container = []
            instance_globals['exit_if_idle'] = False
            t = Thread(target=chat_with_a_client, args=(sock, addr, instance_globals, container))
            container.append(t)
            instance_globals['active_threads'].append(t)
            t.daemon = True
            t.start()
            s.settimeout(.5)
        except socket.timeout:
            pass
        while instance_globals['inactive_threads']:
            addr, t = instance_globals['inactive_threads'].pop()
            t.join()
            log.info('Closed client session with %s:%d', addr[0], addr[1])
        if not instance_globals['active_threads']:
            if single_socket_mode:
                break
            if instance_globals['exit_if_idle'] and is_idle(instance_globals):
                log.info('Exiting due to exit_if_idle request')
                break
            s.settimeout(None)
    s.close()
    papa_socket.cleanup(instance_globals)
    try:
        # noinspection PyUnresolvedReferences
        atexit.unregister(local_cleanup)
    except AttributeError:
        del instance_globals['lock']


def daemonize_server(port_or_path, fix_title=False):
    process_id = os.fork()
    if process_id < 0:
        raise Error('Unable to fork')
    elif process_id != 0:
        return

    # noinspection PyNoneFunctionAssignment,PyArgumentList
    process_id = os.setsid()
    if process_id == -1:
        sys.exit(1)

    for fd in range(3, resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
        try:
            os.close(fd)
        except OSError:
            pass

    devnull = os.devnull if hasattr(os, 'devnull') else '/dev/null'
    devnull_fd = os.open(devnull, os.O_RDWR)
    for fd in range(3):
        # noinspection PyTypeChecker
        os.dup2(devnull_fd, fd)

    os.umask(0o27)
    os.chdir('/')
    if fix_title and setproctitle is not None:
        # noinspection PyCallingNonCallable
        setproctitle('papa daemon from %s' % os.path.basename(sys.argv[0]))
    socket_server(port_or_path)


def main():
    parser = ArgumentParser('papa', description='A simple parent process for sockets and other processes')
    parser.add_argument('-d', '--debug', action='store_true', help='run in debug mode')
    parser.add_argument('-u', '--unix-socket', help='path to unix socket to bind')
    parser.add_argument('-p', '--port', default=20202, type=int, help='port to bind on localhost (default 20202)')
    parser.add_argument('--daemonize', action='store_true', help='daemonize the papa server')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.debug else logging.ERROR)
    if args.daemonize:
        daemonize_server(args.unix_socket or args.port)
    else:
        try:
            socket_server(args.unix_socket or args.port)
        except Exception as e:
            log.error(e)

if __name__ == '__main__':
    main()
