from django.urls import re_path
from .consumers import ScraperLogConsumer

websocket_urlpatterns = [
    #re_path(r"ws/test/$", ScraperLogConsumer.as_asgi()),
    re_path(r"ws/test/(?P<task_id>\w+)/$", ScraperLogConsumer.as_asgi()),
]