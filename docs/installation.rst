.. _installation-section:

================================================================================
Installation
================================================================================

Get it
--------------------------------------------------------------------------------

The source code for the OLD can be found on GitHub at
https://github.com/jrwdunham/old.

Pre-packaged eggs of stable OLD releases can be found on the Python Package
index at http://pypi.python.org/pypi/onlinelinguisticdatabase

Egg files are ... p. 472 on creating an egg


Installation & configuration
--------------------------------------------------------------------------------

Note that these installation instructions assume a Unix-based system, i.e.,
Linux or Mac OS X.  If you are using Windows, please refer to the Pylons
or the virtualenv documentation for instructions on how to create and activate
a Python virtual environment and install and download a Pylons application.


Create a virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is generally recommended that you install the OLD using a virtual Python
environment.  A virtual environment is an isolated Python environment within
which you can install the OLD and its dependencies without inadvertently
rendering other programs unworkable by, say, upgrading *their* dependencies
in incompatible ways.

If you do not want to install the OLD and its dependencies in a virtual
environment, skip this step.

Use virtualenv (http://www.virtualenv.org) to create a virtual Python
environment.  First, follow the steps to on the abovementioned web site to
install virtualenv.  If you already have easy_install or pip installed, you can
just run one of the following commands at the terminal.

    pip install virtualenv
    easy_install virtualenv

Otherwise, you can download the virtualenv archive, decompress it, move into
the directory and install it manually, i.e.,:

    cd virtualenv-X.X
    python setup.py install

Once virtualenv is installed, create a virtual environment in a directory called
`env` (or any other name) with the following command:

    virtualenv --no-site-packages env

The virtual environment set up in `env` is packaged with a program called
`easy_install` which, as its name suggests, makes it easy to install Python
packages and their dependencies.  We will use the virtual environment's version
of `easy_install` to install the OLD and its dependencies into the virtual
environment.

There are two ways to do this.  The more explicit and verbose way is to specify
the path to the executables, i.e., run one of the following two commands in
order to invoke Python or easy_install, respectively:

    env/bin/python
    env/bin/easy_install

The easier way is to activate the Python virtual environment by running the
command below.  The `(env)` at the beginning of your command prompt will
indicate that you have activated the virtual environment in `env`.

    source env/bin/activate


Install the OLD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The easiest way to install the OLD is via `easy_install`, as in the command
below.  (Note that from this point on I am assuming that you have activated a
virtual environment in one of the two ways described above or have elected not
to use a virtual environment.)

    easy_install onlinelinguisticdatabase

Once the install has completed, you should see `Finished processing dependencies
for onlinelinguisticdatabase`.


Configure the OLD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that the OLD is installed, we need to configure it.  When the OLD's setup
script is run, several directories will be created in the same directory as the
config file.  Therefore, it is a good idea to create the config file in its own
directory.  Make a new directory and change to it, as follows:

    mkdir old
    cd old

The first step in configuring the OLD is creating a config file.  To create a
config file named `production.ini`, run

    paster make-config onlinelinguisticdatabase production.ini

Now we edit the config file.

The OLD is configured to use MySQL as its database
backend by default.  This entails installing a MySQL server, installing
mysql-python and creating a database.  This is detailed below (**show where**).
In order to just get the OLD up and running and make sure everything is working
ok, I recommend using SQLite and then switching to MySQL for production.  

* virtualenv
* setup-app
* required programs
* optional programs
* configuration via the config file

Serve it
--------------------------------------------------------------------------------

* cf. Pylons book deployment
* Apache proxy to Paster server
* Admin scripts (include?)


Test it
--------------------------------------------------------------------------------

* WebTests
* Requests tests
