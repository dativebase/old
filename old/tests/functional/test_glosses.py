from old.tests import *
from nose.tools import nottest

class TestGlossesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('glosses'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('glosses'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_gloss'))

    @nottest
    def test_update(self):
        response = self.app.put(url('gloss', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('gloss', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('gloss', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_gloss', id=1))
