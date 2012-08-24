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

from glance.common import exception
from glance.common import wsgi
import glance.context
import glance.db.simple.api as simple_db
import glance.openstack.common.log as logging


LOG = logging.getLogger(__name__)

UUID1 = 'c80a1a6c-bd1f-41c5-90ee-81afedb1d58d'
UUID2 = '971ec09a-8067-4bc8-a91f-ae3557f1c4c7'

TENANT1 = '6838eb7b-6ded-434a-882c-b344c77fe8df'
TENANT2 = '2c014f32-55eb-467d-8fcb-4bd706012f81'

USER1 = '54492ba0-f4df-4e4e-be62-27f4d76b29cf'
USER2 = '0b3b3006-cb76-4517-ae32-51397e22c754'


def get_fake_request(path='', method='POST', is_admin=False):
    req = wsgi.Request.blank(path)
    req.method = method

    kwargs = {
            'user': USER1,
            'tenant': TENANT1,
            'roles': [],
            'is_admin': is_admin,
        }

    req.context = glance.context.RequestContext(**kwargs)

    return req


class FakeDB(object):

    def __init__(self, base_uri=None):
        self.base_uri = base_uri or 'swift+http://storeuri.com/container'
        self.reset()
        self.init_db(self.base_uri)

    @staticmethod
    def init_db(base_uri=None):
        images = [
            {'id': UUID1, 'owner': TENANT1,
             'location': '%s/%s' % (base_uri, UUID1)},
            {'id': UUID2, 'owner': TENANT1},
        ]
        [simple_db.image_create(None, image) for image in images]

        members = [
            {'image_id': UUID1, 'member': TENANT1, 'can_share': True},
            {'image_id': UUID1, 'member': TENANT2, 'can_share': False},
        ]
        [simple_db.image_member_create(None, member) for member in members]

        simple_db.image_tag_set_all(None, UUID1, ['ping', 'pong'])

    @staticmethod
    def reset():
        simple_db.DATA = {
            'images': {},
            'members': [],
            'tags': {},
        }

    def __getattr__(self, key):
        return getattr(simple_db, key)


class FakeStoreAPI(object):

    def __init__(self, base_uri=None):
        self.base_uri = base_uri or 'swift+http://storeuri.com/container'
        self.data = {
            '%s/%s' % (self.base_uri, UUID1): ('XXX', 3),
        }

    def create_stores(self):
        pass

    def get_from_backend(self, context, location):
        try:
            return self.data[location]
        except KeyError:
            raise exception.NotFound()

    def get_size_from_backend(self, context, location):
        return self.get_from_backend(context, location)[1]

    def add_to_backend(self, context, scheme, image_id, data, size):
        for location in self.data.keys():
            if image_id in location:
                raise exception.Duplicate()
        self.data[image_id] = (data, size or len(data))
        checksum = 'Z'
        return (image_id, size, checksum)

    def delete_from_backend(self, context, uri, **kwargs):
        del self.data[uri]

    def schedule_delete_from_backend(self, uri, context, image_id, **kwargs):
        self.delete_from_backend(context, uri)

    def set_acls(*_args, **_kwargs):
        pass


class FakePolicyEnforcer(object):
    def __init__(self, *_args, **kwargs):
        self.rules = {}

    def enforce(self, _ctxt, action, target=None, **kwargs):
        """Raise Forbidden if a rule for given action is set to false."""
        if self.rules.get(action) is False:
            raise exception.Forbidden()

    def set_rules(self, rules):
        self.rules = rules
