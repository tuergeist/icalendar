# -*- coding: utf-8 -*-
"""This module contains the parser/generators (or coders/encoders if you
prefer) for the classes/datatypes that are used in iCalendar:

###########################################################################
# This module defines these property value data types and property parameters

4.2 Defined property parameters are:

     ALTREP, CN, CUTYPE, DELEGATED-FROM, DELEGATED-TO, DIR, ENCODING, FMTTYPE,
     FBTYPE, LANGUAGE, MEMBER, PARTSTAT, RANGE, RELATED, RELTYPE, ROLE, RSVP,
     SENT-BY, TZID, VALUE

4.3 Defined value data types are:

    BINARY, BOOLEAN, CAL-ADDRESS, DATE, DATE-TIME, DURATION, FLOAT, INTEGER,
    PERIOD, RECUR, TEXT, TIME, URI, UTC-OFFSET

###########################################################################

iCalendar properties has values. The values are strongly typed. This module
defines these types, calling val.to_ical() on them, Will render them as defined
in rfc2445.

If you pass any of these classes a Python primitive, you will have an object
that can render itself as iCalendar formatted date.

Property Value Data Types starts with a 'v'. they all have an to_ical() and
from_ical() method. The to_ical() method generates a text string in the
iCalendar format. The from_ical() method can parse this format and return a
primitive Python datatype. So it should allways be true that:

    x == vDataType.from_ical(VDataType(x).to_ical())

These types are mainly used for parsing and file generation. But you can set
them directly.
"""
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo
from icalendar.caselessdict import CaselessDict
from icalendar.parser import Parameters
from icalendar.parser import escape_char
from icalendar.parser import tzid_from_dt
from icalendar.parser import unescape_char
from icalendar.parser_tools import DEFAULT_ENCODING
from icalendar.parser_tools import SEQUENCE_TYPES
from icalendar.parser_tools import to_unicode

import base64
import binascii
import pytz
import re
import time as _time


DATE_PART = r'(\d+)D'
TIME_PART = r'T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
DATETIME_PART = '(?:%s)?(?:%s)?' % (DATE_PART, TIME_PART)
WEEKS_PART = r'(\d+)W'
DURATION_REGEX = re.compile(r'([-+]?)P(?:%s|%s)$'
                            % (WEEKS_PART, DATETIME_PART))
WEEKDAY_RULE = re.compile('(?P<signal>[+-]?)(?P<relative>[\d]?)'
                          '(?P<weekday>[\w]{2})$')


####################################################
# handy tzinfo classes you can use.
#

ZERO = timedelta(0)
HOUR = timedelta(hours=1)
STDOFFSET = timedelta(seconds=-_time.timezone)
if _time.daylight:
    DSTOFFSET = timedelta(seconds=-_time.altzone)
else:
    DSTOFFSET = STDOFFSET
DSTDIFF = DSTOFFSET - STDOFFSET


class FixedOffset(tzinfo):
    """Fixed offset in minutes east from UTC.
    """
    def __init__(self, offset, name):
        self.__offset = timedelta(minutes=offset)
        self.__name = name

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return ZERO


class LocalTimezone(tzinfo):
    """Timezone of the machine where the code is running.
    """
    def utcoffset(self, dt):
        if self._isdst(dt):
            return DSTOFFSET
        else:
            return STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return DSTDIFF
        else:
            return ZERO

    def tzname(self, dt):
        return _time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, -1)
        stamp = _time.mktime(tt)
        tt = _time.localtime(stamp)
        return tt.tm_isdst > 0


class PropertyValue(object):
    """Abstract base class for icalendar property values.
    """
    value = None  # Native Python value of icalendar property value
    params = Parameters()

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, self.to_ical())

    def decoded(self):
        """Return decoded Python value of the PropertyValue.
        """
        value = self.value
        if isinstance(value, list):
            return [it.decoded() for it in value]
        return self.value

    def _to_ical(self):
        """Produce an RFC5545 compatible ical string of the property value.

        :returns: Property value as icalendar/RFC5545 unicode string.
        """
        raise NotImplementedError(u"to_ical must be implemented by "
                                  u"subclasses of Property.")

    def to_ical(self):
        """Produce an RFC5545 compatible ical string of the property value,
        encoded to utf-8, as expected by RFC5545.

        :returns: Property value as icalendar/RFC5545 encoded string, by
                  default encoded to utf-8.
        """
        return self._to_ical().encode(DEFAULT_ENCODING)

    @staticmethod
    def from_ical(ical):
        """Create a PropertyValue from an icalendar/RFC5545 property value
        string.

        :param ical: icalendar/RFC5545 compatible representation of a property
                     value.
        :type ical: String
        :returns: A subclass of PropertyValue.
        """
        raise NotImplementedError(u"from_ical must be implemented by "
                                  u"subclasses of Property.")


class vBinary(PropertyValue):
    """3.3.1. Binary: This value type is used to identify properties that
    contain a character encoding of inline binary data.

    Binary property values are base64 encoded.
    """

    def __init__(self, value):
        self.value = value
        self.params = Parameters(encoding='BASE64', value="BINARY")

    def _to_ical(self):
        return binascii.b2a_base64(self.value.encode('utf-8'))[:-1]

    def to_ical(self):
        return self._to_ical()

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(base64.b64decode(ical))
        except UnicodeError:
            raise ValueError('Not valid base 64 encoding.')


class vBoolean(PropertyValue):
    """3.3.2. Boolean: This value type is used to identify properties that
    contain either a "TRUE" or "FALSE" Boolean value.
    """
    BOOL_MAP = CaselessDict(true=True, false=False)

    def __init__(self, value):
        self.value = bool(value)

    def _to_ical(self):
        if self.value:
            return u'TRUE'
        return u'FALSE'

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(cls.BOOL_MAP[ical])
        except:
            raise ValueError("Expected 'TRUE' or 'FALSE'. Got %s" % ical)


class vCalAddress(PropertyValue):
    """3.3.3. Calendar User Address: This value type is used to identify
    properties that contain a calendar user address.

    This just returns an unquoted string.
    """

    def __init__(self, value):
        value = to_unicode(value)
        if not u'mailto:' in value.lower()\
                and re.match(r"[^@]+@[^@]+\.[^@]+", value):
            # Very basic mail address check.
            # Mail addresses must be mailto URIs
            value = u'mailto:{0}'.format(value)
        self.value = to_unicode(value)

    def _to_ical(self):
        return self.value

    @classmethod
    def from_ical(cls, ical):
        return cls(ical)


class vFloat(PropertyValue):
    """3.3.7. Float: This value type is used to identify properties that
    contain a real-number value.
    """

    def __init__(self, value):
        self.value = float(value)

    def _to_ical(self):
        return to_unicode(self.value, typecast=True)

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical)
        except:
            raise ValueError('Expected float value, got: %s' % ical)


class vInt(PropertyValue):
    """3.3.8. Integer: This value type is used to identify properties that
    contain a signed integer value.
    """

    def __init__(self, value):
        self.value = int(value)

    def _to_ical(self):
        return to_unicode(self.value, typecast=True)

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical)
        except:
            raise ValueError('Expected int, got: %s' % ical)


class vDDDLists(PropertyValue):
    """A list of vDate, vDatetime, vDuration or vTime values.
    """
    def __init__(self, value):
        if not hasattr(value, '__iter__'):
            value = [value]
        vDDD = []
        tzid = None
        for dt in value:
            dt = vDDDTypesFactory(dt)
            vDDD.append(dt)
            if 'TZID' in dt.params:
                tzid = dt.params['TZID']

        if tzid:
            # NOTE: All DATE-TIME values must have same timezone!
            self.params = Parameters({'TZID': tzid})
        self.value = vDDD

    def _to_ical(self):
        return u",".join([dt._to_ical() for dt in self.value])

    @classmethod
    def from_ical(cls, ical, timezone=None):
        ret = []
        ical_dates = ical.split(",")
        for ical_dt in ical_dates:
            val = vDDDTypesFactory.from_ical(ical_dt, timezone=timezone).value
            ret.append(val)
        return cls(ret)


class vDDDTypesFactory(object):
    """Factory for vDate, vDatetime or vDuration objects.
    """

    def __new__(cls, value):
        if not isinstance(value, (datetime, date, timedelta, time)):
            raise ValueError('You must use datetime, date, timedelta or time')
        if isinstance(value, datetime):
            # datetime check first, as datetime is instance of date
            return vDatetime(value)
        elif isinstance(value, date):
            return vDate(value)
        elif isinstance(value, time):
            return vTime(value)
        elif isinstance(value, timedelta):
            return vDuration(value)

    @classmethod
    def from_ical(cls, ical, timezone=None):
        u = ical.upper()
        if u.startswith('-P') or u.startswith('P'):
            return vDuration.from_ical(ical)
        try:
            return vDatetime.from_ical(ical, timezone=timezone)
        except ValueError:
            try:
                return vDate.from_ical(ical)
            except ValueError:
                return vTime.from_ical(ical)


class vDate(PropertyValue):
    """3.3.4. Date: This value type is used to identify values that contain a
    calendar date.
    """

    def __init__(self, value):
        if not isinstance(value, date):
            raise ValueError('Value MUST be a date instance')
        self.value = value
        self.params = Parameters({'value': 'DATE'})

    def _to_ical(self):
        value = self.value
        ret = u"%04d%02d%02d" % (value.year, value.month, value.day)
        return to_unicode(ret)

    @classmethod
    def from_ical(cls, ical):
        try:
            timetuple = (
                int(ical[:4]),  # year
                int(ical[4:6]),  # month
                int(ical[6:8]),  # day
            )
            return cls(date(*timetuple))
        except:
            raise ValueError('Wrong date format %s' % ical)


def _set_tzid_param(params, value):
    tzid = tzid_from_dt(value)
    if tzid and tzid.lower() != 'utc':
        params['TZID'] = tzid

class vDatetime(PropertyValue):
    """3.3.5. Date-Time: This value type is used to identify values that
    specify a precise calendar date and time of day.

    vDatetime is timezone aware and uses the pytz library, an implementation of
    the Olson database in Python. When a vDatetime object is created from an
    ical string, you can pass a valid pytz timezone identifier. When a
    vDatetime object is created from a python datetime object, it uses the
    tzinfo component, if present. Otherwise an timezone-naive object is
    created. Be aware that there are certain limitations with timezone naive
    DATE-TIME components in the icalendar standard.
    """

    def __init__(self, value):
        if not isinstance(value, datetime):
            raise ValueError('Value MUST be a datetime instance')
        self.params = Parameters({'value': 'DATE-TIME'})
        _set_tzid_param(self.params, value)
        self.value = value

    def _to_ical(self):
        value = self.value
        tzid = tzid_from_dt(value)

        ret = u"%04d%02d%02dT%02d%02d%02d%s" % (
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            tzid and tzid.lower() == 'utc' and 'Z' or ''
        )
        return to_unicode(ret)

    @classmethod
    def from_ical(cls, ical, timezone=None):
        dt = None
        tzinfo = None

        if timezone:
            try:
                tzinfo = pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                pass

        try:
            timetuple = (
                int(ical[:4]),  # year
                int(ical[4:6]),  # month
                int(ical[6:8]),  # day
                int(ical[9:11]),  # hour
                int(ical[11:13]),  # minute
                int(ical[13:15]),  # second
            )
            if tzinfo:
                dt = tzinfo.localize(datetime(*timetuple))
            elif not ical[15:]:
                dt = datetime(*timetuple)
            elif ical[15:16] == 'Z':
                dt = datetime(tzinfo=pytz.utc, *timetuple)
            else:
                raise ValueError(ical)
        except:
            raise ValueError('Wrong datetime format: %s' % ical)

        return cls(dt)


class vDuration(PropertyValue):
    """3.3.6. Duration: This value type is used to identify properties that
    contain a duration of time.
    """

    def __init__(self, value):
        if not isinstance(value, timedelta):
            raise ValueError('Value MUST be a timedelta instance')
        self.value = value

    def _to_ical(self):
        value = self.value
        sign = ""
        if value.days < 0:
            sign = "-"
            value = -value
        timepart = ""
        if value.seconds:
            timepart = "T"
            hours = value.seconds // 3600
            minutes = value.seconds % 3600 // 60
            seconds = value.seconds % 60
            if hours:
                timepart += "%dH" % hours
            if minutes or (hours and seconds):
                timepart += "%dM" % minutes
            if seconds:
                timepart += "%dS" % seconds
        if value.days == 0 and timepart:
            ret = "%sP%s" % (sign, timepart)
        else:
            ret = "%sP%sD%s" % (sign, abs(value.days), timepart)
        return to_unicode(ret)

    @classmethod
    def from_ical(cls, ical):
        try:
            match = DURATION_REGEX.match(ical)
            sign, weeks, days, hours, minutes, seconds = match.groups()
            if weeks:
                value = timedelta(weeks=int(weeks))
            else:
                value = timedelta(days=int(days or 0),
                                  hours=int(hours or 0),
                                  minutes=int(minutes or 0),
                                  seconds=int(seconds or 0))
            if sign == '-':
                value = -value
        except:
            raise ValueError('Invalid iCalendar duration: %s' % ical)
        return cls(value)


class vTime(PropertyValue):
    """3.3.12. Time: This value type is used to identify values that contain a
    time of day.
    """

    def __init__(self, value):
        if not isinstance(value, time):
            raise ValueError('Value MUST be a time instance')
        self.params = Parameters({'value': 'TIME'})
        _set_tzid_param(self.params, value)
        self.value = value

    def _to_ical(self):
        value = self.value
        tzid = tzid_from_dt(value)

        ret = u"%02d%02d%02d%s" % (
            value.hour,
            value.minute,
            value.second,
            tzid and tzid.lower() == 'utc' and 'Z' or ''
        )
        return to_unicode(ret)

    @classmethod
    def from_ical(cls, ical, timezone=None):
        dt = None
        tzinfo = None

        if timezone:
            try:
                tzinfo = pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                pass

        try:
            timetuple = (
                int(ical[:2]),  # hour
                int(ical[2:4]),  # minute
                int(ical[4:6])  # second
            )
            if tzinfo:
                dt = tzinfo.localize(time(*timetuple))
            elif not ical[6:]:
                dt = time(*timetuple)
            elif ical[6:7] == 'Z':
                dt = time(tzinfo=pytz.utc, *timetuple)
            else:
                raise ValueError(ical)
        except:
            raise ValueError('Expected time, got: %s' % ical)

        return cls(dt)


class vPeriod(PropertyValue):
    """3.3.9. Period of Time: This value type is used to identify values that
    contain a precise period of time.
    """

    def __init__(self, value):
        if not isinstance(value, tuple):
            raise ValueError('Value MUST be a tuple instance')

        start, end_or_duration = value

        if not isinstance(start, (datetime, date)):
            raise ValueError('Start value MUST be a datetime or date instance')
        if not isinstance(end_or_duration, (datetime, date, timedelta)):
            raise ValueError('end_or_duration MUST be a datetime, '
                             'date or timedelta instance')
        by_duration = 0
        if isinstance(end_or_duration, timedelta):
            by_duration = 1
            duration = end_or_duration
            end = start + duration
        else:
            end = end_or_duration
            duration = end - start
        if start > end:
            raise ValueError("Start time is greater than end time")

        # set the timezone identifier
        # does not support different timezones for start and end
        _set_tzid_param(self.params, start)

        self.start = start
        self.end = end
        self.by_duration = by_duration
        self.duration = duration

    @property
    def value(self):
        if self.by_duration:
            return (self.start, self.duration)
        return (self.start, self.end)

    def __cmp__(self, other):
        if not isinstance(other, vPeriod):
            import pdb; pdb.set_trace()
            raise NotImplementedError('Cannot compare vPeriod with %r' % other)
        return cmp((self.start, self.end), (other.start, other.end))

    def overlaps(self, other):
        if self.start > other.start:
            return other.overlaps(self)
        if self.start <= other.start < self.end:
            return True
        return False

    def _to_ical(self):
        if self.by_duration:
            ret = u"%s/%s" % (vDatetime(self.start)._to_ical(),
                              vDuration(self.duration)._to_ical())
        else:
            ret = u"%s/%s" % (vDatetime(self.start)._to_ical(),
                              vDatetime(self.end)._to_ical())
        return to_unicode(ret)

    @classmethod
    def from_ical(cls, ical):
        try:
            start, end_or_duration = ical.split('/')
            # Get Python values by letting vDDDTypesFactory instance do the
            # parsing
            start = vDDDTypesFactory.from_ical(start).value
            end_or_duration = vDDDTypesFactory.from_ical(end_or_duration).value
            return cls((start, end_or_duration))
        except:
            raise ValueError('Expected period format, got: %s' % ical)


class vWeekday(PropertyValue):
    """This returns an unquoted weekday abbrevation.
    """
    week_days = CaselessDict({
        "SU": 0, "MO": 1, "TU": 2, "WE": 3, "TH": 4, "FR": 5, "SA": 6,
    })

    def __init__(self, value):
        value = to_unicode(value)
        match = WEEKDAY_RULE.match(value)
        if match is None:
            raise ValueError('Expected weekday abbrevation, got: %s' % value)
        match = match.groupdict()
        sign = match['signal']
        weekday = match['weekday']
        relative = match['relative']
        if not weekday in vWeekday.week_days or sign not in '+-':
            raise ValueError('Expected weekday abbrevation, got: %s' % value)
        self.relative = relative and int(relative) or None
        self.value = value

    def _to_ical(self):
        return self.value.upper()

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical.upper())
        except:
            raise ValueError('Expected weekday abbrevation, got: %s' % ical)


class vFrequency(PropertyValue):
    """A simple class that catches illegal values.
    """

    frequencies = CaselessDict({
        "SECONDLY": "SECONDLY",
        "MINUTELY": "MINUTELY",
        "HOURLY": "HOURLY",
        "DAILY": "DAILY",
        "WEEKLY": "WEEKLY",
        "MONTHLY": "MONTHLY",
        "YEARLY": "YEARLY",
    })

    def __init__(self, value):
        value = to_unicode(value)
        if not value in self.frequencies:
            raise ValueError('Expected frequency, got: %s' % value)
        self.value = value

    def _to_ical(self):
        return self.value.upper()  # TODO: upper necessary?

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical.upper())
        except:
            raise ValueError('Expected frequency, got: %s' % ical)


class vRecur(CaselessDict):
    """3.3.10. Recurrence Rule
    Value Name:  RECUR
    Purpose:  This value type is used to identify properties that contain
              a recurrence rule specification.
    """

    frequencies = ["SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY",
                   "MONTHLY", "YEARLY"]

    # Mac iCal ignores RRULEs where FREQ is not the first rule part.
    # Sorts parts according to the order listed in RFC 5545, section 3.3.10.
    canonical_order = ("FREQ", "UNTIL", "COUNT", "INTERVAL",
                       "BYSECOND", "BYMINUTE", "BYHOUR", "BYDAY",
                       "BYMONTHDAY", "BYYEARDAY", "BYWEEKNO", "BYMONTH",
                       "BYSETPOS", "WKST")

    types = CaselessDict({
        'COUNT': vInt,
        'INTERVAL': vInt,
        'BYSECOND': vInt,
        'BYMINUTE': vInt,
        'BYHOUR': vInt,
        'BYMONTHDAY': vInt,
        'BYYEARDAY': vInt,
        'BYMONTH': vInt,
        'UNTIL': vDDDTypesFactory,
        'BYSETPOS': vInt,
        'WKST': vWeekday,
        'BYDAY': vWeekday,
        'FREQ': vFrequency,
    })

    params = Parameters()

    @property
    def value(self):
        # Fulfill PropertyValue API
        return self

    def _to_ical(self):
        result = []
        for key, vals in self.sorted_items():
            typ = self.types[key]
            if not isinstance(vals, SEQUENCE_TYPES):
                vals = [vals]
            vals = u','.join(typ(val)._to_ical() for val in vals)

            # CaselessDict keys are always unicode
            key = to_unicode(key)
            result.append(key + u'=' + vals)

        return u';'.join(result)

    def to_ical(self):
        return self._to_ical().encode(DEFAULT_ENCODING)

    @classmethod
    def parse_type(cls, key, values):
        # integers
        parser = cls.types.get(key, vText)
        return [parser.from_ical(v).value for v in values.split(',')]

    @classmethod
    def from_ical(cls, ical):
        try:
            recur = cls()
            for pairs in ical.split(';'):
                key, vals = pairs.split('=')
                recur[key] = cls.parse_type(key, vals)
            return cls(recur)
        except:
            raise ValueError('Error in recurrence rule: %s' % ical)


class vText(PropertyValue):
    """3.3.11. Text: This value type is used to identify values that contain
    human-readable text.
    """

    def __init__(self, value):
        self.value = to_unicode(value)

    def _to_ical(self):
        return escape_char(self.value)

    @classmethod
    def from_ical(cls, ical):
        return cls(unescape_char(ical))


class vUri(PropertyValue):
    """3.3.13. URI: This value type is used to identify values that contain a
    uniform resource identifier (URI) type of reference to the property value.
    """

    def __init__(self, value):
        self.value = to_unicode(value)

    def _to_ical(self):
        return self.value

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical)
        except:
            raise ValueError('Expected , got: %s' % ical)


class vUTCOffset(PropertyValue):
    """3.3.14. UTC Offset: This value type is used to identify properties that
    contain an offset from UTC to local time.
    """

    def __init__(self, value):
        if not isinstance(value, timedelta):
            raise ValueError('Offset value MUST be a timedelta instance')
        self.value = value

    def _to_ical(self):
        value = self.value
        if value < timedelta(0):
            sign = u'-%s'
            td = timedelta(0) - value  # get timedelta relative to 0
        else:
            # Google Calendar rejects '0000' but accepts '+0000'
            sign = u'+%s'
            td = value

        days, seconds = td.days, td.seconds

        hours = abs(days * 24 + seconds // 3600)
        minutes = abs((seconds % 3600) // 60)
        seconds = abs(seconds % 60)
        if seconds:
            duration = '%02i%02i%02i' % (hours, minutes, seconds)
        else:
            duration = '%02i%02i' % (hours, minutes)
        return sign % duration

    @classmethod
    def from_ical(cls, ical):
        try:
            sign, hours, minutes, seconds = (ical[0:1],
                                             int(ical[1:3]),
                                             int(ical[3:5]),
                                             int(ical[5:7] or 0))
            offset = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        except:
            raise ValueError('Expected utc offset, got: %s' % ical)
        if offset >= timedelta(hours=24):
            raise ValueError(
                'Offset must be less than 24 hours, was %s' % ical)
        if sign == '-':
            offset = -offset
        return cls(offset)


# HELPERS

class vGeo(PropertyValue):
    """A special type that is only indirectly defined in the RFC.
    """

    def __init__(self, value):
        if not isinstance(value, (tuple, list)):
            raise ValueError('Value MUST be a tuple or list instance')

        try:
            latitude, longitude = value
            latitude = float(latitude)
            longitude = float(longitude)
        except:
            raise ValueError('Input must be (float, float) for '
                             'latitude and longitude')
        self.value = (latitude, longitude)

    def _to_ical(self):
        value = self.value
        return u'%s;%s' % (value[0], value[1])

    @classmethod
    def from_ical(cls, ical):
        try:
            latitude, longitude = ical.split(';')
            return cls((float(latitude), float(longitude)))
        except:
            raise ValueError("Expected 'float;float' , got: %s" % ical)


class vInline(PropertyValue):
    """This is an especially dumb class that just holds raw unparsed text and
    has parameters. Conversion of inline values are handled by the Component
    class, so no further processing is needed.
    """

    def __init__(self, value):
        self.value = to_unicode(value)

    def _to_ical(self):
        return self.value

    @classmethod
    def from_ical(cls, ical):
        return cls(ical)


# FACTORIES

class TypesFactory(CaselessDict):
    """All Value types defined in rfc 2445 are registered in this factory
    class.

    The value and parameter names don't overlap. So one factory is enough for
    both kinds.
    """

    def __init__(self, *args, **kwargs):
        "Set keys to upper for initial dict"
        CaselessDict.__init__(self, *args, **kwargs)
        self.all_types = (
            vBinary,
            vBoolean,
            vCalAddress,
            vDDDLists,
            vDDDTypesFactory,
            vDate,
            vDatetime,
            vDuration,
            vFloat,
            vFrequency,
            vGeo,
            vInline,
            vInt,
            vPeriod,
            vRecur,
            vText,
            vTime,
            vUTCOffset,
            vUri,
            vWeekday
        )
        self['binary'] = vBinary
        self['boolean'] = vBoolean
        self['cal-address'] = vCalAddress
        self['date'] = vDDDTypesFactory
        self['date-time'] = vDDDTypesFactory
        self['duration'] = vDDDTypesFactory
        self['float'] = vFloat
        self['integer'] = vInt
        self['period'] = vPeriod
        self['recur'] = vRecur
        self['text'] = vText
        self['time'] = vDDDTypesFactory
        self['uri'] = vUri
        self['utc-offset'] = vUTCOffset
        self['geo'] = vGeo
        self['inline'] = vInline
        self['date-time-list'] = vDDDLists

    #################################################
    # Property types

    # These are the default types
    types_map = CaselessDict({
        ####################################
        # Property value types
        # Calendar Properties
        'calscale': 'text',
        'method': 'text',
        'prodid': 'text',
        'version': 'text',
        # Descriptive Component Properties
        'attach': 'uri',
        'categories': 'text',
        'class': 'text',
        'comment': 'text',
        'description': 'text',
        'geo': 'geo',
        'location': 'text',
        'percent-complete': 'integer',
        'priority': 'integer',
        'resources': 'text',
        'status': 'text',
        'summary': 'text',
        # Date and Time Component Properties
        'completed': 'date-time',
        'dtend': 'date-time',
        'due': 'date-time',
        'dtstart': 'date-time',
        'duration': 'duration',
        'freebusy': 'period',
        'transp': 'text',
        # Time Zone Component Properties
        'tzid': 'text',
        'tzname': 'text',
        'tzoffsetfrom': 'utc-offset',
        'tzoffsetto': 'utc-offset',
        'tzurl': 'uri',
        # Relationship Component Properties
        'attendee': 'cal-address',
        'contact': 'text',
        'organizer': 'cal-address',
        'recurrence-id': 'date-time',
        'related-to': 'text',
        'url': 'uri',
        'uid': 'text',
        # Recurrence Component Properties
        'exdate': 'date-time-list',
        'exrule': 'recur',
        'rdate': 'date-time-list',
        'rrule': 'recur',
        # Alarm Component Properties
        'action': 'text',
        'repeat': 'integer',
        'trigger': 'duration',
        # Change Management Component Properties
        'created': 'date-time',
        'dtstamp': 'date-time',
        'last-modified': 'date-time',
        'sequence': 'integer',
        # Miscellaneous Component Properties
        'request-status': 'text',
        ####################################
        # parameter types (luckily there is no name overlap)
        'altrep': 'uri',
        'cn': 'text',
        'cutype': 'text',
        'delegated-from': 'cal-address',
        'delegated-to': 'cal-address',
        'dir': 'uri',
        'encoding': 'text',
        'fmttype': 'text',
        'fbtype': 'text',
        'language': 'text',
        'member': 'cal-address',
        'partstat': 'text',
        'range': 'text',
        'related': 'text',
        'reltype': 'text',
        'role': 'text',
        'rsvp': 'boolean',
        'sent-by': 'cal-address',
        'tzid': 'text',
        'value': 'text',
    })

    def for_property(self, name):
        """Returns a the default type for a property or parameter
        """
        return self[self.types_map.get(name, 'text')]

    def to_ical(self, name, value):
        """Encodes a named value from a primitive python type to an icalendar
        encoded string.
        """
        import pdb; pdb.set_trace()
        type_class = self.for_property(name)
        return type_class(value).to_ical()

    def from_ical(self, name, value):
        """Decodes a named property or parameter value from an icalendar
        encoded string to a primitive python type.
        """
        type_class = self.for_property(name)
        decoded = type_class.from_ical(value)
        return decoded
