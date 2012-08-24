# Copyright 2012 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime
import json

import webob

import glance.api.v2.images
from glance.common import utils
from glance.openstack.common import cfg
import glance.schema
from glance.tests.unit import base
import glance.tests.unit.utils as unit_test_utils
import glance.tests.utils as test_utils
import glance.store


DATETIME = datetime.datetime(2012, 5, 16, 15, 27, 36, 325355)
ISOTIME = '2012-05-16T15:27:36Z'


CONF = cfg.CONF


UUID1 = 'c80a1a6c-bd1f-41c5-90ee-81afedb1d58d'
UUID2 = 'a85abd86-55b3-4d5b-b0b4-5d0a6e6042fc'
UUID3 = '971ec09a-8067-4bc8-a91f-ae3557f1c4c7'
UUID4 = '6bbe7cc2-eae7-4c0f-b50d-a7160b0c6a86'

TENANT1 = '6838eb7b-6ded-434a-882c-b344c77fe8df'
TENANT2 = '2c014f32-55eb-467d-8fcb-4bd706012f81'
TENANT3 = '5a3e60e8-cfa9-4a9e-a90a-62b42cea92b8'
TENANT4 = 'c6c87f25-8a94-47ed-8c83-053c25f42df4'


def _fixture(id, **kwargs):
    obj = {
        'id': id,
        'name': None,
        'is_public': False,
        'properties': {},
        'checksum': None,
        'owner': None,
        'status': 'queued',
        'tags': [],
        'size': None,
        'location': None,
        'protected': False,
        'disk_format': None,
        'container_format': None,
        'deleted': False,
        'min_ram': None,
        'min_disk': None,
    }
    obj.update(kwargs)
    return obj


class TestImagesController(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesController, self).setUp()
        self.base_uri = 'swift+http://storeuri.com/container'
        self.db = unit_test_utils.FakeDB(base_uri=self.base_uri)
        self.policy = unit_test_utils.FakePolicyEnforcer()
        self.store = unit_test_utils.FakeStoreAPI(base_uri=self.base_uri)
        self._create_images()
        self.controller = glance.api.v2.images.ImagesController(self.db,
                                                                self.policy,
                                                                self.store)

    def _create_images(self):
        self.db.reset()
        self.images = [
            _fixture(UUID1, owner=TENANT1, name='1', size=256, is_public=True,
                     location='%s/%s' % (self.base_uri, UUID1)),
            _fixture(UUID2, owner=TENANT1, name='2', size=512, is_public=True),
            _fixture(UUID3, owner=TENANT3, name='3', size=512, is_public=True),
            _fixture(UUID4, owner=TENANT4, name='4', size=1024),
        ]
        [self.db.image_create(None, image) for image in self.images]

        self.db.image_tag_set_all(None, UUID1, ['ping', 'pong'])

    def test_index(self):
        self.config(limit_param_default=1, api_limit_max=3)
        request = unit_test_utils.get_fake_request()
        output = self.controller.index(request)
        self.assertEqual(1, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID3])
        self.assertEqual(actual, expected)

    def test_index_return_parameters(self):
        self.config(limit_param_default=1, api_limit_max=3)
        request = unit_test_utils.get_fake_request()
        output = self.controller.index(request, marker=UUID3, limit=1,
                                       sort_key='created_at', sort_dir='desc')
        self.assertEqual(1, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID2])
        self.assertEqual(actual, expected)
        self.assertEqual(UUID2, output['next_marker'])

    def test_index_next_marker(self):
        self.config(limit_param_default=1, api_limit_max=3)
        request = unit_test_utils.get_fake_request()
        output = self.controller.index(request, marker=UUID3, limit=2)
        self.assertEqual(2, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID2, UUID1])
        self.assertEqual(actual, expected)
        self.assertEqual(UUID1, output['next_marker'])

    def test_index_no_next_marker(self):
        self.config(limit_param_default=1, api_limit_max=3)
        request = unit_test_utils.get_fake_request()
        output = self.controller.index(request, marker=UUID1, limit=2)
        self.assertEqual(0, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([])
        self.assertEqual(actual, expected)
        self.assertTrue('next_marker' not in output)

    def test_index_with_id_filter(self):
        request = unit_test_utils.get_fake_request('/images?id=%s' % UUID1)
        output = self.controller.index(request, filters={'id': UUID1})
        self.assertEqual(1, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID1])
        self.assertEqual(actual, expected)

    def test_index_size_max_filter(self):
        request = unit_test_utils.get_fake_request('/images?size_max=512')
        output = self.controller.index(request, filters={'size_max': 512})
        self.assertEqual(3, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID1, UUID2, UUID3])
        self.assertEqual(actual, expected)

    def test_index_size_min_filter(self):
        request = unit_test_utils.get_fake_request('/images?size_min=512')
        output = self.controller.index(request, filters={'size_min': 512})
        self.assertEqual(2, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID2, UUID3])
        self.assertEqual(actual, expected)

    def test_index_size_range_filter(self):
        path = '/images?size_min=512&size_max=512'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request,
                                       filters={'size_min': 512,
                                                'size_max': 512})
        self.assertEqual(2, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID2, UUID3])
        self.assertEqual(actual, expected)

    def test_index_with_invalid_max_range_filter_value(self):
        request = unit_test_utils.get_fake_request('/images?size_max=blah')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.index,
                          request,
                          filters={'size_max': 'blah'})

    def test_index_with_filters_return_many(self):
        path = '/images?status=queued'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, filters={'status': 'queued'})
        self.assertEqual(3, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID1, UUID2, UUID3])
        self.assertEqual(actual, expected)

    def test_index_with_nonexistant_name_filter(self):
        request = unit_test_utils.get_fake_request('/images?name=%s' % 'blah')
        images = self.controller.index(request,
                                       filters={'name': 'blah'})['images']
        self.assertEqual(0, len(images))

    def test_index_with_non_default_is_public_filter(self):
        image = {
            'id': utils.generate_uuid(),
            'owner': TENANT3,
            'name': '3',
            'is_public': False
        }
        self.db.image_create(None, image)
        path = '/images?visibility=private'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, filters={'is_public': False})
        self.assertEqual(2, len(output['images']))

    def test_index_with_many_filters(self):
        url = '/images?status=queued&name=2'
        request = unit_test_utils.get_fake_request(url)
        output = self.controller.index(request,
                filters={'status': 'queued', 'name': '2'})
        self.assertEqual(1, len(output['images']))
        actual = set([image['id'] for image in output['images']])
        expected = set([UUID2])
        self.assertEqual(actual, expected)

    def test_index_with_marker(self):
        self.config(limit_param_default=1, api_limit_max=3)
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, marker=UUID3)
        actual = set([image['id'] for image in output['images']])
        self.assertEquals(1, len(actual))
        self.assertTrue(UUID2 in actual)

    def test_index_with_limit(self):
        path = '/images'
        limit = 2
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, limit=limit)
        actual = set([image['id'] for image in output['images']])
        self.assertEquals(limit, len(actual))
        self.assertTrue(UUID3 in actual)
        self.assertTrue(UUID2 in actual)

    def test_index_greater_than_limit_max(self):
        self.config(limit_param_default=1, api_limit_max=3)
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, limit=4)
        actual = set([image['id'] for image in output['images']])
        self.assertEquals(3, len(actual))
        self.assertTrue(output['next_marker'] not in output)

    def test_index_default_limit(self):
        self.config(limit_param_default=1, api_limit_max=3)
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request)
        actual = set([image['id'] for image in output['images']])
        self.assertEquals(1, len(actual))

    def test_index_with_sort_dir(self):
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, sort_dir='asc', limit=3)
        actual = [image['id'] for image in output['images']]
        self.assertEquals(3, len(actual))
        self.assertEquals(UUID1, actual[0])
        self.assertEquals(UUID2, actual[1])
        self.assertEquals(UUID3, actual[2])

    def test_index_with_sort_key(self):
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        output = self.controller.index(request, sort_key='created_at', limit=3)
        actual = [image['id'] for image in output['images']]
        self.assertEquals(3, len(actual))
        self.assertEquals(UUID3, actual[0])
        self.assertEquals(UUID2, actual[1])
        self.assertEquals(UUID1, actual[2])

    def test_index_with_marker_not_found(self):
        fake_uuid = utils.generate_uuid()
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.index, request, marker=fake_uuid)

    def test_index_invalid_sort_key(self):
        path = '/images'
        request = unit_test_utils.get_fake_request(path)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.index, request, sort_key='foo')

    def test_index_zero_images(self):
        self.db.reset()
        request = unit_test_utils.get_fake_request()
        output = self.controller.index(request)
        self.assertEqual([], output['images'])

    def test_show(self):
        request = unit_test_utils.get_fake_request()
        output = self.controller.show(request, image_id=UUID2)
        self.assertEqual(UUID2, output['id'])
        self.assertEqual('2', output['name'])

    def test_show_non_existant(self):
        request = unit_test_utils.get_fake_request()
        image_id = utils.generate_uuid()
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.show, request, image_id)

    def test_create(self):
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-1'}
        output = self.controller.create(request, image)
        self.assertEqual('image-1', output['name'])
        self.assertEqual({}, output['properties'])
        self.assertEqual([], output['tags'])
        self.assertEqual(False, output['is_public'])

    def test_create_public_image_as_admin(self):
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-1', 'is_public': True}
        output = self.controller.create(request, image)
        self.assertEqual(True, output['is_public'])

    def test_create_duplicate_tags(self):
        request = unit_test_utils.get_fake_request()
        image = {'tags': ['ping', 'ping']}
        output = self.controller.create(request, image)
        self.assertEqual(['ping'], output['tags'])

    def test_update(self):
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-2'}
        output = self.controller.update(request, UUID1, image)
        self.assertEqual(UUID1, output['id'])
        self.assertEqual('image-2', output['name'])
        self.assertNotEqual(output['created_at'], output['updated_at'])

    def test_update_non_existant(self):
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-2'}
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.update,
                          request, utils.generate_uuid(), image)

    def test_update_duplicate_tags(self):
        request = unit_test_utils.get_fake_request()
        image = {'tags': ['ping', 'ping']}
        output = self.controller.update(request, UUID1, image)
        self.assertEqual(['ping'], output['tags'])

    def test_delete(self):
        request = unit_test_utils.get_fake_request()
        for k in self.store.data:
            self.assertTrue(UUID1 in k)

        self.controller.delete(request, UUID1)
        deleted_img = self.db.image_get(request.context, UUID1,
                                        force_show_deleted=True)
        self.assertTrue(deleted_img['deleted'])
        for k in self.store.data:
            self.assertFalse(UUID1 in k)

    def test_delete_non_existant(self):
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          request, utils.generate_uuid())

    def test_index_with_invalid_marker(self):
        fake_uuid = utils.generate_uuid()
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.index, request, marker=fake_uuid)


class TestImagesControllerPolicies(base.IsolatedUnitTest):

    def setUp(self):
        super(TestImagesControllerPolicies, self).setUp()
        self.db = unit_test_utils.FakeDB()
        self.policy = unit_test_utils.FakePolicyEnforcer()
        self.controller = glance.api.v2.images.ImagesController(self.db,
                                                                self.policy)

    def test_index_unauthorized(self):
        rules = {"get_images": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.index,
                          request)

    def test_show_unauthorized(self):
        rules = {"get_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.show,
                          request, image_id=UUID2)

    def test_create_public_image_unauthorized(self):
        rules = {"publicize_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-1', 'is_public': True}
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.create,
                          request, image)

    def test_update_unauthorized(self):
        rules = {"modify_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-2'}
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.update,
                          request, UUID1, image)

    def test_update_publicize_image_unauthorized(self):
        rules = {"publicize_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-1', 'is_public': True}
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.update,
                          request, UUID1, image)

    def test_update_public_image_unauthorized(self):
        rules = {"modify_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-1', 'is_public': True}
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.update,
                          request, UUID1, image)

    def test_update_public_image_unauthorized_but_not_publicizing(self):
        rules = {"publicize_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        image = {'name': 'image-2', 'is_public': False}
        output = self.controller.update(request, UUID1, image)
        self.assertEqual(UUID1, output['id'])
        self.assertEqual('image-2', output['name'])

    def test_delete_unauthorized(self):
        rules = {"delete_image": False}
        self.policy.set_rules(rules)
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPForbidden, self.controller.delete,
                          request, UUID1)


class TestImagesDeserializer(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesDeserializer, self).setUp()
        self.deserializer = glance.api.v2.images.RequestDeserializer()

    def test_create_minimal(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({})
        output = self.deserializer.create(request)
        expected = {'image': {'properties': {}}}
        self.assertEqual(expected, output)

    def test_create_invalid_id(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'id': 'gabe'})
        self.assertRaises(webob.exc.HTTPBadRequest, self.deserializer.create,
                          request)

    def test_create_no_body(self):
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPBadRequest, self.deserializer.create,
                          request)

    def test_create_full(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({
            'id': UUID3,
            'name': 'image-1',
            'visibility': 'public',
            'tags': ['one', 'two'],
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'foo': 'bar',
            'protected': True,
        })
        output = self.deserializer.create(request)
        expected = {'image': {
            'id': UUID3,
            'name': 'image-1',
            'is_public': True,
            'tags': ['one', 'two'],
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'properties': {'foo': 'bar'},
            'protected': True,
        }}
        self.assertEqual(expected, output)

    def test_create_readonly_attributes_forbidden(self):
        bodies = [
            {'created_at': ISOTIME},
            {'updated_at': ISOTIME},
            {'status': 'saving'},
            {'direct_url': 'http://example.com'},
            {'size': 10},
            {'checksum': 'asdf'},
            {'self': 'http://example.com'},
            {'file': 'http://example.com'},
            {'schema': 'http://example.com'},
        ]

        for body in bodies:
            request = unit_test_utils.get_fake_request()
            request.body = json.dumps(body)
            self.assertRaises(webob.exc.HTTPForbidden,
                              self.deserializer.create, request)

    def test_update(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({
            'id': UUID3,
            'name': 'image-1',
            'visibility': 'public',
            'tags': ['one', 'two'],
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'foo': 'bar',
            'protected': True,
        })
        output = self.deserializer.update(request)
        expected = {'image': {
            'id': UUID3,
            'name': 'image-1',
            'is_public': True,
            'tags': ['one', 'two'],
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'properties': {'foo': 'bar'},
            'protected': True,
        }}
        self.assertEqual(expected, output)

    def test_update_no_body(self):
        request = unit_test_utils.get_fake_request()
        self.assertRaises(webob.exc.HTTPBadRequest, self.deserializer.update,
                          request)

    def test_update_readonly_attributes_forbidden(self):
        bodies = [
            {'created_at': ISOTIME},
            {'updated_at': ISOTIME},
            {'status': 'saving'},
            {'direct_url': 'http://example.com'},
            {'size': 10},
            {'checksum': 'asdf'},
            {'self': 'http://example.com'},
            {'file': 'http://example.com'},
            {'schema': 'http://example.com'},
        ]

        for body in bodies:
            request = unit_test_utils.get_fake_request()
            request.body = json.dumps(body)
            self.assertRaises(webob.exc.HTTPForbidden,
                              self.deserializer.update, request)

    def test_index(self):
        marker = utils.generate_uuid()
        path = '/images?limit=1&marker=%s' % marker
        request = unit_test_utils.get_fake_request(path)
        expected = {'limit': 1,
                    'marker': marker,
                    'sort_key': 'created_at',
                    'sort_dir': 'desc',
                    'filters': {}}
        output = self.deserializer.index(request)
        self.assertEqual(output, expected)

    def test_index_with_filter(self):
        name = 'My Little Image'
        path = '/images?name=%s' % name
        request = unit_test_utils.get_fake_request(path)
        output = self.deserializer.index(request)
        self.assertEqual(output['filters']['name'], name)

    def test_index_strip_params_from_filters(self):
        name = 'My Little Image'
        path = '/images?name=%s' % name
        request = unit_test_utils.get_fake_request(path)
        output = self.deserializer.index(request)
        self.assertEqual(output['filters']['name'], name)
        self.assertEqual(len(output['filters']), 1)

    def test_index_with_many_filter(self):
        name = 'My Little Image'
        instance_id = utils.generate_uuid()
        path = '/images?name=%(name)s&id=%(instance_id)s' % locals()
        request = unit_test_utils.get_fake_request(path)
        output = self.deserializer.index(request)
        self.assertEqual(output['filters']['name'], name)
        self.assertEqual(output['filters']['id'], instance_id)

    def test_index_with_filter_and_limit(self):
        name = 'My Little Image'
        path = '/images?name=%s&limit=1' % name
        request = unit_test_utils.get_fake_request(path)
        output = self.deserializer.index(request)
        self.assertEqual(output['filters']['name'], name)
        self.assertEqual(output['limit'], 1)

    def test_index_non_integer_limit(self):
        request = unit_test_utils.get_fake_request('/images?limit=blah')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.index, request)

    def test_index_zero_limit(self):
        request = unit_test_utils.get_fake_request('/images?limit=0')
        expected = {'limit': 0,
                    'sort_key': 'created_at',
                    'sort_dir': 'desc',
                    'filters': {}}
        output = self.deserializer.index(request)
        self.assertEqual(expected, output)

    def test_index_negative_limit(self):
        request = unit_test_utils.get_fake_request('/images?limit=-1')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.index, request)

    def test_index_fraction(self):
        request = unit_test_utils.get_fake_request('/images?limit=1.1')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.index, request)

    def test_index_marker(self):
        marker = utils.generate_uuid()
        path = '/images?marker=%s' % marker
        request = unit_test_utils.get_fake_request(path)
        output = self.deserializer.index(request)
        self.assertEqual(output.get('marker'), marker)

    def test_index_marker_not_specified(self):
        request = unit_test_utils.get_fake_request('/images')
        output = self.deserializer.index(request)
        self.assertFalse('marker' in output)

    def test_index_limit_not_specified(self):
        request = unit_test_utils.get_fake_request('/images')
        output = self.deserializer.index(request)
        self.assertFalse('limit' in output)

    def test_index_sort_key_id(self):
        request = unit_test_utils.get_fake_request('/images?sort_key=id')
        output = self.deserializer.index(request)
        expected = {
            'sort_key': 'id',
            'sort_dir': 'desc',
            'filters': {}
        }
        self.assertEqual(output, expected)

    def test_index_sort_dir_asc(self):
        request = unit_test_utils.get_fake_request('/images?sort_dir=asc')
        output = self.deserializer.index(request)
        expected = {
            'sort_key': 'created_at',
            'sort_dir': 'asc',
            'filters': {}}
        self.assertEqual(output, expected)

    def test_index_sort_dir_bad_value(self):
        request = unit_test_utils.get_fake_request('/images?sort_dir=blah')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.index, request)


class TestImagesDeserializerWithExtendedSchema(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesDeserializerWithExtendedSchema, self).setUp()
        self.config(allow_additional_image_properties=False)
        custom_image_properties = {
            'pants': {
                'type': 'string',
                'required': True,
                'enum': ['on', 'off'],
            },
        }
        schema = glance.api.v2.images.get_schema(custom_image_properties)
        self.deserializer = glance.api.v2.images.RequestDeserializer(schema)

    def test_create(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'name': 'image-1', 'pants': 'on'})
        output = self.deserializer.create(request)
        expected = {
            'image': {
                'name': 'image-1',
                'properties': {'pants': 'on'},
            },
        }
        self.assertEqual(expected, output)

    def test_create_bad_data(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'name': 'image-1', 'pants': 'borked'})
        self.assertRaises(webob.exc.HTTPBadRequest,
                self.deserializer.create, request)

    def test_update(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'name': 'image-1', 'pants': 'off'})
        output = self.deserializer.update(request)
        expected = {
            'image': {
                'name': 'image-1',
                'properties': {'pants': 'off'},
            },
        }
        self.assertEqual(expected, output)

    def test_update_bad_data(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'name': 'image-1', 'pants': 'borked'})
        self.assertRaises(webob.exc.HTTPBadRequest,
                self.deserializer.update, request)


class TestImagesDeserializerWithAdditionalProperties(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesDeserializerWithAdditionalProperties, self).setUp()
        self.config(allow_additional_image_properties=True)
        self.deserializer = glance.api.v2.images.RequestDeserializer()

    def test_create(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'foo': 'bar'})
        output = self.deserializer.create(request)
        expected = {'image': {'properties': {'foo': 'bar'}}}
        self.assertEqual(expected, output)

    def test_create_with_numeric_property(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'abc': 123})
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.create, request)

    def test_create_with_list_property(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'foo': ['bar']})
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.create, request)

    def test_update(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'foo': 'bar'})
        output = self.deserializer.update(request)
        expected = {'image': {'properties': {'foo': 'bar'}}}
        self.assertEqual(expected, output)


class TestImagesDeserializerNoAdditionalProperties(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesDeserializerNoAdditionalProperties, self).setUp()
        self.config(allow_additional_image_properties=False)
        self.deserializer = glance.api.v2.images.RequestDeserializer()

    def test_create_with_additional_properties_disallowed(self):
        self.config(allow_additional_image_properties=False)
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'foo': 'bar'})
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.create, request)

    def test_update(self):
        request = unit_test_utils.get_fake_request()
        request.body = json.dumps({'foo': 'bar'})
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.update, request)


class TestImagesSerializer(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesSerializer, self).setUp()
        self.serializer = glance.api.v2.images.ResponseSerializer()
        self.fixtures = [
            #NOTE(bcwaldon): This first fixture has every property defined
            _fixture(UUID1, name='image-1', size=1024, tags=['one', 'two'],
                    created_at=DATETIME, updated_at=DATETIME, owner=TENANT1,
                    is_public=True, container_format='ami', disk_format='ami',
                    checksum='ca425b88f047ce8ec45ee90e813ada91',
                    min_ram=128, min_disk=10),

            #NOTE(bcwaldon): This second fixture depends on default behavior
            # and sets most values to None
            _fixture(UUID2, created_at=DATETIME, updated_at=DATETIME),
        ]

    def test_index(self):
        expected = {
            'images': [
                {
                    'id': UUID1,
                    'name': 'image-1',
                    'status': 'queued',
                    'visibility': 'public',
                    'protected': False,
                    'tags': ['one', 'two'],
                    'size': 1024,
                    'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
                    'container_format': 'ami',
                    'disk_format': 'ami',
                    'min_ram': 128,
                    'min_disk': 10,
                    'created_at': ISOTIME,
                    'updated_at': ISOTIME,
                    'self': '/v2/images/%s' % UUID1,
                    'file': '/v2/images/%s/file' % UUID1,
                    'schema': '/v2/schemas/image',
                },
                {
                    'id': UUID2,
                    'status': 'queued',
                    'visibility': 'private',
                    'protected': False,
                    'tags': [],
                    'created_at': ISOTIME,
                    'updated_at': ISOTIME,
                    'self': '/v2/images/%s' % UUID2,
                    'file': '/v2/images/%s/file' % UUID2,
                    'schema': '/v2/schemas/image',
                },
            ],
            'first': '/v2/images',
            'schema': '/v2/schemas/images',
        }
        request = webob.Request.blank('/v2/images')
        response = webob.Response(request=request)
        result = {'images': self.fixtures}
        self.serializer.index(response, result)
        self.assertEqual(expected, json.loads(response.body))
        self.assertEqual('application/json', response.content_type)

    def test_index_next_marker(self):
        request = webob.Request.blank('/v2/images')
        response = webob.Response(request=request)
        result = {'images': self.fixtures, 'next_marker': UUID2}
        self.serializer.index(response, result)
        output = json.loads(response.body)
        self.assertEqual('/v2/images?marker=%s' % UUID2, output['next'])

    def test_index_carries_query_parameters(self):
        url = '/v2/images?limit=10&sort_key=id&sort_dir=asc'
        request = webob.Request.blank(url)
        response = webob.Response(request=request)
        result = {'images': self.fixtures, 'next_marker': UUID2}
        self.serializer.index(response, result)
        output = json.loads(response.body)
        self.assertEqual('/v2/images?sort_key=id&sort_dir=asc&limit=10',
                         output['first'])
        expect_next = '/v2/images?sort_key=id&sort_dir=asc&limit=10&marker=%s'
        self.assertEqual(expect_next % UUID2, output['next'])

    def test_show_full_fixture(self):
        expected = {
            'id': UUID1,
            'name': 'image-1',
            'status': 'queued',
            'visibility': 'public',
            'protected': False,
            'tags': ['one', 'two'],
            'size': 1024,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID1,
            'file': '/v2/images/%s/file' % UUID1,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.show(response, self.fixtures[0])
        self.assertEqual(expected, json.loads(response.body))
        self.assertEqual('application/json', response.content_type)

    def test_show_minimal_fixture(self):
        expected = {
            'id': UUID2,
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'tags': [],
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.show(response, self.fixtures[1])
        self.assertEqual(expected, json.loads(response.body))

    def test_create(self):
        expected = {
            'id': UUID1,
            'name': 'image-1',
            'status': 'queued',
            'visibility': 'public',
            'protected': False,
            'tags': ['one', 'two'],
            'size': 1024,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID1,
            'file': '/v2/images/%s/file' % UUID1,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.create(response, self.fixtures[0])
        self.assertEqual(response.status_int, 201)
        self.assertEqual(expected, json.loads(response.body))
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(response.location, '/v2/images/%s' % UUID1)

    def test_update(self):
        expected = {
            'id': UUID1,
            'name': 'image-1',
            'status': 'queued',
            'visibility': 'public',
            'protected': False,
            'tags': ['one', 'two'],
            'size': 1024,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'container_format': 'ami',
            'disk_format': 'ami',
            'min_ram': 128,
            'min_disk': 10,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID1,
            'file': '/v2/images/%s/file' % UUID1,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.update(response, self.fixtures[0])
        self.assertEqual(expected, json.loads(response.body))
        self.assertEqual('application/json', response.content_type)


class TestImagesSerializerWithExtendedSchema(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesSerializerWithExtendedSchema, self).setUp()
        self.config(allow_additional_image_properties=False)
        custom_image_properties = {
            'color': {
                'type': 'string',
                'required': True,
                'enum': ['red', 'green'],
            },
        }
        schema = glance.api.v2.images.get_schema(custom_image_properties)
        self.serializer = glance.api.v2.images.ResponseSerializer(schema)

        self.fixture = _fixture(UUID2, name='image-2', owner=TENANT2,
                checksum='ca425b88f047ce8ec45ee90e813ada91',
                created_at=DATETIME, updated_at=DATETIME,
                size=1024, properties={'color': 'green', 'mood': 'grouchy'})

    def test_show(self):
        expected = {
            'id': UUID2,
            'name': 'image-2',
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'tags': [],
            'size': 1024,
            'color': 'green',
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.show(response, self.fixture)
        self.assertEqual(expected, json.loads(response.body))

    def test_show_reports_invalid_data(self):
        self.fixture['properties']['color'] = 'invalid'
        expected = {
            'id': UUID2,
            'name': 'image-2',
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'tags': [],
            'size': 1024,
            'color': 'invalid',
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        self.serializer.show(response, self.fixture)
        self.assertEqual(expected, json.loads(response.body))


class TestImagesSerializerWithAdditionalProperties(test_utils.BaseTestCase):

    def setUp(self):
        super(TestImagesSerializerWithAdditionalProperties, self).setUp()
        self.config(allow_additional_image_properties=True)
        self.fixture = _fixture(UUID2, name='image-2', owner=TENANT2,
            checksum='ca425b88f047ce8ec45ee90e813ada91',
            created_at=DATETIME, updated_at=DATETIME,
            properties={'marx': 'groucho'}, size=1024)

    def test_show(self):
        serializer = glance.api.v2.images.ResponseSerializer()
        expected = {
            'id': UUID2,
            'name': 'image-2',
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'marx': 'groucho',
            'tags': [],
            'size': 1024,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        serializer.show(response, self.fixture)
        self.assertEqual(expected, json.loads(response.body))

    def test_show_invalid_additional_property(self):
        """Ensure that the serializer passes through invalid additional
        properties (i.e. non-string) without complaining.
        """
        serializer = glance.api.v2.images.ResponseSerializer()
        self.fixture['properties']['marx'] = 123
        expected = {
            'id': UUID2,
            'name': 'image-2',
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'marx': 123,
            'tags': [],
            'size': 1024,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        serializer.show(response, self.fixture)
        self.assertEqual(expected, json.loads(response.body))

    def test_show_with_additional_properties_disabled(self):
        self.config(allow_additional_image_properties=False)
        serializer = glance.api.v2.images.ResponseSerializer()
        expected = {
            'id': UUID2,
            'name': 'image-2',
            'status': 'queued',
            'visibility': 'private',
            'protected': False,
            'checksum': 'ca425b88f047ce8ec45ee90e813ada91',
            'tags': [],
            'size': 1024,
            'created_at': ISOTIME,
            'updated_at': ISOTIME,
            'self': '/v2/images/%s' % UUID2,
            'file': '/v2/images/%s/file' % UUID2,
            'schema': '/v2/schemas/image',
        }
        response = webob.Response()
        serializer.show(response, self.fixture)
        self.assertEqual(expected, json.loads(response.body))


class TestImagesSerializerDirectUrl(test_utils.BaseTestCase):
    def setUp(self):
        super(TestImagesSerializerDirectUrl, self).setUp()
        self.serializer = glance.api.v2.images.ResponseSerializer()

        self.active_image = _fixture(UUID1, name='image-1', is_public=True,
                status='active', size=1024,
                created_at=DATETIME, updated_at=DATETIME,
                location='http://some/fake/location')

        self.queued_image = _fixture(UUID2, name='image-2', status='active',
                created_at=DATETIME, updated_at=DATETIME,
                checksum='ca425b88f047ce8ec45ee90e813ada91')

    def _do_index(self):
        request = webob.Request.blank('/v2/images')
        response = webob.Response(request=request)
        self.serializer.index(response,
                {'images': [self.active_image, self.queued_image]})
        return json.loads(response.body)['images']

    def _do_show(self, image):
        request = webob.Request.blank('/v2/images')
        response = webob.Response(request=request)
        self.serializer.show(response, image)
        return json.loads(response.body)

    def test_index_store_location_enabled(self):
        self.config(show_image_direct_url=True)
        images = self._do_index()

        # NOTE(markwash): ordering sanity check
        self.assertEqual(images[0]['id'], UUID1)
        self.assertEqual(images[1]['id'], UUID2)

        self.assertEqual(images[0]['direct_url'], 'http://some/fake/location')
        self.assertFalse('direct_url' in images[1])

    def test_index_store_location_explicitly_disabled(self):
        self.config(show_image_direct_url=False)
        images = self._do_index()
        self.assertFalse('direct_url' in images[0])
        self.assertFalse('direct_url' in images[1])

    def test_show_location_enabled(self):
        self.config(show_image_direct_url=True)
        image = self._do_show(self.active_image)
        self.assertEqual(image['direct_url'], 'http://some/fake/location')

    def test_show_location_enabled_but_not_set(self):
        self.config(show_image_direct_url=True)
        image = self._do_show(self.queued_image)
        self.assertFalse('direct_url' in image)

    def test_show_location_explicitly_disabled(self):
        self.config(show_image_direct_url=False)
        image = self._do_show(self.active_image)
        self.assertFalse('direct_url' in image)
