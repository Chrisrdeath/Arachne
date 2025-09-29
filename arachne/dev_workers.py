import os
import multiprocessing
import signal
import sys
import django

from django.core.management import execute_from_command_line

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arachne.settings')
django.setup()

def run_worker(worker_id):
    print(f'Starting background worker {worker_id}')
    execute_from_command_line(['manage.py', 'process_tasks'])

def shutdown(signum, frame):
    print("Shutting down all processes...")
    for p in processes:
        p.terminate()
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown)  #Ctrl+C
    signal.signal(signal.SIGTERM, shutdown) #Termination signal

    if len(sys.argv) < 2:
        print("Usage: python my_script.py <num_workers>")
        sys.exit(1)

    try:
        num_workers = int(sys.argv[1])
    except ValueError:
        print("Error: num_workers must be an integer")
        sys.exit(1)


    processes = []

    for i in range(num_workers):
        p_worker = multiprocessing.Process(target=run_worker, args=(i,))
        processes.append(p_worker)

    for p in processes:
        p.start()

    for p in processes:
        p.join()
