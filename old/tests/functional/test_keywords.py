from old.tests import *
from nose.tools import nottest

class TestKeywordsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('keywords'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('keywords'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_keyword'))

    @nottest
    def test_update(self):
        response = self.app.put(url('keyword', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('keyword', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('keyword', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_keyword', id=1))
