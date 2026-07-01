import logging

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class Logger():
    def __init__(self, file_label = ''):
        self.info_logger = logging.getLogger('spider')
        self.debug_logger = logging.getLogger('spider_debug')

        self.info_logger = logging.LoggerAdapter(self.info_logger, {'file': file_label})
        self.debug_logger = logging.LoggerAdapter(self.debug_logger, {'file': file_label})

    def info(self, msg, *args, **kwargs):
        self.info_logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.info_logger.warning(msg, *args, **kwargs)

    
    def debug(self, msg, *args, **kwargs):
        self.debug_logger.debug(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.debug_logger.error(msg, *args, **kwargs)


class WebSocketLogHandler(logging.Handler):

    def __init__(self, task_id=None, level="INFO"):
        super().__init__()
        self.task_id = task_id
        self.level = level

    def emit(self, record):
        try: 
            channel_layer = get_channel_layer()
            message = self.format(record)
            async_to_sync(channel_layer.group_send)(
                f"scraper_({self.task_id})",
                {
                    "type": "scraper.log",
                    "message": message,
                    "level": self.level,
                }
            )

        except Exception:
            pass


