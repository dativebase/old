"""This script contains the imports and globals needed to interact with and old
app via the command line.

See https://groups.google.com/forum/?fromgroups=#!topic/pylons-discuss/kMR9xhIPpD0
"""

from paste.deploy import appconfig
from pylons import config
from old.config.environment import load_environment
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h

conf = appconfig('config:test.ini', relative_to='.')
load_environment(conf.global_conf, conf.local_conf)

# forms = Session.query(model.Form).all()
# etc. ...

print type(h.dateString2date('2012-01-01'))