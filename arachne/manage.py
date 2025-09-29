#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

from secrets import token_urlsafe


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arachne.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

def env():
    try:
        if not os.path.exists(r"arachne/.env"):
            with open(r"arachne/.env", 'x') as f:
                f.write(f"SECRET_KEY = '{token_urlsafe(32)}'\nDEBUG = True")
            
    except Exception as e:
        print(e)
        
if __name__ == '__main__':
    env()
    main()
    
