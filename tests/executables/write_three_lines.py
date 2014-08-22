import sys
from time import sleep

__author__ = 'Scott Maxwell'

# with open('aack0.txt', 'w') as f:
#     f.write('ran')

print('Version: %s' % sys.version.partition(' ')[0])
# sys.stdout.flush()
sleep(.1)
# with open('aack1.txt', 'w') as f:
#     f.write('ran')

print('Executable: %s' % sys.executable)
# sys.stdout.flush()
sleep(.1)
# with open('aack2.txt', 'w') as f:
#     f.write('ran')

print('Args: %s' % ' '.join(sys.argv[1:]))
sys.stderr.write('done')
# with open('aack3.txt', 'w') as f:
#     f.write('ran')

# with open('aack.txt', 'w') as f:
#     f.write('ran')
