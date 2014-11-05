import os
import sys
import os.path
import socket
from time import sleep
try:
    # noinspection PyPackageRequirements
    import unittest2 as unittest
except ImportError:
    import unittest
import select
import papa
from papa.server.papa_socket import unix_socket
from papa.utils import cast_bytes
from tempfile import gettempdir
import logging

logging.basicConfig()
import inspect

isdebugging = False
for frame in inspect.stack():
    if frame[1].endswith("pydevd.py"):
        isdebugging = True
        break

here = os.path.dirname(os.path.realpath(__file__))


class SocketTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    def check_subset(self, expected, result):
        for key, value in expected.items():
            self.assertIn(key, result)
            self.assertEqual(value, result[key])

    def test_inet(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'family': 'inet', 'backlog': 5, 'host': '127.0.0.1'}
            reply = p.make_socket('inet_sock')
            self.check_subset(expected, reply)
            self.assertIn('port', reply)
            p.remove_sockets('inet_sock')
            self.assertDictEqual({}, p.list_sockets())
            reply = p.make_socket('inet_sock', reuseport=True)
            self.check_subset(expected, reply)
            self.assertIn('port', reply)

    def test_inet_interface(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'interface': 'eth0', 'family': 'inet', 'backlog': 5, 'host': '0.0.0.0'}
            self.assertDictEqual({}, p.list_sockets())

            reply = p.make_socket('interface_socket', interface='eth0')
            self.assertIn('port', reply)
            self.assertIn('fileno', reply)
            expected['port'] = reply['port']
            expected['fileno'] = reply['fileno']
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.list_sockets())
            p.remove_sockets('interface_socket')
            self.assertDictEqual({}, p.list_sockets())
            reply = p.make_socket('interface_socket', interface='eth0', port=expected['port'])
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.list_sockets())

    def test_inet6(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'family': 'inet6', 'backlog': 5, 'host': '::1'}
            reply = p.make_socket('inet6_sock', family=socket.AF_INET6)
            self.check_subset(expected, reply)
            self.assertIn('port', reply)
            p.remove_sockets('inet6_sock')
            self.assertDictEqual({}, p.list_sockets())
            reply = p.make_socket('inet6_sock', family=socket.AF_INET6, reuseport=True)
            self.check_subset(expected, reply)
            self.assertIn('port', reply)

    def test_inet6_interface(self):
        with papa.Papa() as p:
            expected = {'type': 'stream', 'interface': 'eth0', 'family': 'inet6', 'backlog': 5, 'host': '::'}
            self.assertDictEqual({}, p.list_sockets())

            reply = p.make_socket('interface_socket', family=socket.AF_INET6, interface='eth0')
            self.assertIn('port', reply)
            self.assertIn('fileno', reply)
            expected['port'] = reply['port']
            expected['fileno'] = reply['fileno']
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'interface_socket': expected}, p.list_sockets())

    @unittest.skipIf(unix_socket is None, 'Unix socket not supported on this platform')
    def test_file_socket(self):
        with papa.Papa() as p:
            path = os.path.join(gettempdir(), 'tst.sock')
            expected = {'path': path, 'backlog': 5, 'type': 'stream', 'family': 'unix'}

            reply = p.make_socket('fsock', path=path)
            self.assertIn('fileno', reply)
            expected['fileno'] = reply['fileno']
            self.assertDictEqual(expected, reply)
            self.assertDictEqual({'fsock': expected}, p.list_sockets())

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
            self.check_subset(expected, reply)
            self.assertIn('port', reply)

            reply = p.make_socket('inet.1')
            self.check_subset(expected, reply)
            self.assertIn('port', reply)

            reply = p.make_socket('other')
            self.check_subset(expected, reply)
            self.assertIn('port', reply)

            reply = p.list_sockets('inet.*')
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1'], sorted(reply.keys()))

            reply = p.list_sockets('other')
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual(['other'], list(reply.keys()))

            reply = p.list_sockets('not_there')
            self.assertEqual({}, reply)

            reply = p.list_sockets('other', 'inet.1')
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['inet.1', 'other'], sorted(reply.keys()))

            reply = p.list_sockets('other', 'inet*')
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))

            reply = p.list_sockets('*')
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))

            reply = p.list_sockets()
            self.assertEqual(3, len(list(reply.keys())))
            self.assertEqual(['inet.0', 'inet.1', 'other'], sorted(reply.keys()))


class ValueTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    def test_value(self):
        with papa.Papa() as p:
            self.assertEqual(None, p.get('aack'))
            self.assertDictEqual({}, p.list_values())

            p.set('aack', 'bar')
            self.assertEqual('bar', p.get('aack'))
            self.assertDictEqual({'aack': 'bar'}, p.list_values())

            p.set('aack2', 'barry')
            self.assertEqual('barry', p.get('aack2'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry'}, p.list_values())

            p.set('aack3', 'larry')
            self.assertEqual('larry', p.get('aack3'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry'}, p.list_values())

            p.set('bar', 'aack')
            self.assertEqual('aack', p.get('bar'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry', 'bar': 'aack'}, p.list_values())

            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry', 'bar': 'aack'}, p.list_values('*'))
            self.assertDictEqual({'aack': 'bar', 'aack2': 'barry', 'aack3': 'larry'}, p.list_values('aack*'))
            self.assertDictEqual({'bar': 'aack'}, p.list_values('b*'))
            self.assertDictEqual({'aack2': 'barry', 'bar': 'aack'}, p.list_values('aack2', 'b*'))

            p.set('aack')
            self.assertEqual(None, p.get('aack'))
            self.assertDictEqual({'aack2': 'barry', 'aack3': 'larry'}, p.list_values('a*'))

            p.remove_values('aack*')
            self.assertDictEqual({'bar': 'aack'}, p.list_values())

    def test_wildcard_clear(self):
        with papa.Papa() as p:
            self.assertRaises(papa.Error, p.remove_values)
            self.assertRaises(papa.Error, p.remove_values, '*')


class ProcessTest(unittest.TestCase):
    def setUp(self):
        papa.set_debug_mode(quit_when_connection_closed=True)

    @staticmethod
    def _merge_lines(output):
        if len(output) > 1:
            by_name = {}
            merged_lines = False
            for line in output:
                by_name.setdefault(line.name, []).append(line)
            for named_lines in by_name.values():
                line_number = 1
                while line_number < len(named_lines):
                    line = named_lines[line_number]
                    prev = named_lines[line_number - 1]
                    if line.timestamp - prev.timestamp > .05:
                        line_number += 1
                    else:
                        named_lines[line_number - 1] = papa.ProcessOutput(prev.name, prev.timestamp, prev.data + line.data)
                        del named_lines[line_number]
                        merged_lines = True
            if merged_lines:
                output = sorted((item for items in by_name.values() for item in items), key=lambda x: x.timestamp)
        return output

    def gather_output(self, watcher):
        out = []
        err = []
        close = []
        while watcher:
            reply = watcher.read()
            if reply:
                out.extend(reply[0])
                err.extend(reply[1])
                close.extend(reply[2])
        return self._merge_lines(out), self._merge_lines(err), close

    if isdebugging:
        _non_debug_gather_output = gather_output

        def _filter_list(self, output):
            remove = []
            for line_number, line in enumerate(output):
                if line.data.startswith(b'pydev debugger: process ') and b'is connecting' in line.data:
                    if line.data.endswith(b'is connecting\n\n'):
                        remove.append(line_number)
                    else:
                        end = line.data.find(b'is connecting\n\n')
                        output[line_number] = papa.ProcessOutput(line.name, line.timestamp, line.data[end + 14:])
            for line_number in reversed(remove):
                del output[line_number]

        def gather_output(self, watcher):
            out, err, close = self._non_debug_gather_output(watcher)
            self._filter_list(out)
            self._filter_list(err)
            return out, err, close

    def test_process_with_out_and_err(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            reply2 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertEqual(reply1['pid'], reply2['pid'])

            self.assertRaises(papa.Error, p.watch_processes, 'not_there')

            with p.watch_processes('write*') as w:
                select.select([w], [], [])
                self.assertTrue(w.ready)
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(3, len(out))
            self.assertEqual(1, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', out[0].name)
            self.assertEqual('write3', out[1].name)
            self.assertEqual('write3', out[2].name)
            self.assertEqual('write3', err[0].name)
            self.assertEqual('write3', close[0].name)
            self.assertLess(out[0].timestamp, out[1].timestamp)
            self.assertLess(out[1].timestamp, out[2].timestamp)
            self.assertLessEqual(out[2].timestamp, err[0].timestamp)
            self.assertLessEqual(out[2].timestamp, close[0].timestamp)
            self.assertLessEqual(err[0].timestamp, close[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out[1].data)
            self.assertEqual(b'Args: \n', out[2].data)
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_none_executable(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', None, args=[sys.executable, 'executables/write_three_lines.py'], working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            reply2 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertEqual(reply1['pid'], reply2['pid'])

            self.assertRaises(papa.Error, p.watch_processes, 'not_there')

            with p.watch_processes('write*') as w:
                select.select([w], [], [])
                self.assertTrue(w.ready)
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(3, len(out))
            self.assertEqual(1, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', out[0].name)
            self.assertEqual('write3', out[1].name)
            self.assertEqual('write3', out[2].name)
            self.assertEqual('write3', err[0].name)
            self.assertEqual('write3', close[0].name)
            self.assertLess(out[0].timestamp, out[1].timestamp)
            self.assertLess(out[1].timestamp, out[2].timestamp)
            self.assertLessEqual(out[2].timestamp, err[0].timestamp)
            self.assertLessEqual(out[2].timestamp, close[0].timestamp)
            self.assertLessEqual(err[0].timestamp, close[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out[1].data)
            self.assertEqual(b'Args: \n', out[2].data)
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_watch_immediately(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            with p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, watch_immediately=True) as w:
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(3, len(out))
            self.assertEqual(1, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', out[0].name)
            self.assertEqual('write3', out[1].name)
            self.assertEqual('write3', out[2].name)
            self.assertEqual('write3', err[0].name)
            self.assertEqual('write3', close[0].name)
            self.assertLess(out[0].timestamp, out[1].timestamp)
            self.assertLess(out[1].timestamp, out[2].timestamp)
            self.assertLessEqual(out[2].timestamp, err[0].timestamp)
            self.assertLessEqual(out[2].timestamp, close[0].timestamp)
            self.assertLessEqual(err[0].timestamp, close[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out[1].data)
            self.assertEqual(b'Args: \n', out[2].data)
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_err_redirected_to_out(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, stderr=papa.STDOUT)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            with p.watch_processes('write*') as w:
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(3, len(out))
            self.assertEqual(0, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', out[0].name)
            self.assertEqual('write3', out[1].name)
            self.assertEqual('write3', out[2].name)
            self.assertEqual('write3', close[0].name)
            self.assertLess(out[0].timestamp, out[1].timestamp)
            self.assertLess(out[1].timestamp, out[2].timestamp)
            self.assertLessEqual(out[2].timestamp, close[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out[1].data)
            self.assertEqual(b'Args: \ndone', out[2].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_no_out(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, stdout=papa.DEVNULL)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            with p.watch_processes('write*') as w:
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(0, len(out))
            self.assertEqual(1, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', err[0].name)
            self.assertEqual('write3', close[0].name)
            self.assertLessEqual(err[0].timestamp, close[0].timestamp)
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_no_buffer(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, bufsize=0)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])

            with p.watch_processes('write*') as w:
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(0, len(out))
            self.assertEqual(0, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', close[0].name)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_two_list_processes_full_output(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3.0', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)

            reply2 = p.make_process('write3.1', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply2)
            self.assertIsInstance(reply2['pid'], int)

            reply = p.list_processes()
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['write3.0', 'write3.1'], sorted(reply.keys()))
            self.assertIn('pid', list(reply.values())[0])
            self.assertIn('pid', list(reply.values())[1])
            self.assertNotEqual(list(reply.values())[0]['pid'], list(reply.values())[1]['pid'])

            with p.watch_processes('write3.*') as w:
                select.select([w], [], [])
                self.assertTrue(w.ready)
                out, err, close = self.gather_output(w)
                exit_code0 = w.exit_code['write3.0']
                exit_code1 = w.exit_code['write3.1']
            self.assertEqual(6, len(out))
            self.assertEqual(2, len(err))
            self.assertEqual(2, len(close))
            self.assertEqual(3, len([item for item in out if item.name == 'write3.0']))
            self.assertEqual(3, len([item for item in out if item.name == 'write3.1']))
            self.assertEqual(1, len([item for item in err if item.name == 'write3.0']))
            self.assertEqual(1, len([item for item in err if item.name == 'write3.1']))
            self.assertEqual(1, len([item for item in close if item.name == 'write3.0']))
            self.assertEqual(1, len([item for item in close if item.name == 'write3.1']))
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(b'done', err[1].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code0)
            self.assertEqual(0, close[1].data)
            self.assertEqual(0, exit_code1)
            self.assertDictEqual({}, p.list_processes())

    def test_two_list_processes_wait_for_one_to_close(self):
        with papa.Papa() as p:
            f = p.fileno()
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3.0', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)

            sleep(.2)
            reply2 = p.make_process('write3.1', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply2)
            self.assertIsInstance(reply2['pid'], int)

            reply = p.list_processes()
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['write3.0', 'write3.1'], sorted(reply.keys()))
            self.assertIn('pid', list(reply.values())[0])
            self.assertIn('pid', list(reply.values())[1])
            self.assertNotEqual(list(reply.values())[0]['pid'], list(reply.values())[1]['pid'])

            with p.watch_processes('write3.*') as w:
                while True:
                    out, err, close = w.read()
                    if close:
                        break
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3.1', list(reply.keys())[0])
            self.assertEqual(f, p.fileno())

    def test_multiple_watchers(self):
        with papa.Papa() as p:
            f = p.fileno()
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3.0', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)

            reply2 = p.make_process('write3.1', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply2)
            self.assertIsInstance(reply2['pid'], int)

            reply = p.list_processes()
            self.assertEqual(2, len(list(reply.keys())))
            self.assertEqual(['write3.0', 'write3.1'], sorted(reply.keys()))
            self.assertIn('pid', list(reply.values())[0])
            self.assertIn('pid', list(reply.values())[1])
            self.assertNotEqual(list(reply.values())[0]['pid'], list(reply.values())[1]['pid'])

            w1 = p.watch_processes('write3.0')
            self.assertEqual(f, w1.fileno())

            w2 = p.watch_processes('write3.1')
            self.assertNotEqual(f, w2.fileno())

            p.set('p1', 't1')
            self.assertNotEqual(f, p.fileno())
            self.assertNotEqual(p.fileno(), w1.fileno())
            self.assertNotEqual(p.fileno(), w2.fileno())

            out1, err1, close1 = self.gather_output(w1)
            out2, err2, close2 = self.gather_output(w2)

            w1.close()
            w2.close()

            self.assertEqual(3, len(out1))
            self.assertEqual(1, len(err1))
            self.assertEqual(1, len(close1))
            self.assertEqual('write3.0', out1[0].name)
            self.assertEqual('write3.0', out1[1].name)
            self.assertEqual('write3.0', out1[2].name)
            self.assertEqual('write3.0', err1[0].name)
            self.assertEqual('write3.0', close1[0].name)
            self.assertLess(out1[0].timestamp, out1[1].timestamp)
            self.assertLess(out1[1].timestamp, out1[2].timestamp)
            self.assertLessEqual(out1[2].timestamp, err1[0].timestamp)
            self.assertLessEqual(out1[2].timestamp, close1[0].timestamp)
            self.assertLessEqual(err1[0].timestamp, close1[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out1[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out1[1].data)
            self.assertEqual(b'Args: \n', out1[2].data)
            self.assertEqual(b'done', err1[0].data)
            self.assertEqual(0, close1[0].data)

            self.assertEqual(3, len(out2))
            self.assertEqual(1, len(err2))
            self.assertEqual(1, len(close2))
            self.assertEqual('write3.1', out2[0].name)
            self.assertEqual('write3.1', out2[1].name)
            self.assertEqual('write3.1', out2[2].name)
            self.assertEqual('write3.1', err2[0].name)
            self.assertEqual('write3.1', close2[0].name)
            self.assertLess(out2[0].timestamp, out2[1].timestamp)
            self.assertLess(out2[1].timestamp, out2[2].timestamp)
            self.assertLessEqual(out2[2].timestamp, err2[0].timestamp)
            self.assertLessEqual(out2[2].timestamp, close2[0].timestamp)
            self.assertLessEqual(err2[0].timestamp, close2[0].timestamp)
            self.assertEqual(b'Version: ' + cast_bytes(sys.version.partition(' ')[0]) + b'\n', out2[0].data)
            self.assertEqual(b'Executable: ' + cast_bytes(sys.executable) + b'\n', out2[1].data)
            self.assertEqual(b'Args: \n', out2[2].data)
            self.assertEqual(b'done', err2[0].data)
            self.assertEqual(0, close2[0].data)
            self.assertDictEqual({}, p.list_processes())

            self.assertEqual('t1', p.get('p1'))

    def test_process_with_small_buffer(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply1 = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ, bufsize=14)
            self.assertIn('pid', reply1)
            self.assertIsInstance(reply1['pid'], int)
            reply = p.list_processes()
            self.assertEqual(1, len(list(reply.keys())))
            self.assertEqual('write3', list(reply.keys())[0])
            self.assertIn('pid', list(reply.values())[0])
            sleep(.5)

            with p.watch_processes('write*') as w:
                select.select([w], [], [])
                self.assertTrue(w.ready)
                out, err, close = self.gather_output(w)
                exit_code = w.exit_code['write3']
            self.assertEqual(1, len(out))
            self.assertEqual(1, len(err))
            self.assertEqual(1, len(close))
            self.assertEqual('write3', out[0].name)
            self.assertEqual('write3', err[0].name)
            self.assertEqual('write3', close[0].name)
            self.assertLessEqual(out[0].timestamp, err[0].timestamp)
            self.assertLessEqual(out[0].timestamp, close[0].timestamp)
            self.assertLessEqual(err[0].timestamp, close[0].timestamp)
            self.assertEqual(b'Args: \n', out[0].data)
            self.assertEqual(b'done', err[0].data)
            self.assertEqual(0, close[0].data)
            self.assertEqual(0, exit_code)
            self.assertDictEqual({}, p.list_processes())

    def test_one_process_two_parallel_watchers(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply)
            self.assertIn('running', reply)
            self.assertIsInstance(reply['pid'], int)
            self.assertIsInstance(reply['running'], bool)

            w1 = p.watch_processes('write*')
            w2 = p.watch_processes('write*')
            out1, err1, close1 = w1.read()
            if isdebugging and not out1 and err1 and err1[0].data.startswith('pydev debugger'):
                out1, err1, close1 = w1.read()
            out2, err2, close2 = w2.read()
            self.assertEqual(out1[0], out2[0])
            w1.close()
            w2.close()

    def test_one_process_two_serial_watchers(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            reply = p.make_process('write3', sys.executable, args='executables/write_three_lines.py', working_dir=here, uid=os.environ['LOGNAME'], env=os.environ)
            self.assertIn('pid', reply)
            self.assertIn('running', reply)
            self.assertIsInstance(reply['pid'], int)
            self.assertIsInstance(reply['running'], bool)

            with p.watch_processes('write*') as w:
                out1, err1, close1 = w.read()
                if isdebugging and not out1 and err1 and err1[0].data.startswith('pydev debugger'):
                    out1, err1, close1 = w.read()
            with p.watch_processes('write*') as w:
                out2, err2, close2 = self.gather_output(w)
            self.assertLess(out1[0].timestamp, out2[0].timestamp)

    def test_echo_server_with_normal_socket(self):
        with papa.Papa() as p:
            reply = p.make_socket('echo_socket')
            self.assertIn('port', reply)
            self.assertIn('fileno', reply)
            port = reply['port']

            reply = p.make_process('echo1', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)
            self.assertIn('pid', reply)

            s = socket.socket()
            s.connect(('127.0.0.1', port))

            s.send(b'test\n')
            msg = b''
            while len(msg) < 5:
                msg += s.recv(5)
            self.assertEqual(b'test\n', msg)

            s.send(b'and do some more\n')
            msg = b''
            while len(msg) < 17:
                msg += s.recv(17)
            self.assertEqual(b'and do some more\n', msg)

            s.close()
            with p.watch_processes('echo*') as w:
                out, err, close = self.gather_output(w)
            self.assertEqual(b'test\nand do some more\n', out[0].data)

    def test_echo_server_with_echo_client(self):
        with papa.Papa() as p:
            reply = p.make_socket('echo_socket')
            self.assertIn('port', reply)
            self.assertIn('fileno', reply)

            reply = p.make_process('echo.server', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)
            self.assertIn('pid', reply)

            reply = p.make_process('echo.client', sys.executable, args=('executables/echo_client.py', '$(socket.echo_socket.port)'), working_dir=here)
            self.assertIn('pid', reply)

            with p.watch_processes('echo.*') as w:
                out, err, close = self.gather_output(w)
            self.assertEqual(2, len(out))
            self.assertEqual(2, len(close))
            self.assertEqual(b'howdy\n', out[0].data)
            self.assertEqual(b'howdy\n', out[1].data)
            self.assertIn(out[0].name, ('echo.client', 'echo.server'))
            self.assertIn(out[1].name, ('echo.client', 'echo.server'))
            self.assertNotEqual(out[0].name, out[1].name)

    def test_echo_server_with_reuseport(self):
        with papa.Papa() as p:
            reply = p.make_socket('echo_socket', reuseport=True)
            self.assertIn('port', reply)
            port = reply['port']

            reply = p.make_process('echo1', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)
            self.assertIn('pid', reply)

            s = socket.socket()
            s.connect(('127.0.0.1', port))

            s.send(b'test\n')
            msg = b''
            while len(msg) < 5:
                msg += s.recv(5)
            self.assertEqual(b'test\n', msg)

            s.send(b'and do some more\n')
            msg = b''
            while len(msg) < 17:
                msg += s.recv(17)
            self.assertEqual(b'and do some more\n', msg)

            s.close()
            with p.watch_processes('echo*') as w:
                out, err, close = self.gather_output(w)
            self.assertEqual(b'test\nand do some more\n', out[0].data)

    def test_process_with_close_output_late(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            socket_reply = p.make_socket('echo_socket')
            p.make_process('echo', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)

            s = socket.socket()
            s.connect(('127.0.0.1', socket_reply['port']))

            s.send(b'test\n')
            msg = b''
            while len(msg) < 5:
                msg += s.recv(5)
            self.assertEqual(b'test\n', msg)
            s.close()

            sleep(.2)
            p.remove_processes('echo')
            self.assertDictEqual({}, p.list_processes())

    def test_process_with_close_output_early(self):
        with papa.Papa() as p:
            self.assertDictEqual({}, p.list_processes())
            socket_reply = p.make_socket('echo_socket')
            p.make_process('echo', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)
            p.remove_processes('echo')

            s = socket.socket()
            s.connect(('127.0.0.1', socket_reply['port']))

            s.send(b'test\n')
            msg = b''
            while len(msg) < 5:
                msg += s.recv(5)
            self.assertEqual(b'test\n', msg)
            s.close()

            sleep(.2)
            self.assertDictEqual({}, p.list_processes())

    def test_bad_socket_reference(self):
        with papa.Papa() as p:
            self.assertRaises(papa.Error, p.make_process, 'bad', sys.executable, args=('executables/echo_server.py', '$(socket.echo_socket.fileno)'), working_dir=here)

    def test_bad_process(self):
        with papa.Papa() as p:
            self.assertRaises(papa.Error, p.make_process, 'bad', sys.executable + '-blah')

    def test_bad_working_dir(self):
        with papa.Papa() as p:
            self.assertRaises(papa.Error, p.make_process, 'bad', sys.executable, working_dir=here + '-blah')

if __name__ == '__main__':
    unittest.main()
