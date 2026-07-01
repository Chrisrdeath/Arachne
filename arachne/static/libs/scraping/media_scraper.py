import json
import logging
import math
import multiprocessing
import os
import psutil
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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urljoin

#Arachne Django
from istos.models import *

#Static Library
from static.libs.mixins import ScrapingMixin, TagProccessingMixin
from static.libs.scraping.parallel_scraper import Parallel_Scraper
from static.libs.utils import scraper_constants as sc
from static.libs.utils.header import Header

#Websockets
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

file_label = '-MEDIA'

logger = logging.LoggerAdapter(logging.getLogger('spider'), {'file': file_label})
debug_logger = logging.LoggerAdapter(logging.getLogger('spider_debug'), {'file': file_label})

JSON_MEDIA = Path(__file__).parents[2] /"json"
MAX_WORKERS = max(1, int(psutil.cpu_count(logical=False) * 0.4))

class Media_Scraper(ScrapingMixin, TagProccessingMixin):
    #These are for the 429 loop
    WAIT_TIME = 0
    RETRIES = 0

    MEDIA_LOAD_TYPE = [
        'infinite',
        'lazy-load'
    ]

    #Create entry in Link table
    def create_link(self):
        link, created = Link.objects.get_or_create(
            url=self.url,
            defaults = {'site': self.site, 'title': self.title}
        )
        link_type = LinkType.objects.get(slug='media')
        link.linkType.add(link_type)

        return link

    def __init__(self, url, site, title):
        self.logger = logger

        self.PIC_FORMATS = list(Formats.objects.filter(type='pic', formSave=True).values_list('formName', flat=True))
        self.VID_FORMATS = list(Formats.objects.filter(type='vid', formSave=True).values_list('formName', flat=True))

        self.FORMATS = list(set(self.PIC_FORMATS + self.VID_FORMATS))

        self.find_pages = Settings.objects.get(settingName = "get_pages")
        self.parallel_processing = Settings.objects.get(settingName = "parallel_processing")

        self.url = url
        self.site = site
        self.title = title

        
        self.site_type = "SSR"
        self.engine_choice = "Firefox"

        if "php" in url.lower():
            self.site_type = "PHP"

        logger.info(f"Site: {self.site}")

        self.header_obj = Header(self.url) 
        self.header = {
            "User-Agent": self.header_obj.user_agent,
            "Referer": self.header_obj.referer,
            "Accept-Encoding": "gzip, deflate, br"
        }

        self.db_link = self.create_link()

        #Tags for Media
        self.tags = ['img', 'video']

        #Sources for media
        self.attrs = ['src', 'poster', 'href', 'data-poster', 'data-src']

        self.current_items = 0
        self.current_tags = 0
        self.current_thmb_tags = 0

        self.full_links = []
        self.link_items = []
        self.thmb_links = []
        self.thmb_tags = []
    
        self.driver = None
        self.is_pagination = False
        self.items_scraped = 0
        self.pages = []
        self.vid_sleep = False
        self.vid_sleep_time = 10


    def start_scraping(self, selenium):
        max_retries = 3
        retry_delay = 5

        start = time.time()

        try:
            logger.info("Starting Media Scrape")
            if(selenium == False):
                soup = self.req_scrape()
            else:
                soup = self.sel_scrape()
                
            if self.site_type == "SSR":
                for check in sc.ANGULAR_CHECK:
                    angular_check = soup.find(check)
                    if angular_check and "ng-version" in angular_check.attrs:
                        self.site_type = "ANGULAR"

            logger.info(f"Site Type: {self.site_type}")

            self.scrape_loop(soup)

            
            return self.items_scraped

        except Exception as e:
            
            debug_logger.info(f"Function: start_scraping: {e}")

        finally:
            elapsed = time.time() - start
            minutes = int(elapsed // 60)
            seconds = elapsed % 60

            

            logger.info(f"Scraping took: {minutes}m {seconds:.1f}s")
            self.driver.quit()

    #Loop scraping pages
    def scrape_loop(self, soup, driver=None):

        try:
            if self.find_pages.on:  
                self.get_pages(soup)

            logger.info(f"Number of Pages: {len(self.pages)+1}")

            if self.pages:
                if self.parallel_processing.on:
                    self.parallel_page_scraping(MAX_WORKERS)
                
                else:
                    self.get_tags(soup)
                    for page in self.pages:
                        self.url = self.url.rstrip('/')

                        if self.is_pagination:
                            new_link = (f"{self.url}{page}")    
                        else:
                            new_link = (f"{self.url}/{page}")

                        logger.info(f"Page: {new_link}")

                        soup = self.sel_scrape(new_link)
                        self.get_tags(soup)
                        self.log_scrape_info

                        if self.thmb_tags:
                            self.get_full_res_page()

                        if self.thmb_links:
                            self.get_full_res_file()

                        if self.full_links:
                            self.get_final_link(self.full_links)

            else:
                self.get_tags(soup)

                self.log_scrape_info
                
                if self.thmb_tags:
                    self.get_full_res_page()
            
                if self.thmb_links:
                    #self.get_full_res_file()
                    self.parallel_thmb_scraping()
                
                if self.full_links:
                    self.get_final_link(self.full_links)


        
        except Exception as e:
            logger.error(f"scrape_loop: {e}")
            
    #Checks if page has any items
    def page_check(self, soup):
        page_items = 0
        for tag in soup.find_all(self.tags):
            page_items+=1

        return page_items

    #Scrape thumbnails
    def thumb_scrape(self, link):

        soup = self.sel_scrape(link, loop=False)

        body = soup.find('body')
        body_classes = body.get('class', [])
        angular_indicators = ['mat-', 'ng-', 'angular']
        is_angular = any(any(indicator in bcls for indicator in angular_indicators) for bcls in body_classes)

        for tag in soup.find_all(self.tags):
            if tag.name == "video":
                if is_angular:
                    src_link = tag.get('src')

                    if not src_link:
                        sources = tag.find_all('source')

                        for source in sources:
                            src_link = source.get('src')
                            if src_link:
                                break

                    self.set_download_btn(src_link, link)

            elif 'src' in tag.attrs:
                src_link = tag['src']

                if 'icon' in src_link:
                    continue

                #checks for angular
                if is_angular and any(thmb in src_link.lower() for thmb in sc.THMB_KEYWORDS):

                    self.set_download_btn(src_link, link)                   
                    

                elif any(thmb in src_link.lower() for thmb in sc.THMB_KEYWORDS):
                    logger.info("PHP")

                    normal_res = tag.find_parent('a')
                    
                    #This is looking for php links for full res
                    if normal_res and 'href' in normal_res.attrs:
                        if 'javascript' in normal_res['href']:
                            php_onclick = normal_res['onclick']
                            img_link = php_onclick.split('\'')[1]

                            self.link_items.append(img_link)

                else:
                    logger.info("Full Res Already")

                    self.link_items.append(src_link)

    #Look for download button and set to true
    def set_download_btn(self, src_link, link):
        angular_menu = ['mat-mdc-menu-trigger', 'mat-menu-trigger']

        scraper = Proxy_Scrape(url)
        driver = scraper.proxy_sel()

        wait = WebDriverWait(self.driver, 10)

        for menu_class in angular_menu:
            button = self.driver.find_elements(By.CLASS_NAME, menu_class)
            if button:
                button[0].click()
                
                #Menu Panel opens
                menu_panel = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[id^="mat-menu-panel-"]'))
                )
                break
        
        try:
            download_btn = menu_panel.find_element(By.XPATH, ".//*[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')]")
            
            format = src_link.split('.')[-1].upper().rstrip('/')

            if format in self.PIC_FORMATS:
                self.link_items.append([link, 'dwn_btn', 'pic'])
            elif format in self.VID_FORMATS:
                self.link_items.append([link, 'dwn_btn', 'vid'])
            else:
                #self.link_items.append([link, 'dwn_btn', 'unknown'])
                logger.info('Unknown Download Type')

        except TimeoutException:
            debug_logger.info(f"Timeout waiting for menu panel on {link}")
            return
        except NoSuchElementException:
            debug_logger.info(f"Download button not found on {link}")
            return
        except:
            #logger.info("No Download Button Found")
            #no download button
            pass

    #Saves items to DB
    def save_items(self):
        saved_items = 0

        logger.info(f"3:{self.link_items}")
        
        print("")
        logger.info("Saving Items")

        #rules
        media_rules = Rules.objects.filter(rule_type='media', action_choice="exclude")
        
        try:
            if None in self.link_items:
                logger.debug("None Items in list")
                self.link_items = [x for x in self.link_items if x is not None]

            for link_item in self.link_items:
                logger.info(link_item)
                if isinstance(link_item, list):
                    #logger.info("Download Button Media")
                    
                    if link_item[1]=="dwn_btn":
                        if not Items.objects.filter(url=link_item[0]).exists():
                            Items.objects.create(url=link_item[0], site=self.site, type=link_item[2], link_id=self.db_link.id, downloadBtn=True)
                    
                    continue

                should_break = False
                format = link_item.split('.')[-1].upper().rstrip('/')

                if "?" in format:
                    format = format.split('?')[0]

                if format in self.FORMATS:
                    for rule in media_rules:
                        if rule.selector_type=="name":
                            if rule.match_type=="contains":
                                if rule.text.lower() in link_item.lower():
                                    should_break = True
                                    break
                            elif rule.match_type=="ends with":
                                if link_item.rstrip(f".{format.lower()}").endswith(rule.text):
                                    should_break = True
                                    break
                            elif rule.match_type=="begins with":
                                if link_item.rstrip(f".{format.lower()}").startswith(rule.text):
                                    should_break = True
                                    break

                    if should_break==True:
                        continue

                    if not Items.objects.filter(url=link_item).exists():
                        if format in self.PIC_FORMATS:
                            Items.objects.create(url=link_item, site=self.site, type='pic', link_id=self.db_link.id)
                            saved_items+=1
                        elif format in self.VID_FORMATS:
                            Items.objects.create(url=link_item, site=self.site, type='vid', link_id=self.db_link.id)
                            saved_items+=1
                        else:
                            print(f"Not saving: {link_item}")
                else:
                    logger.info(f"Not Allowed Media: {link_item}")
                    print(f"Not saving: {link_item}")
                    continue

            return saved_items      

        except Exception as e:
            debug_logger.info(e)

        finally:
            if self.driver:
                self.driver.quit()
            return saved_items

    #Loop for 429 connection codes
    def tmr_loop(self):
        print("429 Too Many Requests")
        time.sleep(15+self.wait_time)
        self.wait_time += 10

    #Seperate links into lists using max_workers
    def get_workers_work(self, max_workers, parallel_pages):
        self.actual_workers = min(max_workers, len(parallel_pages))

        logger.info(f"Amount of Workers: {self.actual_workers}")
        
        # Calculate base size and remainder
        base_size = len(parallel_pages) // self.actual_workers
        remainder = len(parallel_pages) % self.actual_workers

        batches = []
        start_index = 0

        for i in range(self.actual_workers):
            batch_size = base_size + (1 if i < remainder else 0)
            batch = parallel_pages[start_index:start_index + batch_size]
            batches.append(batch)
            start_index += batch_size

        logger.info(f"Created {len(batches)} batches with sizes: {[len(b) for b in batches]}")
        return batches

    #Scraping pages concurrently
    def parallel_page_scraping(self, max_workers=4):
        logger.info("Starting Parrallel Scraping")
        parallel_pages = [self.url]
        batches = []
        results = []

        #logger.info(len(self.pages))

        for page in self.pages:
            self.url = self.url.rstrip('/')

            if self.is_pagination:
                new_link = (f"{self.url}{page}")    
            else:
                new_link = (f"{self.url}/{page}")

            parallel_pages.append(new_link)

        #logger.info(parallel_pages)

        batches = self.get_workers_work(max_workers, parallel_pages)
        
        with Pool(processes=min(self.actual_workers, len(batches))) as pool:
            indexed_batches = list(enumerate(batches))
            results = pool.starmap(process_pages_standalone, indexed_batches)
        
        for result in results:
            self.current_items += result['current_items']
            self.current_tags += result['current_tags']
            self.items_scraped += result['items_scraped']
            self.thmb_links.extend(result['thmb_links'])
            self.link_items.extend(result['link_items'])


        results = None
        parallel_pages = []

        if self.thmb_links:
            self.parallel_thmb_scraping(max_workers)

    #Scraping thumbnails concurrently
    def parallel_thmb_scraping(self, max_workers=4):
        batches = self.get_workers_work(max_workers, self.thmb_links)

        with Pool(processes=min(self.actual_workers, len(batches))) as pool:
            indexed_batches = list(enumerate(batches))
            results = pool.starmap(process_thmbs_standalone, indexed_batches)

        for result in results:
            self.items_scraped += result['items_scraped']
            self.link_items.extend(result['link_items'])

    #region properties
        @property
        def scrape_info(self):
            return{
                'current_items': self.current_items,
                'current_tags': self.current_tags,
                'current_thmb_tags': len(self.thmb_tags)
            }

        @scrape_info.setter
        def scrape_info(self, values):
            self.current_items = values[0]
            self.current_tags = values[1]

        @property
        def log_scrape_info(self):
            logger.info(f"Total Items Grabbed: {self.current_items}")
            logger.info(f"Number of Tags grabbed: {self.current_tags}")
            logger.info(f"Number of Thumbnail Tags grabbed: {len(self.thmb_tags)}\n")
    #endregion

#region standalone functions
#Scrape pages
def process_pages_standalone(idx, batch_data):
    try:
        par = Parallel_Scraper(batch_data[0], idx)
       
        for bd in batch_data:
            cpu_usage = psutil.cpu_percent(interval=0.1)

            if cpu_usage > 90:
                print("CPU usage higher than 90%")
                time.sleep(2)
            elif cpu_usage > 80:
                print("CPU usage higher than 80%")
                time.sleep(1)
            elif cpu_usage > 70:
                print("CPU usage higher than 70%")
                time.sleep(0.5)
            #logger.info(f"batch item: {bd}")
            par.scrape_loop(bd, True)

        par.write_json()

        if par.driver:
            par.driver.quit()

            JSON_MEDIA

        media_paths = os.path.join(JSON_MEDIA, f'media-{idx}.json')

        with open(media_paths, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        return {
            'current_items': par.current_items,#Int
            'current_tags': par.current_tags,#Int
            'items_scraped': par.items_scraped,#Int
            'thmb_links': data['thmb_links'],#Strings
            'link_items': data['link_items']#Strings
        }

    except Exception as e:
        print(f"process_pages_standalone: {e}")

#Finishing scraping thumbnail links
def process_thmbs_standalone(idx, batch_data):
    try:
        par = Parallel_Scraper(batch_data[0], idx)

        par.thmb_loop(batch_data, True)

        par.write_json()

        if par.driver:
            par.driver.quit()

        media_paths = os.path.join(JSON_MEDIA, f'media-{idx}.json')

        with open(media_paths, 'r', encoding='utf-8') as file:
            data = json.load(file)

        print(data)

        return {
            'items_scraped': par.items_scraped,#Int
            'link_items': data['link_items']#Strings
        }
    except Exception as e:
        print(f"process_thmbs_standalone: {e}")
#endregion




