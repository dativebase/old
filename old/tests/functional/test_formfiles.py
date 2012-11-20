from old.tests import *
from nose.tools import nottest

class TestFormfilesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('formfiles'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('formfiles'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_formfile'))

    @nottest
    def test_update(self):
        response = self.app.put(url('formfile', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('formfile', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('formfile', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_formfile', id=1))
