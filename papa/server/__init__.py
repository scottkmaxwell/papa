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

active_threads = []
inactive_threads = []


class CloseSocket(Exception):
    def __init__(self, final_message=None):
        self.final_message = final_message
        super(CloseSocket, self).__init__(self)


close_commands = {
    'socket': papa_socket.close_socket_command,
    'output': proc.close_output_command,
}


# noinspection PyUnusedLocal
def close_command(sock, args, instance_globals):
    """Close the output channel of the specified process and recover the memory buffer
or a socket.

You can close output channels by name or PID
Examples:
    close output 3698
    close output nginx

You can close sockets by name or file number
Examples:
    close socket uwsgi
    close socket 10
"""
    cmd = args.pop(0)
    command = lookup_command(cmd, close_commands)
    if command:
        return command(sock, args, instance_globals)
    raise Error('Bad close command. The second word must be either "output" or "socket".')


# noinspection PyUnusedLocal
def quit_command(sock, args, instance_globals):
    """Close the client socket"""
    raise CloseSocket('ok\n')


# noinspection PyUnusedLocal
def help_command(sock, args, instance_globals):
    """Show help info"""
    if args:
        help_for = lookup_command(args)
        if not help_for:
            return '"{0}" is an unknown command\n'.format(help_for)
        return help_for.__doc__
    return """Possible commands are:
    socket - Create a socket to be used by processes
    sockets - Show a list of active sockets
    process - Launch a process
    processes - Show a list of active processes
    watch - Start receiving the output of a process
    close - Close a socket or stop recording the output of a process
    values - Return all named values
    set - Set a named value
    get - Get a named value
    quit - Close the client session
    help - Type "help <cmd>" for more information

All of these commands may be abbreviated.

After a 'watch' command, just enter '-' and a return to receive more output.
"""


top_level_commands = {
    'sockets': papa_socket.sockets_command,
    'socket': papa_socket.socket_command,
    'processes': proc.processes_command,
    'process': proc.process_command,
    'watch': proc.watch_command,
    'close': close_command,
    'values': values.values_command,
    'set': values.set_command,
    'get': values.get_command,
    'clear': values.clear_command,
    'quit': quit_command,
    'help': help_command,
}


def lookup_command(cmd, commands=top_level_commands):
    cmd = cmd.lower()
    if cmd in commands:
        return commands[cmd]
    for item in commands:
        if item.startswith(cmd):
            return commands[item]


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

                cmd = args.pop(0).lower()
                command = lookup_command(cmd)
                if command:
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
                else:
                    reply = 'Error: "{0}" is an unknown command\n'.format(cmd)

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
        active_threads.remove(thread_object)
        inactive_threads.append((addr, thread_object))


def cleanup(instance_globals):
    if 'lock' in instance_globals:
        papa_socket.cleanup(instance_globals)


def socket_server(port_or_path, single_socket_mode=False):
    instance_globals = {
        'processes': {},
        'sockets': {'by_name': {}, 'by_path': {}},
        'values': {},
        'lock': Lock()
    }
    atexit.register(cleanup, (instance_globals,))
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
            t = Thread(target=chat_with_a_client, args=(sock, addr, instance_globals, container))
            container.append(t)
            active_threads.append(t)
            t.daemon = True
            t.start()
            s.settimeout(.5)
        except socket.timeout:
            pass
        while inactive_threads:
            addr, t = inactive_threads.pop()
            t.join()
            log.info('Closed client session with %s:%d', addr[0], addr[1])
        if not active_threads:
            if single_socket_mode:
                break
            s.settimeout(None)
    s.close()
    papa_socket.cleanup(instance_globals)
    try:
        # noinspection PyUnresolvedReferences
        atexit.unregister(cleanup)
    except AttributeError:
        del instance_globals['lock']


def daemonize_server(port_or_path):
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
