try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='onlinelinguisticdatabase',
    version='1.0a',
    description='''A program for building a web service that facilitates collaborative
storing, searching, processing and analyzing of linguistic fieldwork data.''',
    author='Joel Dunham',
    author_email='jrwdunham@gmail.com',
    url='http://www.onlinelinguisticdatabase.org',
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
        "Pylons>=1.0,<=1.0.99",
        "SQLAlchemy>=0.5,<=0.7.9",
        "WebOb<=1.0",
        "Markdown",
        "PassLib",
        "docutils>=0.10"
    ],
    setup_requires=["PasteScript>=1.6.3"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    package_data={'onlinelinguisticdatabase': ['i18n/*/LC_MESSAGES/*.mo']},
    #message_extractors={'old': [
    #        ('**.py', 'python', None),
    #        ('templates/**.mako', 'mako', {'input_encoding': 'utf-8'}),
    #        ('public/**', 'ignore', None)]},
    zip_safe=False,
    paster_plugins=['PasteScript', 'Pylons'],
    entry_points="""
    [paste.app_factory]
    main = old.config.middleware:make_app

    [paste.app_install]
    main = pylons.util:PylonsInstaller
    """,
    extras_require = {
        'MySQL': ["mysql-python>-1.2"],
        'magic': ["python-magic"],   # interface to libmagic for guessing file type based on contents
        'PIL': ["PIL"]  # Python Imaginc Library (note: easy_install PIL fails for me ...)
    }
)
