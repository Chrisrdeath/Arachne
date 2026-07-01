import argparse
import os
import multiprocessing
import signal
import sys
import django

from django.core.management import execute_from_command_line

graceful_shutdown_requested = False

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arachne.settings')
django.setup()

parser = argparse.ArgumentParser()
parser.add_argument('--no-monitor', action='store_true', help='Disable worker monitor')
parser.add_argument('--shutdown', action='store_true', help='Shuts down computer after all work is done')
parser.add_argument('num_workers', type=int, help='Number of workers')

def run_worker(worker_id):
    print(f'Starting background worker {worker_id}')
    execute_from_command_line(['manage.py', 'process_tasks'])

def shutdown_graceful(signum, frame):
    global graceful_shutdown_requested
    graceful_shutdown_requested = True

def shutdown_immediate(signum, frame):
    print("Shutting down all processes...")
    try:
        for p in processes:
            p.terminate()
        
    except Exception as e:
        print(f"Failed to shutdown: {e}")
    finally:
        #Delete all JSON
        sys.exit(0)

def start_monitor(num_workers):
    print(f'Starting worker monitor')
    execute_from_command_line(['manage.py', 'monitor_worker', str(num_workers)])

def background_monitor(task):
    execute_from_command_line(['manage.py', 'background_monitor', task])

if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown_immediate)  #Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_immediate) #Termination signal

    args = parser.parse_args()

    num_workers = args.num_workers

    if len(sys.argv) < 2:
        print("Usage: python dev_workers.py <num_workers>")
        sys.exit(1)

    processes = []

    for i in range(num_workers):
        p_worker = multiprocessing.Process(target=run_worker, args=(i,))
        processes.append(p_worker)

    if args.no_monitor:
        print("Worker Monitor Disabled...")
    else:
        monitor_process = multiprocessing.Process(target=start_monitor, args=(num_workers,))
        processes.append(monitor_process)

    if args.shutdown:
        print("Computer will shutdown after finishing all tasks")
        shutdown = multiprocessing.Process(target=background_monitor, args=('shutdown',))
        processes.append(shutdown)

    for p in processes:
        p.start()

    for p in processes:
        p.join()
