from __future__ import unicode_literals

import os, uuid
from datetime import datetime, timedelta, date

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone

from PIL import Image
import logging

logger = logging.getLogger(__name__)

def room_img_upload_to(instance, filename):
    # rename file to a unique string
    ext = filename.split('.')[-1]
    filename = "%s_%s.%s" % (instance.name, uuid.uuid4(), ext.lower())

    upload_path = "rooms/"
    upload_abs_path = os.path.join(settings.MEDIA_ROOT, upload_path)
    if not os.path.exists(upload_abs_path):
        os.makedirs(upload_abs_path)
    return os.path.join(upload_path, filename)

class RoomManager(models.Manager):

    def available(self, start=None, end=None, has_av=None, has_phone=None, floor=None, seats=None):
        # Default time is now, for one hour
        if not start:
            start = timezone.now()
        if not end:
            end = start + timedelta(hours=1)

        rooms = self.all()

        if has_av != None:
            rooms = rooms.filter(has_av=has_av)
        if has_phone != None:
            rooms = rooms.filter(has_phone=has_phone)
        if floor != None:
            rooms = rooms.filter(floor=floor)
        if seats != None:
            rooms = rooms.filter(seats__gte=seats)

        straddling = Q(event__start_ts__lte=start, event__end_ts__gt=start)
        sandwich = Q(event__start_ts__gte=start, event__start_ts__lt=end)
        overlap = Q(event__start_ts__lte=start, event__end_ts__gte=end)
        rooms = rooms.exclude(straddling| sandwich | overlap)

        return rooms

class Room(models.Model):
    name = models.CharField(max_length=64)
    location = models.CharField(max_length=128, null=True)
    description = models.TextField(blank=True, null=True)
    floor = models.SmallIntegerField()
    seats = models.SmallIntegerField()
    max_capacity = models.SmallIntegerField()
    has_av = models.BooleanField(default=False)
    has_phone = models.BooleanField(default=False)
    default_rate = models.DecimalField(decimal_places=2, max_digits=9)
    #image = models.ImageField(upload_to=room_img_upload_to, blank=True, null=True, help_text="Images should be 500px x 325px or a 1 to 0.65 ratio ")
    image = models.ImageField(upload_to=room_img_upload_to, blank=True, null=True)

    objects = RoomManager()

    def __str__(self):
        return self.name

    def get_events(self, start, end):
        return self.event_set.filter(start_ts__gte=start, end_ts__lte=end)

    def get_raw_calendar(self):
        # Calendar is a list of {hour, minute} time blocks
        calendar = []

        # Default OPEN_TIME is 8AM
        open_hour = '8'
        open_minute = '00'
        if hasattr(settings, 'OPEN_TIME') and ':' in settings.OPEN_TIME:
            open_hour = settings.OPEN_TIME.split(':')[0]
            open_minute = settings.OPEN_TIME.split(':')[1]

        # Default CLOSE_TIME is 6PM
        close_hour = '18'
        close_minute = '00'
        if hasattr(settings, 'CLOSE_TIME') and ':' in settings.CLOSE_TIME:
            close_hour = settings.CLOSE_TIME.split(':')[0]
            close_minute = settings.CLOSE_TIME.split(':')[1]

        for num in range(int(open_hour), int(close_hour)):
            minutes = open_minute
            for count in range(0, 4):
                time_block = {}
                calendar.append(time_block)
                if num <= 12:
                    time_block['hour'] = str(num)
                else:
                    time_block['hour'] = str(num - 12)
                time_block['mil_hour'] = str(num)

                time_block['minutes'] = minutes
                if minutes == '00':
                    minutes = '15'
                elif minutes =='15':
                    minutes = '30'
                elif minutes =='30':
                    minutes = '45'
                else:
                    minutes = '00'
                    num += 1
        return calendar

    def get_calendar(self, target_date=None):
        if not target_date:
            target_date = timezone.now().date()

        # Start with the raw calendar
        calendar = self.get_raw_calendar()

        # Extract the start and end times from our target date and the raw calendar
        first_block = calendar[0]
        last_block = calendar[len(calendar) - 1]
        tz = timezone.get_current_timezone()
        start = datetime(year=target_date.year, month=target_date.month, day=target_date.day, hour=int(first_block['mil_hour']), minute=int(first_block['minutes']), tzinfo=tz)
        end = datetime(year=target_date.year, month=target_date.month, day=target_date.day, hour=int(last_block['mil_hour']), minute=int(last_block['minutes']), tzinfo=tz)
        end = end + timedelta(minutes=15)
        #print("Start: %s, End: %s, TZ: %s" % (start, end, tz))

        # Loop through the events for this day and mark which blocks are reserved
        # We use time integers in the form of HOURMIN (830, 1600, etc) for comparison
        events = self.event_set.filter(room=self, start_ts__gte=start, end_ts__lte=end)
        for event in events:
            start_int = int(timezone.localtime(event.start_ts).strftime('%H%M'))
            end_int = int(timezone.localtime(event.end_ts).strftime('%H%M'))
            for block in calendar:
                block_int = int(block['mil_hour'] + block['minutes'])
                #print ("%d, %d, %d" % (start_int, end_int, block_int))
                if start_int <= block_int and block_int <= end_int:
                    #print "Reserved!"
                    block['reserved'] = True

        return calendar
