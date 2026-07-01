import os
import multiprocessing
import signal
import sys
import django
import time
import json

from istos.models import ScrapeJob, Link
from background_task.models import Task

from istos.utils import extract_items

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('num_workers', type=int)

    def handle(self, *args, **options):
        new_params = None 
        num_workers = options['num_workers']

        while True:

            if Task.objects.count() > num_workers:
                scrape_job = ScrapeJob.objects.filter(
                    #__in cheks for either
                    scrape_type__in=['scrape', 'update'], 
                    status='queued'
                ).last()
                if scrape_job:
                    latest_job = ScrapeJob.objects.filter(scrape_type='extraction', status='running').last()
                    if latest_job:
                        link_id = Link.objects.get(url=latest_job.url).id

                        tasks = Task.objects.all()

                        for task in tasks:
                            params = json.loads(task.task_params)

                            if params[0][0] == link_id:
                                new_params = params
                                break

                        latest_job.status='paused'
                        latest_job.save()

                        extract_items(new_params[0][0], new_params[0][1], new_params[0][2], priority=1)
                        time.sleep(30)  

            else:
                time.sleep(5)