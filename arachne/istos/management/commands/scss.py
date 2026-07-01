import signal
import subprocess
import sys
import os


from pathlib import Path

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Watch SCSS files and compile to CSS'

    def __init__(self):
        super().__init__()
        self.process = None        


    def shutdown(self, signum, frame):
        print("Shutting down SCSS watcher...")
        self.process.terminate()
        sys.exit(0)

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            nargs='?', #This makes it optional 
            type=str,
            default='main',
            help='filename for SCSS compilation'
        )

    def handle(self, *args, **options):
        signal.signal(signal.SIGINT, self.shutdown)  #Ctrl+C
        signal.signal(signal.SIGTERM, self.shutdown) #Termination signal

        new_params = None

        static_css_dir = Path('static/css')

        file_name = options['file']

        

        os.chdir(static_css_dir)
        
        try:
            self.process = subprocess.Popen(['sass', '--watch', '--no-source-map',  f'{file_name}.scss', f'{file_name}.css'], shell=True)
            self.stdout.write(self.style.SUCCESS(f"Starting SCSS watcher for {file_name}.scss"))
            #self.process.wait()
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"{file_name}.scss not found"))