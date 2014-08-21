import os
import sys
import os.path
import socket
import unittest
import papa
from papa.server.papa_socket import unix_socket
from tempfile import gettempdir

here = os.path.dirname(os.path.realpath(__file__))


class SocketTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    def test_inet(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'family': 'inet', 'backlog': 5, 'host': '127.0.0.1'}
            reply = p.make_socket('inet_sock')
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)
            p.close_socket('inet_sock')
            self.assertDictEqual({}, p.sockets())
            reply = p.make_socket('inet_sock', reuseport=True)
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)

    def test_inet_interface(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'interface': 'eth0', 'family': 'inet', 'backlog': 5, 'host': '0.0.0.0'}
            self.assertDictEqual({}, p.sockets())

            reply = p.make_socket('interface_socket', interface='eth0')
            self.assertIn('port', reply)
            expected['port'] = reply['port']
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.sockets())
            p.close_socket('interface_socket')
            self.assertDictEqual({}, p.sockets())
            reply = p.make_socket('interface_socket', interface='eth0', port=expected['port'])
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.sockets())

    def test_inet6(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'family': 'inet6', 'backlog': 5, 'host': '::1'}
            reply = p.make_socket('inet6_sock', family=socket.AF_INET6)
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)
            p.close_socket('inet6_sock')
            self.assertDictEqual({}, p.sockets())
            reply = p.make_socket('inet6_sock', family=socket.AF_INET6, reuseport=True)
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)

    def test_inet6_interface(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'interface': 'eth0', 'family': 'inet6', 'backlog': 5, 'host': '::'}
            self.assertDictEqual({}, p.sockets())

            reply = p.make_socket('interface_socket', family=socket.AF_INET6, interface='eth0')
            self.assertIn('port', reply)
            expected['port'] = reply['port']
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.sockets())

    @unittest.skipIf(unix_socket is None, 'Unix socket not supported on this platform')
    def test_file_socket(self):
        with papa.Papa() as p:
            path = os.path.join(gettempdir(), 'tst.sock')
            expected = {'path': path, 'backlog': 5, 'type': 'stream', 'family': 'unix'}

            reply = p.make_socket('fsock', path=path)
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'fsock': expected}, p.sockets())

            self.assertRaises(papa.Error, p.make_socket, 'fsock', path='path')

    def test_already_exists(self):
        with papa.Papa() as p:
            reply = p.make_socket('exists_sock')
            self.assertDictEqual(reply, p.make_socket('exists_sock'))
            self.assertRaises(papa.Error, p.make_socket, 'exists_sock', family=socket.AF_INET6)

    def test_wildcard(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'family': 'inet', 'backlog': 5, 'host': '127.0.0.1'}

            reply = p.make_socket('inet.0')
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)

            reply = p.make_socket('inet.1')
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)

            reply = p.make_socket('other')
            self.assertDictContainsSubset(expected, reply)
            self.assertIn('port', reply)

            reply = p.sockets('inet.*')
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1'], sorted(reply.keys()))

            reply = p.sockets('other')
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual(['other'], list(reply.keys()))

            reply = p.sockets('not_there')
            self.assertEqual({}, reply)

            reply = p.sockets('other', 'inet.1')
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['inet.1', 'other'], sorted(reply.keys()))

            reply = p.sockets('other', 'inet*')
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))

            reply = p.sockets('*')
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))

            reply = p.sockets()
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))


class ValueTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    def test_value(self):
        with papa.Papa() as p:
            self.assertEqual(None, p.get('aack'))
            self.assertDictEqual({}, p.values())

            p.set('aack', 'bar')
            self.assertEqual('bar', p.get('aack'))
            self.assertDictEqual({'aack': 'bar'}, p.values())

            p.set('aack2', 'barry')
            self.assertEqual('barry', p.get('aack2'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry'}, p.values())

            p.set('aack3', 'larry')
            self.assertEqual('larry', p.get('aack3'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry'}, p.values())

            p.set('bar', 'aack')
            self.assertEqual('aack', p.get('bar'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry', 'bar': 'aack'}, p.values())

            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry', 'bar': 'aack'}, p.values('*'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry'}, p.values('aack*'))
            self.assertDictEqual({'bar': 'aack'}, p.values('b*'))
            self.assertDictEqual({'aack2': 'barry', 'bar': 'aack'}, p.values('aack2', 'b*'))

            p.set('aack')
            self.assertEqual(None, p.get('aack'))
            self.assertDictEqual({'aack2': 'barry', 'aack3': 'larry'}, p.values('a*'))

            p.clear('aack*')
            self.assertDictEqual({'bar': 'aack'}, p.values())

    def test_wildcard_clear(self):
        with papa.Papa() as p:
            self.assertRaises(papa.Error, p.clear)
            self.assertRaises(papa.Error, p.clear, '*')


class ProcessTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    def test_process(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.processes())
            reply1 = p.make_process('write3', sys.executable, args='write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, out='1m', err=0)
            self.assertIn('pid', reply1)
            self.assertTrue(isinstance(reply1['pid'], int))
            reply = p.processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            reply2 = p.make_process('write3', sys.executable, args='write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, out='1m', err=0)
            self.assertDictEqual(reply1, reply2)

if __name__ == '__main__':
    unittest.main()
