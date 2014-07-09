import os
import sys
import socket
from threading import Thread
import logging
from collections import namedtuple
import resource
from papa.server import papa_socket
from papa.utils import Error, partition_and_strip

__author__ = 'Scott Maxwell'

try:
    from argparse import ArgumentParser
except ImportError:
    from optparse import OptionParser

    class ArgumentParser(OptionParser):
        def add_argument(self, *args, **kwargs):
            return self.add_option(*args, **kwargs)

        def parse_args(self, args=None, values=None):
            return OptionParser.parse_args(self, args, values)[0]

log = logging.getLogger('papa.server')

active_threads = []
inactive_threads = []

processes_by_name = {}
processes_by_pid = {}

ProcessInfo = namedtuple('ProcessInfo', 'pid name')


def process_command(sock, args):
    """Start a new process"""
    return 'ok'


# noinspection PyUnusedLocal
def processes_command(sock, args):
    """List all active sockets and processes"""
    lines = []
    for name, proc_list in processes_by_name.items():
        for info in proc_list:
            lines.append('process %s %s (%d)' % (name, info.name, info.pid))
    return '\n'.join(lines) if lines else 'No processes'


def watch_command(sock, args):
    """Watch a process"""
    return 'ok'


# noinspection PyUnusedLocal
def close_command(sock, args):
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
    cmd, args = partition_and_strip(args)
    cmd = cmd.lower()
    if cmd == 'output':
        pass
    elif cmd == 'socket':
        return papa_socket.close_socket_command(sock, args)
    else:
        return 'Bad close command. The second word must be either "output" or "socket".'

    return 'ok'


# noinspection PyUnusedLocal
def quit_command(sock, args):
    """Close the client socket"""
    sock.sendall(b'ok\n')


# noinspection PyUnusedLocal
def help_command(sock, args):
    """Show help info"""
    if args:
        help_for = lookup_command(args)
        if not help_for:
            return '"%s" is an unknown command\n' % help_for
        return help_for.__doc__
    return b"""Possible commands are:
    socket - Create a socket to be used by processes
    process - Launch a process
    sockets - Show a list of active sockets
    processes - Show a list of active processes
    watch - Start receiving the output of a process
    close - Stop recording the output of a process
    quit - Close the client session
    help - Type "help <cmd>" for more information

All of these commands may be abbreviated.

After a 'watch' command, just enter '-' and a return to receive more output.
"""


commands = {
    'socket': papa_socket.socket_command,
    'process': process_command,
    'sockets': papa_socket.sockets_command,
    'processes': processes_command,
    'watch': watch_command,
    'close': close_command,
    'quit': quit_command,
    'help': help_command,
}


def lookup_command(cmd):
    cmd = cmd.lower()
    if cmd in commands:
        return commands[cmd]
    for item in commands:
        if item.startswith(cmd):
            return commands[item]


def chat_with_a_client(sock, addr, container):
    try:
        sock.send(b'Papa is home. Type "help" for commands.\n> ')

        done = False
        while not done:
            data = b''
            while not data.endswith(b'\n'):
                new_data = sock.recv(1024)
                if not new_data:
                    done = True
                    continue
                data += new_data

            data = data.decode()
            data = data.strip()
            cmd, args = partition_and_strip(data)
            cmd = cmd.lower()
            if cmd:
                command = lookup_command(cmd)
                if command:
                    reply = command(sock, args)
                    if not reply:
                        break
                else:
                    reply = '"%s" is an unknown command\n' % cmd

                if isinstance(reply, str):
                    reply = reply.encode()
                if reply[-1:] != b'\n':
                    reply += b'\n> '
                else:
                    reply += b'> '
            else:
                reply = b'> '
            sock.sendall(reply)
    except socket.error:
        pass

    try:
        sock.close()
    except socket.error:
        pass

    thread_object = container[0]
    active_threads.remove(thread_object)
    inactive_threads.append((addr, thread_object))


def socket_server(connection_string):
    try:
        s = papa_socket.make_socket(connection_string)[0]
    except Exception as e:
        log.error(e)
        sys.exit(1)

    s.listen(10)
    log.info('Listening')
    while True:
        try:
            sock, addr = s.accept()
            log.info('Connected with %s:%d', addr[0], addr[1])
            container = []
            t = Thread(target=chat_with_a_client, args=(sock, addr, container))
            container.append(t)
            active_threads.append(t)
            t.daemon = True
            t.start()
            s.settimeout(.5)
        except socket.timeout:
            while inactive_threads:
                addr, t = inactive_threads.pop()
                t.join()
                log.info('Closed %s: %d', addr[0], addr[1])
            if not active_threads:
                s.settimeout(None)

    s.close()


def daemonize_server(connection_string):
    process_id = os.fork()
    if process_id < 0:
        raise Error('Unable to fork')
    elif process_id != 0:
        return

    # noinspection PyNoneFunctionAssignment,PyArgumentList
    process_id = os.setsid()
    if process_id == -1:
        sys.exit(1)

    devnull = os.devnull if hasattr(os, 'devnull') else '/dev/null'
    for fd in range(3, resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
        try:
            os.close(fd)
        except OSError:
            pass

    devnull_fd = os.open(devnull, os.O_RDWR)
    # noinspection PyTypeChecker
    os.dup2(devnull_fd, 0)
    # noinspection PyTypeChecker
    os.dup2(devnull_fd, 1)
    # noinspection PyTypeChecker
    os.dup2(devnull_fd, 2)
    os.umask(0o27)
    os.chdir('/')
    socket_server(connection_string)


def main():
    parser = ArgumentParser('papa', description='A simple parent process for sockets and other processes')
    parser.add_argument('-d', '--debug', action='store_true', help='run in debug mode')
    parser.add_argument('-s', '--socket', default='tcp://localhost:20202', help='socket to bind')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.debug else logging.ERROR)
    try:
        socket_server(connection_string=args.socket)
    except Exception as e:
        log.error(e)


if __name__ == '__main__':
    main()
