# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack, LLC
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

from glance.notifier import exists_generator
from glance.tests import utils as test_utils


class TestExistsGenerator(test_utils.BaseTestCase):
    """Test routines in glance.notifier.exists_generator"""

    def test_get_period_range_hour(self):
        time = datetime.datetime(year=2013, month=2, day=13, hour=5, minute=30)

        (start, end) = exists_generator.get_period_range('hour', time=time)

        expected_start = datetime.datetime(year=2013, month=2, day=13, hour=5)
        expected_end = datetime.datetime(year=2013, month=2, day=13, hour=5,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)

    def test_get_period_range_day(self):
        time = datetime.datetime(year=2013, month=2, day=13, hour=5, minute=30)

        (start, end) = exists_generator.get_period_range('day', time=time)

        expected_start = datetime.datetime(year=2013, month=2, day=13)
        expected_end = datetime.datetime(year=2013, month=2, day=13, hour=23,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)

    def test_get_period_range_week(self):
        time = datetime.datetime(year=2013, month=2, day=13, hour=5, minute=30)

        (start, end) = exists_generator.get_period_range('week', time=time)

        expected_start = datetime.datetime(year=2013, month=2, day=11)
        expected_end = datetime.datetime(year=2013, month=2, day=17, hour=23,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)

    def test_get_period_range_week_end_of_month(self):
        time = datetime.datetime(year=2013, month=2, day=27, hour=5, minute=30)

        (start, end) = exists_generator.get_period_range('week', time=time)

        expected_start = datetime.datetime(year=2013, month=2, day=25)
        expected_end = datetime.datetime(year=2013, month=3, day=3, hour=23,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)

    def test_get_period_range_month(self):
        time = datetime.datetime(year=2013, month=2, day=13, hour=5, minute=30)

        (start, end) = exists_generator.get_period_range('month', time=time)

        expected_start = datetime.datetime(year=2013, month=2, day=1)
        expected_end = datetime.datetime(year=2013, month=2, day=28, hour=23,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)

    def test_get_period_range_month_end_of_year(self):
        time = datetime.datetime(year=2013, month=12, day=13, hour=5,
                                 minute=30)

        (start, end) = exists_generator.get_period_range('month', time=time)

        expected_start = datetime.datetime(year=2013, month=12, day=1)
        expected_end = datetime.datetime(year=2013, month=12, day=31, hour=23,
                                         minute=59, second=59,
                                         microsecond=999999)
        self.assertEquals(expected_start, start)
        self.assertEquals(expected_end, end)
