# -*- coding: utf-8 -*-
"""
    test
    ~~~~~~~~~~~~~~
    
    This package tests the correctness of utility functions and the behaviour
    of the blog to certain requests.
    
    :copyright: (c) 2010 by Eugen Kiss.
    :license: LICENSE_NAME, see LICENSE_FILE for more details.
"""
from __future__ import with_statement
import unittest
import datetime
import tempfile
import os

from flask import g

from simblin import create_app, helpers


class PasswordTestCase(unittest.TestCase):
    
    def test_password_functions(self):
        """Check the integrity of the password functions"""
        raw_password = 'passworD546$!!.,.'
        hash = helpers.set_password(raw_password)
        self.assertTrue(helpers.check_password(raw_password, hash))
        self.assertFalse(helpers.check_password('abc', hash))
        
        
class NormalizeTestCase(unittest.TestCase):
    
    def test_slug_normalizing(self):
        self.assertEqual(helpers.normalize(''), '')
        self.assertEqual(helpers.normalize('dadada'), 'dadada')
        self.assertEqual(helpers.normalize('DaDaDa'), 'dadada')
        self.assertEqual(helpers.normalize('The house'), 'the-house')
        self.assertEqual(helpers.normalize('The  house'), 'the-house')
        self.assertEqual(helpers.normalize(' 123-name '), '123-name')
        # TODO: test special symbols like ? & = <> /
    
    def test_tags_normalizing(self):
        """
        Test the correct interpretation of a string of comma separated tags
        """
        self.assertEqual(helpers.normalize_tags(''), [])
        self.assertEqual(helpers.normalize_tags(','), [])
        self.assertEqual(helpers.normalize_tags('cool'), ['cool'])
        self.assertEqual(helpers.normalize_tags('cool,cool'), ['cool'])
        self.assertEqual(
            helpers.normalize_tags('cool, cooler'), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags('cool, cooler '), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags('cool, cooler ,'), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags('cool, cooler ,  '), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags(',cool, cooler ,  '), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags(' ,cool, cooler ,,  '), ['cool', 'cooler'])
        self.assertEqual(
            helpers.normalize_tags("django, franz und bertha,vil/bil"),
            ['django','franz-und-bertha','vil-bil'])
            

class BlogTestCase(unittest.TestCase):
    
    def setUp(self):
        """Before each test, set up a blank database"""
        class config:
            DATABASE = ''
        self.db_fd, config.DATABASE = tempfile.mkstemp()
        self.app = create_app(config)
        self.client = self.app.test_client()
        helpers.init_db(self.app.config['DATABASE'])
        self.db = helpers.connect_db(self.app.config['DATABASE'])
        self._ctx = self.app.test_request_context()
        self._ctx.push()

    def tearDown(self):
        """Get rid of the database again after each test."""
        os.close(self.db_fd)
        os.unlink(self.app.config['DATABASE'])
        self._ctx.pop()
    
    # helper functions
    
    def query_db(self, query, args=(), one=False):
        return helpers.query_db(query, args, one, db=self.db)
    
    def cleardb(self):
        """Remove all rows inside the database"""
        helpers.init_db(self.app.config['DATABASE'])
    
    def register(self, username, password, password2=None):
        """Helper function to register a user"""
        return self.client.post('/register', data=dict(
            username=username,
            password=password,
            password2=password2
        ), follow_redirects=True)
    
    def login(self, username, password):
        """Helper function to login"""
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)
        
    def register_and_login(self, username, password):
        """Registers and logs in in one go"""
        self.register(username, password, password)
        self.login(username, password)

    def logout(self):
        """Helper function to logout"""
        return self.client.get('/logout', follow_redirects=True)
    
    def add_entry(self, title, markdown, tags):
        """Helper functions to create a blog post"""
        return self.client.post('/compose', data=dict(
            title=title,
            markdown=markdown,
            tags=tags,
            id=''
        ), follow_redirects=True)
    
    def update_entry(self, title, markdown, tags, id):
        """Helper functions to create a blog post"""
        return self.client.post('/compose', data=dict(
            title=title,
            markdown=markdown,
            tags=tags,
            id=id
        ), follow_redirects=True)
        
# TODO: Test entry view

class RegisterTestCase(BlogTestCase):
    
    def test_redirect(self):
        """
        If there is no admin yet the visitor shall be redirected 
        to the register page.
        """
        rv = self.client.get('/', follow_redirects=True)
        assert 'Register' in rv.data
    
    def test_registering(self):
        rv = self.register('', 'password')
        assert 'You have to enter a username' in rv.data
        rv = self.register('britney spears', '')
        assert 'You have to enter a password' in rv.data
        rv = self.register('barney', 'abv', 'abc')
        assert 'Passwords must match' in rv.data
        rv = self.register('barney', 'abc', 'abc')
        assert 'You are the new master of this blog' in rv.data
        rv = self.register('barney', 'abc', 'abc')
        assert 'There can only be one admin' in rv.data
        

class LoginTestCase(BlogTestCase):
    
    def test_login(self):
        self.register('barney', 'abc', 'abc')
        rv = self.login('borney', 'abc')
        assert 'Invalid username' in rv.data
        rv = self.login('barney', 'abd')
        assert 'Invalid password' in rv.data
        rv = self.login('barney', 'abc')
        assert 'You have been successfully logged in' in rv.data
        # TODO: Test if session.logged_in has been set
        rv = self.logout()
        assert 'You have been successfully logged out' in rv.data
        
        
class ComposingTestCase(BlogTestCase):
    
    def test_validation(self):
        """Check if form validation and validation in general works"""
        self.cleardb();
        self.register_and_login('barney', 'abc')
        rv = self.add_entry(title='', markdown='a', tags='b')
        assert 'You must provide a title' in rv.data
        rv = self.add_entry(title='a', markdown='', tags='')
        assert 'New entry was successfully posted' in rv.data
        rv = self.update_entry(title='a', markdown='', tags='', id=999)
        assert 'Invalid id' in rv.data
        rv = self.client.get('/compose?id=999')
        assert 'Invalid id' in rv.data
        
    def test_conversion(self):
        """
        Test the blog post's fields' correctness after adding/updating an entry
        """
        self.cleardb();
        self.register_and_login('barney', 'abc')
        
        title = "My entry"
        markdown = "# Title"
        tags = "django, franz und bertha,vil/bil"
        expected_id = 1
        expected_title = title
        expected_markdown = markdown
        expected_tags = ['django','franz-und-bertha','vil-bil']
        expected_slug = "my-entry"
        expected_html = "<h1>Title</h1>"
        expected_date = datetime.date.today()
        rv = self.add_entry(title=title, markdown=markdown, tags=tags)
        
        entry = self.query_db('SELECT * FROM entries', one=True)
        self.assertEqual(entry['id'], expected_id)
        self.assertEqual(entry['title'], expected_title)
        self.assertEqual(entry['markdown'], expected_markdown)
        self.assertEqual(entry['slug'], expected_slug)
        assert expected_html in entry['html']
        self.assertEqual(entry['published'].date(), expected_date)
        tags = helpers.get_tags(entry['id'], db=self.db)
        self.assertEqual(tags, expected_tags)
        
        # Add another entry with the same fields but expect a different slug
        # and the same number of tags inside the database
        
        expected_slug2 = expected_slug + '-2'
        tags2 = "django, franz und bertha"
        self.add_entry(title=title, markdown=markdown, tags=tags2)

        entry = self.query_db('SELECT * FROM entries WHERE id=2', one=True)
        self.assertEqual(entry['title'], expected_title) 
        self.assertEqual(entry['slug'], expected_slug2)
        all_tags = self.query_db('SELECT * FROM tags')
        self.assertEqual(len(all_tags), 3)    
        
        # Add yet another entry with the same title and expect a different slug
        
        expected_slug3 = expected_slug2 + '-2'
        self.add_entry(title=title, markdown=markdown, tags=tags2)
        
        entry = self.query_db('SELECT * FROM entries WHERE id=3', one=True)
        self.assertEqual(entry['slug'], expected_slug3)
        
        # Now test updating an entry
        
        updated_title = 'cool'
        updated_markdown = '## Title'
        updated_tags = ''
        expected_title = updated_title
        expected_markdown = updated_markdown
        expected_tags = []
        expected_slug = 'cool'
        expected_html = '<h2>Title</h2>'
        expected_date = datetime.date.today()
        self.update_entry(title=updated_title, markdown=updated_markdown, 
                          tags=updated_tags, id=1)

        entry = self.query_db('SELECT * FROM entries WHERE id=1', one=True)
        self.assertEqual(entry['title'], expected_title)
        self.assertEqual(entry['markdown'], expected_markdown)
        self.assertEqual(entry['slug'], expected_slug)
        assert expected_html in entry['html']
        self.assertEqual(entry['published'].date(), expected_date)
        tags = helpers.get_tags(entry_id=entry['id'], db=self.db)
        self.assertEqual(tags, expected_tags)
        
        # Expect three rows in the entries table because three entries where
        # created and one updated. Expect only two rows in the tags table 
        # because the tag 'vil/bil' is not used anymore by an entry. Also 
        # expect four entries in the entry_tag table because it should look
        # like this:
        # entry_id | tag_id
        # 2          1
        # 2          2
        # 3          1
        # 3          2
        
        entries = self.query_db('SELECT * FROM entries')
        tags = self.query_db('SELECT * FROM tags')
        entry_tag_mappings = self.query_db('SELECT * FROM entry_tag')
        self.assertEqual(len(entries), 3)
        self.assertEqual(len(tags), 2)
        self.assertEqual(len(entry_tag_mappings), 4)
        

if __name__ == '__main__':
    unittest.main()