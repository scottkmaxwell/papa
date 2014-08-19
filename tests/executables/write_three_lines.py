__author__ = 'Scott Maxwell'

import sys
print('Version: %s' % sys.version.partition(' ')[0])
print('Executable: %s' % sys.executable)
print('Args: %s' % ' '.join(sys.argv[1:]))

# with open('aack.txt', 'w') as f:
#     f.write('ran')
