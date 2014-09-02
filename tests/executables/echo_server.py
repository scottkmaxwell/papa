import sys
import socket
import select
from papa.utils import cast_string

__author__ = 'Scott Maxwell'

if len(sys.argv) != 2:
    sys.stderr.write('Need one file descriptor\n')
    sys.exit(1)

listen_socket = socket.fromfd(int(sys.argv[1]), socket.AF_INET, socket.SOCK_STREAM)
connection, address = listen_socket.accept()

while True:
    read_sockets = select.select([connection], [], [])[0]
    sock = read_sockets[0]
    data = sock.recv(100)
    if data:
        sock.send(data)
        sys.stdout.write(cast_string(data))
    else:
        break
