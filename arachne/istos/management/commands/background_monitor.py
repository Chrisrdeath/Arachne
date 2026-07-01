import os
import multiprocessing
import signal
import sys
import django
import time
import json

from background_task.models import Task

from istos.utils import extract_items

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('task', type=str)

    def handle(self, *args, **options):
        task = options['task']

        match task:
            case 'shutdown':

                while True:
                    shut_time = 60

                    while Task.objects.count() == 0:
                        print(f'All tasks have been completed, shutting down in {shut_time} seconds...')
                        if shut_time>0:
                            mins, secs = divmod(shut_time, 60)
                            timer = '{:02d}:{:02d}'.format(mins, secs)
                            print(timer, end='\r')
                            time.sleep(1)
                            shut_time -= 1

                        elif shut_time<=0:
                            os.system('shutdown /s /t 0')