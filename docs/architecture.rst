================================================================================
Architecture Overview
================================================================================

An OLD web service is, at its core, a database with a particular schema (data
structure) and an interface for interacting with the data stored in the database.
The core features of the OLD: user authentication and authorization; resource
creation, retrieval, update and deletion; input validation; data processing; and
search.

The OLD exposes REST-ful interface styled on the Atom Publishing Protocol.  This
means that all of the "resources" of the OLD (e.g., forms, files, collections,
sources, users, syntactic categories, etc.) are **c**\ reated, **r**\ ead,
**u**\ pdated and **d**\ eleted in a standard way.  The HTTP protocol defines a
small set of "methods" for classifying requests to web servers; relevant to us
here are the POST, GET, PUT and DELETE methods.  Requests to create a new
resource use the POST method, read requests use the GET method, update requests
the PUT method and delete requests the DELETE method.  The table below
illustrates this pattern for the forms resource.

+-------------+----------------+----------------------------------+---------------------------+
| HTTP Method | URL            | Effect                           | Parameters                |
+=============+================+==================================+===========================+
| POST        | /forms         | Create a new form                | JSON object               |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms         | Read all forms                   | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/id      | Read form with id=id             |                           |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/new     | Get data for creating a new form | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/id/edit | Get data for editing form id     | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| PUT         | /forms/id      | Update form with id=id           | JSON object               |
+-------------+----------------+----------------------------------+---------------------------+
| DELETE      | /forms/id      | Delete form with id=id           |                           |
+-------------+----------------+----------------------------------+---------------------------+

Assuming an OLD web service served at http://www.xyz-old.org, an HTTP request to
http://www.xyz-old.org/forms with method POST would result in the system
attempting to create a new linguistic form in the database using the data passed
as JavaScript Object Notation (JSON) in the body of the request.  If the input
data are valid, the system will respond with a JSON representation of the form
with additional (server-generated) attributes (e.g., datetimeModified) included.
If the input data are invalid (or if the user was not authorized to create a
form or some other error occured), the system will respond with an HTTP error
status code and a JSON object in the response body that gives more information
about the error.

As a general rule, the OLD communicates via JSON.  JSON is a widely-used
standard for converting certain data types and (nested) data structures to and from
strings.  Strings, numbers, arrays (lists) and associative arrays (dictionaries)
can all be serialized to a JSON string.  For example, a Python dictionary, i.e.,
a set of key/value pairs such as `{'transcription': 'dog', 'gloss': 'chien'}`
when converted to JSON would be `'{"transcription": "dog", "gloss": "chien"}'`.
In most cases, when an OLD web service requires user input, that input will be
expected to be JSON in the request body.  (In contrast to POST, PUT and DELETE
requests, HTTP GET requests do not, canonically, possess contentful request
bodies; therefore, when optional parameters are permissible on such requests,
the OLD will expect GET parameters in the URL string.)

The application logic of the OLD is written in Python (2.6).  The system uses
the Pylons (1.0) web framework.  Pylons facilitates parsing of HTTP requests and
generation of HTTP responses.  It advocates a Model-View-Controller architecture
where, in the context of the OLD, each resource possesses a model, which governs
the storage and retrieval of a persisted object or resource (e.g., a linguistic
form), as well as a controller, which generates responses to user requests, i.e.,
controls authentication, input validation, data processing, etc.

OLD objects are stored in a relational database.  The system has been tested on
both MySQL and SQLite, though the latter is not suited to a concurrent multi-
user production environment.  The system uses SQLAlchemy (a python module) to
map Python objects to relational database tables.  The FormEncode Python module
is used to validate user input.

The OLD prescribes a particular data structure for organizing linguistic
fieldwork data.  The three core objects are forms, files and collections.  In
brief, forms are textual representations of language data (e.g., morphemes,
words, phrases, sentences)

The OLD prescribes a particular data structure or schema for linguistic
fieldwork data; it validates user input against that schema and ...

A web service is a web-based application
that, unlike a traditional web application, does not require a particular user
interface.  An OLD web service can be accessed via a browser-based application,
a traditional desktop application, an application on a mobile device, a command
line application or even another web application.  As long as the front-end
application can send and receive JSON (JavaScript Object Notation) using the
HTTP protocol and store cookies, the OLD will happily interact with it.

    Note that this is a break from previous versions of the OLD.  In versions 0.1
    through 0.2.7, the OLD was a traditional web application, i.e., it served HTML
    pages as user interface and expected user input as HTML form requests.

The OLD exposes REST-ful interface styled on the Atom Publishing Protocol.  This
means that all of the "resources" of the OLD (e.g., forms, files, collections,
sources, users, syntactic categories, etc.) are **c**\ reated, **r**\ ead,
**u**\ pdated and **d**\ eleted in the same way.  The HTTP protocol defines a
small set of "methods" for classifying requests to web servers; relevant to us
here are the POST, GET, PUT and DELETE methods.  Requests to create a new
resource use the POST method, read requests use the GET method, update requests
the PUT method and delete requests the DELETE method.  The table below
illustrates this pattern for the forms resource.

+-------------+----------------+----------------------------------+---------------------------+
| HTTP Method | URL            | Effect                           | Parameters                |
+=============+================+==================================+===========================+
| POST        | /forms         | Create a new form                | JSON object               |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms         | Read all forms                   | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/id      | Read form with id=id             |                           |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/new     | Get data for creating a new form | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| GET         | /forms/id/edit | Get data for editing form id     | optional GET params       |
+-------------+----------------+----------------------------------+---------------------------+
| PUT         | /forms/id      | Update form with id=id           | JSON object               |
+-------------+----------------+----------------------------------+---------------------------+
| DELETE      | /forms/id      | Delete form with id=id           |                           |
+-------------+----------------+----------------------------------+---------------------------+
