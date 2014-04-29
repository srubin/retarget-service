import os.path
import sys

venv_path = '/var/www/html/srubin/VirtualEnvs/retarget_env'

activate_this = os.path.join(venv_path, 'bin/activate_this.py')
execfile(activate_this, dict(__file__=activate_this))

sys.path.insert(0, '/var/www/html/srubin/retargeting/retarget-service')
sys.path.insert(0, os.path.join(venv_path, 'lib/python2.7/site-packages'))

import os
os.environ['MPLCONFIGDIR']='/tmp'
os.environ['HOME']='/tmp'

from retarget_service import app as application
