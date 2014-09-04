import sys
from time import sleep

__author__ = 'Scott Maxwell'

print('Version: %s' % sys.version.partition(' ')[0])
sys.stdout.flush()
sleep(.1)

print('Executable: %s' % sys.executable)
sys.stdout.flush()
sleep(.1)

print('Args: %s' % ' '.join(sys.argv[1:]))
sys.stdout.flush()

sys.stderr.write('done')
