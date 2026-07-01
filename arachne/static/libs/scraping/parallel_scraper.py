import json
import logging
import os
import random
import re
import requests
import sys
import threading
import time
import warnings

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin

#Static Library
from static.libs.mixins import ScrapingMixin, TagProccessingMixin
from static.libs.utils import scraper_constants as sc
from static.libs.utils.header import Header

#Websockets
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from istos.models import Settings

from istos.models import *

TAGS = ['img', 'video']
ATTRS = ['src', 'poster', 'href', 'data-poster']

JSON_MEDIA = Path(__file__).parents[2] /"json"

class Parallel_Scraper(ScrapingMixin, TagProccessingMixin):
    def get_site(self):
        #get site from url
        site = self.url.split('/')[2]

        #make sure www is out of the site
        if 'www' in site:
            period = site.split('.')
            period = period[1:]
            site = '.'.join(period)

        return site

    def __init__(self, url, idx):
        SLEEP = Settings.objects.get(settingName = "grab_sleep")
        self.index = idx
        file_label = f'-PARALLEL-{self.index}'

        logger = logging.LoggerAdapter(logging.getLogger('spider'), {'file': file_label})
        debug_logger = logging.LoggerAdapter(logging.getLogger('spider_debug'), {'file': file_label})

        self.logger = logger

        #Var Constants
        self.PIC_FORMATS = list(Formats.objects.filter(type='pic', formSave=True).values_list('formName', flat=True))
        self.VID_FORMATS = list(Formats.objects.filter(type='vid', formSave=True).values_list('formName', flat=True))
        self.FORMATS = list(set(self.PIC_FORMATS + self.VID_FORMATS))

        #Var Setting
        self.url = url
        self.vid_sleep_time = 10
        self.engine_choice = "Firefox"

        #Var Initiation
        self.current_items = 0
        self.current_tags = 0
        self.current_thmb_tags = 0
        self.items_scraped = 0
        self.thmb_tags = []
        self.full_links = []
        self.thmb_links = []
        self.link_items = []
        self.driver = None
        self.soup = None
        self.vid_sleep = False
        

        #Var Creation
        self.site = self.get_site()
        self.header_obj = Header(self.url)
        self.header = {
            "User-Agent": self.header_obj.user_agent,
            "Referer": self.header_obj.referer,
            "Accept-Encoding": "gzip, deflate, br"
        }

        #image, picture, audio, source, track
        self.tags = ['img', 'video']
        #url
        self.attrs = ['src', 'poster', 'href', 'data-poster']

    def scrape_loop(self, bd, selenium=False):


        try:
            '''
            if not self.driver:
                if(selenium == False):
                   self.soup = self.req_scrape()
                else:
                   self.soup = self.sel_scrape()

            if not self.soup:
                self.driver.get(bd)
            '''
            self.soup = self.sel_scrape()

            soup = self.soup
            time.sleep(random.uniform(5, 8))

            self.get_tags(soup)
            self.logger.info(f"Pages: {bd}")
            self.log_scrape_info

            if self.thmb_tags:
                self.get_full_res_page()

            if self.full_links:
                self.get_final_link(self.full_links)

            self.json_data = {
                'thmb_links': self.thmb_links,
                'link_items': self.link_items
            }


        except Exception as e:
            self.logger.info(f"{e}")

        finally:
            self.soup = None

    def thmb_loop(self, batch_data, selenium=False):
        try:
            self.thmb_links = batch_data

            self.get_full_res_file()

            self.json_data = {
                'link_items': self.link_items
            }

        except Exception as e:
            self.logger.info(f"{e}")

    def write_json(self):
        media_paths = os.path.join(JSON_MEDIA, f'media-{self.index}.json')

        with open(media_paths, 'w',  encoding='utf-8') as file:
            json.dump(self.json_data, file, indent=4)

    @property
    def log_scrape_info(self):
        self.logger.info(f"Total Items Grabbed: {self.current_items}")
        self.logger.info(f"Number of Tags grabbed: {self.current_tags}")
        self.logger.info(f"Number of Thumbnail Tags grabbed: {len(self.thmb_tags)}\n")


