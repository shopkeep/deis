"""
Unit tests for the Deis api app.

Run the tests with "./manage.py test api"
"""

from __future__ import unicode_literals

import json
import mock
import requests

from django.test import TransactionTestCase
from django.test.utils import override_settings

from api.models import Config


def mock_import_repository_task(*args, **kwargs):
    resp = requests.Response()
    resp.status_code = 200
    resp._content_consumed = True
    return resp


@override_settings(CELERY_ALWAYS_EAGER=True)
class ConfigTest(TransactionTestCase):

    """Tests setting and updating config values"""

    fixtures = ['tests.json']

    def setUp(self):
        self.assertTrue(
            self.client.login(username='autotest', password='password'))
        body = {'id': 'autotest', 'domain': 'autotest.local', 'type': 'mock',
                'hosts': 'host1,host2', 'auth': 'base64string', 'options': {}}
        response = self.client.post('/api/clusters', json.dumps(body),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)

    @mock.patch('requests.post', mock_import_repository_task)
    def test_config(self):
        """
        Test that config is auto-created for a new app and that
        config can be updated using a PATCH
        """
        url = '/api/apps'
        body = {'cluster': 'autotest'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        app_id = response.data['id']
        # check to see that an initial/empty config was created
        url = "/api/apps/{app_id}/config".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('values', response.data)
        self.assertEqual(response.data['values'], json.dumps({}))
        config1 = response.data
        # set an initial config value
        body = {'values': json.dumps({'NEW_URL1': 'http://localhost:8080/'})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('x-deis-release', response._headers)
        config2 = response.data
        self.assertNotEqual(config1['uuid'], config2['uuid'])
        self.assertIn('NEW_URL1', json.loads(response.data['values']))
        # read the config
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        config3 = response.data
        self.assertEqual(config2, config3)
        self.assertIn('NEW_URL1', json.loads(response.data['values']))
        # set an additional config value
        body = {'values': json.dumps({'NEW_URL2': 'http://localhost:8080/'})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        config3 = response.data
        self.assertNotEqual(config2['uuid'], config3['uuid'])
        self.assertIn('NEW_URL1', json.loads(response.data['values']))
        self.assertIn('NEW_URL2', json.loads(response.data['values']))
        # read the config again
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        config4 = response.data
        self.assertEqual(config3, config4)
        self.assertIn('NEW_URL1', json.loads(response.data['values']))
        self.assertIn('NEW_URL2', json.loads(response.data['values']))
        # unset a config value
        body = {'values': json.dumps({'NEW_URL2': None})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        config5 = response.data
        self.assertNotEqual(config4['uuid'], config5['uuid'])
        self.assertNotIn('NEW_URL2', json.dumps(response.data['values']))
        # unset all config values
        body = {'values': json.dumps({'NEW_URL1': None})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('NEW_URL1', json.dumps(response.data['values']))
        # disallow put/patch/delete
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(self.client.patch(url).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        return config5

    @mock.patch('requests.post', mock_import_repository_task)
    def test_config_set_same_key(self):
        """
        Test that config sets on the same key function properly
        """
        url = '/api/apps'
        body = {'cluster': 'autotest'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        app_id = response.data['id']
        url = "/api/apps/{app_id}/config".format(**locals())
        # set an initial config value
        body = {'values': json.dumps({'PORT': '5000'})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('PORT', json.loads(response.data['values']))
        # reset same config value
        body = {'values': json.dumps({'PORT': '5001'})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('PORT', json.loads(response.data['values']))
        self.assertEqual(json.loads(response.data['values'])['PORT'], '5001')

    @mock.patch('requests.post', mock_import_repository_task)
    def test_config_str(self):
        """Test the text representation of a node."""
        config5 = self.test_config()
        config = Config.objects.get(uuid=config5['uuid'])
        self.assertEqual(str(config), "{}-{}".format(config5['app'], config5['uuid'][:7]))
