import sys
import socket
from papa.utils import cast_string, send_with_retry, recv_with_retry

__author__ = 'Scott Maxwell'

if len(sys.argv) != 2:
    sys.stderr.write('Need one port number\n')
    sys.exit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', int(sys.argv[1])))

send_with_retry(sock, b'howdy\n')
data = recv_with_retry(sock)
sys.stdout.write(cast_string(data))

sock.close()
