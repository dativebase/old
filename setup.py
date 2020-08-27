try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

################################################################################
# Version Config
################################################################################
#
# Set the version of this OLD using the version variable here. The following
# lines then modify the info.py controller so that it stores the appropriate
# version.
import sys, os, re
version = '2.0.0'
p = re.compile('(^\s*[\'"]version[\'"]:\s*[\'"])([0-9\.]+)([\'"].*$)')
wd = os.path.dirname(os.path.realpath(__file__))
infopth = os.path.join(wd, 'onlinelinguisticdatabase', 'controllers', 'info.py')
lines = []
def fixer(match):
    return '%s%s%s' % (match.group(1), version, match.group(3))
with open(infopth) as f:
    for line in f:
        if p.search(line):
            lines.append(p.sub(fixer, line))
        else:
            lines.append(line)
with open(infopth, 'w') as f:
    f.write(''.join(lines))
# Fix the version number in the onlinelinguisticdatabase/__init__.py file too:
pkgfile = os.path.join(wd, 'onlinelinguisticdatabase', '__init__.py')
lines = []
with open(pkgfile) as f:
    for line in f:
        if line.startswith('__version__'):
            lines.append('__version__ = \'%s\'\n' % version)
        else:
            lines.append(line)
with open(pkgfile, 'w') as f:
    f.write(''.join(lines))

setup(
    name='onlinelinguisticdatabase',
    version=version,
    description='''A program for building web services that facilitate collaborative
storing, searching, processing and analyzing of linguistic fieldwork data.''',
    long_description='''\
================================================================================
The Online Linguistic Database (OLD)
================================================================================

A program for building web services that facilitate collaborative storing,
searching, processing and analyzing of linguistic fieldwork data.

Installation and Setup
================================================================================

Install onlinelinguisticdatabase using ``easy_install``::

    easy_install onlinelinguisticdatabase

Make a config file::

    paster make-config onlinelinguisticdatabase production.ini

Tweak the config file as appropriate and then set up the application::

    paster setup-app production.ini

Serve it::

    paster serve production.ini

Open a new terminal window and run the Requests-based test script to ensure that
the OLD application is being served and is operating correctly::

    python _requests_tests.py

You should see ``All requests tests passed.`` as output.

Files
================================================================================
    ''',
    author='Joel Dunham',
    author_email='jrwdunham@gmail.com',
    url='http://www.onlinelinguisticdatabase.org',
    license='Apache v. 2.0',
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Framework :: Pylons",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Topic :: Database :: Front-Ends",
        "Topic :: Education"
    ],
    install_requires=[
        "Beaker==1.10.0",
        "WebTest==1.4.3",  # WebTest 2.0.1 requires WebOb>=1.2 and OLD needs WebOb <=1.1.1 -- conflict
        "Pylons==1.0",
        "MarkupSafe==0.23",
        "FormEncode==1.2.4",    # vs. >= 1.2.5 include changes that break the OLD
        "SQLAlchemy==0.7.9",
        "WebOb==1.1.1",    # The OLD works with v. <= 1.1.1; Pylons 1.0 works with 1.1.1; DeprecationWarning logged :(
        "mysqlclient==1.4.6",
        "Markdown==2.6.5",
        "Pygments==2.0.2",
        "PassLib==1.6.5",
        "docutils==0.12",
        "python-magic==0.4.10",  # interface to libmagic for guessing file type based on contents
        "requests==2.9.0"  # http requests in Python made easy; good for testing a live system
    ],
    setup_requires=["PasteScript==2.0.2"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    package_data={'onlinelinguisticdatabase': ['i18n/*/LC_MESSAGES/*.mo']},
    #message_extractors={'onlinelinguisticdatabase': [
    #        ('**.py', 'python', None),
    #        ('templates/**.mako', 'mako', {'input_encoding': 'utf-8'}),
    #        ('public/**', 'ignore', None)]},
    zip_safe=False,
    paster_plugins=['PasteScript', 'Pylons'],
    entry_points="""
    [paste.app_factory]
    main = onlinelinguisticdatabase.config.middleware:make_app

    [paste.app_install]
    main = pylons.util:PylonsInstaller
    """,
    extras_require = {
        'MySQL': ["mysql-python==1.2.5"]
    } #'PIL': ["PIL"]  # Python Imagine Library (note: easy_install PIL fails for me ...)
)
