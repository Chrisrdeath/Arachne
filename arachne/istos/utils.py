import logging
import os
import re
import requests
import random
import time
import warnings

from background_task import background
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from django.utils import timezone
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from urllib.parse import urljoin

from .models import *
from static.libs.utils import exceptions as exc

from static.libs.utils.header import Header
from static.libs.extracting.extractor import Extractor, Parallel_Extractor

from static.libs.scraping.link_scraper import Link_Scraper
from static.libs.scraping.media_scraper import Media_Scraper
from static.libs.scraping.video_scraper import Video_Scraper


file_label = '-UTILS'

info_logger = logging.LoggerAdapter(logging.getLogger('spider'), {'file': file_label})
debug_logger = logging.LoggerAdapter(logging.getLogger('spider_debug'), {'file': file_label})

class Validate:
    def URL(url):
        url = url.lower()

        if not url.startswith(('http://', 'https://')):
            raise exc.URLError()

class Conductor():

    def get_site(self):
        #get site from url
        site = self.url.split('/')[2]

        #make sure www is out of the site
        if 'www' in site:
            period = site.split('.')
            period = period[1:]
            site = '.'.join(period)

        return site

    def get_title(self):
        response = requests.get(self.url, headers=self.header)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string if soup.title else ""

        if title == "":
            user_agent = self.header_obj.generate_ua("Firefox")

            options = webdriver.FirefoxOptions()
            options.add_argument("-headless")
            options.set_preference("general.useragent.override", user_agent)
            driver = webdriver.Firefox(options=options)

            driver.get(self.url)
            title = driver.title

        info_logger.info(f"Title: {title}")
        
        # Clean title for filename
        import re
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title

    def get_vid_title(self):

        response = requests.get(self.url, headers=self.header)
        soup = BeautifulSoup(response.content, 'html.parser')

        header = None

        header = soup.get('h1')

        if header==None:
            print('Header None')

        print(header)

    #Create Scraper depending on scrape type
    def create_scraper(self):
        match self.scrape_type:
            case "media":
                self.title = self.get_title()
                return Media_Scraper(self.url, self.site, self.title)

            case "links":
                self.title = self.get_title()
                return Link_Scraper(self.url, self.site, self.title)

            case "video":
                self.title = self.get_vid_title()
                return Video_Scraper(self.url, self.site, self.title)

    def __init__(self, scrape_type, url):
        self.scrape_type = scrape_type
        self.url = url

        self.header_obj = Header(self.url)
        self.header = {
            "User-Agent": self.header_obj.user_agent,
            "Referer": self.header_obj.referer,
            "Accept-Encoding": "gzip, deflate, br"
        }

        self.site = self.get_site()
        

        self.scraper = self.create_scraper()

    #Creates a header and tries to scrape with requests first
    def get_items(self, selenium=False):
        try:
            items_scraped = self.scraper.start_scraping(selenium)

            info_logger.info(f"Items scraped: {items_scraped}")
        except Exception as e:
            raise exc.ItemScrapeError()

    #Save scraped items to db
    def save_items(self):
        try:
            saved_items = self.scraper.save_items()

            info_logger.info(f"Items saved: {saved_items}")

        except Exception as e:
            debug_logger.error(e)
            raise exc.ItemSaveError()

#Scrapes Pages
@background()
def scrape_items(url, scrape_type, curr_job_id):
    if(scrape_type == "unknown"):
        raise exc.UnknownScrapeTypeError()

    curr_job = ScrapeJob.objects.get(id=curr_job_id)
        
    info_logger.info(f"Scraping site {url}")

    BASE_PATH = str(f"{Path(__file__).resolve().parents[1]}")
    
    try:
        json_path = os.path.join(BASE_PATH, 'static', 'json')
        if not os.path.exists(json_path):
            info_logger.info("No JSON folder found, Creating one...")
            os.mkdir(json_path)
    except Exception as e:
        ScrapeJob.objects.filter(id=curr_job.id).update(status="failed")
        debug_logger.error(f"JSON folder could not be created {e}")

    try:
        for scraper in scrape_type:
            debug_logger.debug(f"{scraper.upper()}")

            #create Scrape Conductor
            conductor = Conductor(scraper, url)
            
            ScrapeJob.objects.filter(id=curr_job.id).update(status="running")

            if scrape_type=="video":
                conductor.get_vid_item()

            else:
                conductor.get_items()
                conductor.save_items()

            ScrapeJob.objects.filter(id=curr_job.id).update(status="completed")

            info_logger.info(f"{scraper.upper()} Finished")

        info_logger.info("Site Scraped Successfully")

    except Exception as e:
        ScrapeJob.objects.filter(id=curr_job.id).update(status="failed")
        debug_logger.error(f"Task failed {e}")

#Save Files to Computer
@background()
def extract_items(parent_id, ids, curr_job_id):
    try:
        save_dir = Settings.objects.filter(settingName='save_loc').values_list("addInfo", flat=True).first()
        link = Link.objects.get(id=parent_id)

        curr_job = ScrapeJob.objects.get(id=curr_job_id)

        txt = link.title
        folder = link.title
        info_logger.info(f"Scraping site {folder}")

        ScrapeJob.objects.filter(id=curr_job.id).update(status='running')

        prev_page = link.url

        #Creates a directory structure based on how pages were scraped
        while link.hasParent:
            link = link.hasParent
            folder = os.path.join(link.title, folder)

        files_save_dir = os.path.join(save_dir, folder)

        info_logger.info(files_save_dir)

        save_info = {
            "save_dir": files_save_dir,
            "prev_page": prev_page,
            "items": []
        }

        id_list = ids.split(',')

        for url_id in id_list:

            item_info = Items.objects.filter(id=url_id).first()
            item = {
                "id": item_info.id,
                "url": item_info.url,
                "download_btn": item_info.downloadBtn
            }
            save_info["items"].append(item)

        parallel_processing = Settings.objects.get(settingName = "parallel_processing")
        
        start = time.time()
        #This is where the extracting starts
        if parallel_processing.on:
            Saver = Parallel_Extractor(link, save_info)
            Saver.parallel_extracting(curr_job)
        else:
            Saver = Extractor(save_info, link)
            Saver.download_items(curr_job)
        
        txt_save_dir = os.path.join(files_save_dir, f"{txt}.txt")

        ScrapeJob.objects.filter(id=curr_job.id).update(status="completed", completed_at=timezone.now())
        info_logger.info("Finished Extracing Items")

        elapsed = time.time() - start
        minutes = int(elapsed // 60)
        seconds = elapsed % 60

        #Log how long extracting took
        info_logger.info(f"Extracting took: {minutes}m {seconds:.1f}s")

        #info for when page was scraped last
        with open(txt_save_dir, 'w') as f:
            f.write(f"{folder} last scraped at {timezone.now()}")

    except Exception as e:
        ScrapeJob.objects.filter(id=curr_job.id).update(status="failed")
        debug_logger.error(f"Task failed: {e}")

#Delete indiviual Item or Link
def delete_items(parent_id, ids):
    split_ids = ids.split(',')
    for id in split_ids:
        Items.objects.filter(id=id, link_id=parent_id).first().delete()

#Save parent link ass foreignkey
def parent_link(id, p_id):
    link = Link.objects.get(id=id)
    p_link = Link.objects.get(id=p_id)
    link.hasParent = p_link
    link.save()

