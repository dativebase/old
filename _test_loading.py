"""This script facilitates testing of the SQLAlchemy loading strategies with
respect to the OLD's schema.  Cf. http://docs.sqlalchemy.org/en/rel_0_7/orm/loading.html

My simple tests show that select loading is 2-7x slower than joined/subquery.
They also suggest that subquery is slightly faster than joined across the board.
However, I will follow the advice of the SQLA docs (as I interpret it) and use
the following rules of thumb:

many-to-one:    if the relation will likely be non-NULL, always use subquery
x-to-many:      use subquery if the collections tend to be large; use joined otherwise

Data from tests:
n = 100
timeit number = 100

    lazy            select      joined          subquery
Form.glosses        17.4        4.0, 4.1        3.7, 3.9
Form.elicitor       24.3, 25.7  3.3, 5.8, 3.4   3.5, 3.5, 4.1
Form.files          29.3        4.6, 4.6        3.9, 3.8
Collection.forms    90.9        54.2            45.4

"""

from paste.deploy import appconfig
from pylons import config
from onlinelinguisticdatabase.config.environment import load_environment
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
import timeit

conf = appconfig('config:test.ini', relative_to='.')
load_environment(conf.global_conf, conf.local_conf)


def setUp():
    h.clearAllModels()

def cleanUp():
    h.clearAllModels()


def createCollections(n):
    createForms(n)
    forms = Session.query(model.Form).all()
    for i in range(1, n + 1):
        createCollection(i, forms)
    Session.commit()

def createCollection(i, forms=None, commit=False):
    c = model.Collection()
    c.title = u'title'
    if i % 3 == 0:
        c.forms = forms
    elif i % 2 == 0:
        c.forms = forms[::3]
    else:
        c.forms = forms[:10]
    Session.add(c)
    if commit:
        Session.commit()
    return c

def createForms(n):
    for i in range(1, n + 1):
        createForm(i)
    Session.commit()

def createForm(i, commit=False):
    f = model.Form()
    f.transcription = u'transcription'

    g1 = model.Gloss()
    g1.gloss = u'gloss'
    f.glosses.append(g1)
    if i % 2 == 0:
        g2 = model.Gloss()
        g2.gloss = u'gloss'
        f.glosses.append(g2)

    u = model.User()
    u.name = u'name'
    f.elicitor = u

    if i % 3 == 0:
        f1 = model.File()
        f1.filename = u'file%s-1.wav' % str(i)
        f2 = model.File()
        f2.filename = u'file%s-2.wav' % str(i)
        f3 = model.File()
        f3.filename = u'file%s-3.wav' % str(i)
        f.files = [f1, f2, f3]

    Session.add(f)
    if commit:
        Session.commit()
    return f

def getForms():
    forms = Session.query(model.Form).all()
    #glosses = [f.glosses for f in forms]
    #files = [f.files for f in forms]
    #elicitors = [f.elicitor for f in forms]

def getFormsGlosses():
    forms = Session.query(model.Form).all()
    glosses = [f.glosses for f in forms]

def getFormsElicitor():
    forms = Session.query(model.Form).all()
    elicitors = [f.elicitor for f in forms]

def getFormsFiles():
    forms = Session.query(model.Form).all()
    files = [f.files for f in forms]

def getCollectionsForms():
    collections = Session.query(model.Collection).all()
    forms = [c.forms for c in collections]

def timeForms(n, rel):
    map_ = {'m2o': getFormsElicitor, 'o2m': getFormsGlosses, 'm2m': getFormsFiles}
    setUp()
    createForms(n)
    time = timeit.timeit(map_[rel], number=100)
    print time
    cleanUp()
    print 'done.'

def timeCollections(n, rel):
    map_ = {'m2m': getCollectionsForms}
    setUp()
    createCollections(n)
    time = timeit.timeit(map_[rel], number=100)
    print time
    cleanUp()
    print 'done.'

n = 100

def testCircularity():
    setUp()
    c = model.Collection()
    c.title = u'title'
    fo = model.Form()
    fo.transcription = u'transcription'
    fi = model.File()
    fi.filename = u'filename.wav'
    Session.add_all([c, fo, fi])
    Session.commit()
    fi.collections.append(c)
    fo.files.append(fi)
    c.forms.append(fo)
    Session.commit()
    c = fo = fi = None
    c = Session.query(model.Collection).first()
    print c.forms[0]
    print c.forms[0].files[0]
    print c.forms[0].files[0].collections[0]
    cleanUp()

#testCircularity()
