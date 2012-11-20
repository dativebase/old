from old.tests import *
from nose.tools import nottest

class TestFormkeywordsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('formkeywords'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('formkeywords'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_formkeyword'))

    @nottest
    def test_update(self):
        response = self.app.put(url('formkeyword', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('formkeyword', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('formkeyword', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_formkeyword', id=1))
