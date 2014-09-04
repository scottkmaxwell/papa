import sys
import socket
from papa.utils import cast_string, send_with_retry, recv_with_retry

__author__ = 'Scott Maxwell'

if len(sys.argv) != 2:
    sys.stderr.write('Need one file descriptor\n')
    sys.exit(1)

listen_socket = socket.fromfd(int(sys.argv[1]), socket.AF_INET, socket.SOCK_STREAM)
sock, address = listen_socket.accept()

while True:
    data = recv_with_retry(sock)
    if data:
        send_with_retry(sock, data)
        sys.stdout.write(cast_string(data))
    else:
        break

sock.close()
