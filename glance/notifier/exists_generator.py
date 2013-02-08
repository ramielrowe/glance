# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack LLC.
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
from time import sleep

import glance.context
import glance.db
import glance.notifier


def get_period_range(period, time=datetime.datetime.utcnow()):
    start = None
    end = None
    if period == 'hour':
        start = datetime.datetime(year=time.year, month=time.month,
                                  day=time.day, hour=time.hour)
        end = datetime.datetime(year=time.year, month=time.month, day=time.day,
                                hour=time.hour, minute=59, second=59,
                                microsecond=999999)
    elif period == 'day':
        start = datetime.datetime(year=time.year, month=time.month,
                                  day=time.day)
        end = datetime.datetime(year=time.year, month=time.month, day=time.day,
                                hour=23, minute=59, second=59,
                                microsecond=999999)
    elif period == 'week':
        today = datetime.datetime(year=time.year, month=time.month,
                                  day=time.day)
        # 00:00:00.000000 Last Monday
        start = today - datetime.timedelta(days=time.weekday())
        # 23:59:59.999999 Next Sunday
        end = start + datetime.timedelta(days=6, hours=23, minutes=59,
                                         seconds=59, microseconds=999999)
    elif period == 'month':
        start = datetime.datetime(year=time.year, month=time.month, day=1)
        end_month = time.month + 1
        end_year = time.year
        if end_month == 13:
            end_year = time.year + 1
            end_month = 1
        next_month_date = datetime.datetime(year=end_year, month=end_month,
                                            day=1)
        end = next_month_date - datetime.timedelta(microseconds=1)

    return start, end


class ExistsGenerator(object):
    def __init__(self, period, wait, time, notifier=None, db_api=None):
        self.wait = wait
        self.period = period
        (start, end) = get_period_range(period, time=time)
        self.period_start = start
        self.period_end = end

        self.notifier = notifier or glance.notifier.Notifier()
        self.db_api = db_api or glance.db.get_api()
        self.db_api.setup_db_env()
        self.context = glance.context.RequestContext(is_admin=True)
        self.image_repo = glance.db.ImageRepo(self.context, self.db_api)

    def _db_to_notification(self, image):
        image_dict = self.image_repo._format_image_to_db(image)
        for key in image_dict:
            if isinstance(image_dict[key], datetime.datetime):
                image_dict[key] = str(image_dict[key])
        image_dict['audit_period_begining'] = str(self.period_start)
        image_dict['audit_period_ending'] = str(self.period_end)
        return image_dict

    def _wait_until_period_end(self):
        while datetime.datetime.utcnow() < self.period_end:
            sleep(5)

    def run(self):
        if self.wait:
            self._wait_until_period_end()

        active_filters = {
            'location_not': None,
            'created_at_max': self.period_end,
            'deleted': False
        }
        active_images = self.image_repo.list(filters=active_filters)
        deleted_filters = {
            'location_not': None,
            'created_at_max': self.period_end,
            'deleted': True,
            'deleted_at_min': self.period_start
        }
        deleted_images = self.image_repo.list(filters=deleted_filters)
        all_images = []
        all_images.extend(active_images)
        all_images.extend(deleted_images)
        for image in all_images:
            image_dict = self._db_to_notification(image)
            self.notifier.info("image.exists", image_dict)
