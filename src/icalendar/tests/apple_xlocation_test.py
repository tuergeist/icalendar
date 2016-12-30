# -*- coding: utf-8 -*-
from icalendar.tests import unittest

import datetime
import icalendar
import os
import pytz

class TestEncoding(unittest.TestCase):

    def test_apple_xlocation(self):
        """
        Test if error messages are encode properly.
        """
        try:
            directory = os.path.dirname(__file__)
            data = open(os.path.join(directory, 'x_location.ics'), 'rb').read()
            cal = icalendar.Calendar.from_ical(data)
            for event in cal.walk('vevent'):
                self.assertEqual(len(event.errors), 0, 'Got too many errors')

        except UnicodeEncodeError as e:
            self.fail("There is something wrong with encoding in the collected error messages")
