import logging
import os
import re
import requests
import random
import threading
import time
import warnings
import sys
import psutil

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urljoin

#Django
from django.conf import settings

#Arachne Django
from istos.models import *

#Static Library
from static.libs.utils import exceptions as exc
from static.libs.utils import scraper_constants as sc
from static.libs.utils.header import Header

#Websockets
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class ScrapingMixin:

    #Connection code retry logic
    @staticmethod
    def safe_get(driver):
        original_get = driver.get

        def get_with_retries(url):
            max_retries = 3

            cc_retry_time = 0

            for attempt in range(max_retries):
                try:
                    time.sleep(cc_retry_time)

                    original_get(url)
                    
                    title = driver.title


                    if any(char.isdigit() for char in title):
                        match = re.search(r'\d+', title)

                        if match:
                            connection_code = int(match.group())

                            match connection_code:
                                case 403:
                                    raise exc.CC403
                                case 404:
                                    raise exc.CC404
                                case 429:
                                    raise exc.CC429
                                case 429:
                                    raise exc.CC429
                                case 503:
                                    raise exc.CC503
                                case 522:
                                    raise exc.CC522

                                case _:
                                    if "Not found" in title:
                                        raise exc.CC404
                
                except exc.CC403 as e:
                    print(f"Connection Error: {e}")
                    cc_retry_time = 5
                    raise

                except exc.CC429 as e:
                    cc_retry_time = 10
                    raise

                except Exception as e:
                    if attempt == (max_retries - 1):
                        raise
                    print(f"Retry {attempt + 1}: {e}")

        driver.get = get_with_retries

        return driver

    #Request Scraping - Non JS loading
    def req_scrape(self, link=None, loop=True):
        try:
            self.logger.info("Requests Scraper")
            self.link_items = []

            request = requests.get(self.url, headers=self.header)

            match request.status_code:
                case 200:

                    soup = BeautifulSoup(request.content, 'html.parser')

                    if '\uFFFD' in soup.get_text():
                        self.logger.info("Warning: Replacement characters detected!")
                        self.sel_scrape(self.url)

                    return soup


                #Likely scraper seen as bot
                case 403:
                    self.sel_scrape(self.url)

                #Link doesn't exist anymore
                case 404:
                    Link.objects.filter(url=self.url).first().delete()

                #Need to wait longer and retry in a little bit
                case 429:
                    self.tmr_loop()
                    self.req_scrape(self)
                    
        except Exception as e:
            self.logger.error(f"req_scrape: {e}")
            self.logger.info(f"Switching to Selenium")
            self.sel_scrape()

    #Selenium Scraping - JS loading
    def sel_scrape(self, link=None, loop=True):
        try:
            if not self.driver:
                self.driver = self.create_driver()

            url = link or self.url

            sleep = Settings.objects.get(settingName = "grab_sleep")

            self.driver.get(url)

            #Makes look less like a bot
            if(sleep.on) and int(sleep.addInfo)>0:
                self.logger.info(sleep.addInfo)
                time.sleep(int(sleep.addInfo))
            #time.sleep(15)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            return soup
        except Exception as e:
            self.logger.error(f"sel_scrape: {e}")

    #Create the driver for Selenium Scraping
    def create_driver(self):
        max_retries = 3

        for attempt in range(max_retries):


            try:
                engines = ["Firefox", "Chrome"]
                #self.engine_choice = random.choice(engines)
        
                new_driver = None

                self.logger.info("Starting Selenium Driver")
                match self.engine_choice:
                    case "Chrome":
                        new_driver = webdriver.Chrome()
                        new_driver.get(url)
                        time.sleep(10)
                    
                    case "Firefox":
                        user_agent = self.header_obj.generate_ua(self.engine_choice)

                        options = webdriver.FirefoxOptions()
                        options.add_argument("-headless")
                        options.set_preference("general.useragent.override", user_agent)
                        options.set_preference("marionette.port", 2829)
                        new_driver = webdriver.Firefox(options=options)
                        new_driver = ScrapingMixin.safe_get(new_driver)
                        

                return new_driver

            except SessionNotCreatedException as e:
                if attempt == (max_retries - 1):
                    raise
                print(f"Retrying to set prefrences {attempt + 1}: {e}")

            except Exception as e:
                self.logger.error(f"create_driver: {e}")
            
        #grab all nav tags, then check for nav keywords in classes
    
    #Get number of pages based on NAV tags known
    def get_pages(self, soup):
        pages_list = []
        nav_match = False
        class_lower = None
        first_page = True
        page_number = True
        
        #Parameter key
        para_key = ""
        per_page = 0
        overall = 0
        num_pages = 0

        next_page_suffix = ""
        last_page_suffix = ""
        back_up_suffix = ""
        page_link_suffix = ""

        #if PHP find &pid= number of items on page

        try:

            for tag in soup.find_all(sc.NAV_TAGS):
                classes = tag.get('class') or []

                if any(nav in classes for nav in sc.NAV_KEYWORDS):
                    nav_match = True

                if any('paginator' in c or 'pagination' in c for c in classes):
                    for link in tag.find_all('a'):
                        if(link.has_attr('alt')):
                            if(link['alt'] == 'next' or link['alt'] == 'next page'):
                                next_page_suffix = self.get_suffix(link['href'])
                            elif(link['alt'] == 'last' or link['alt'] == 'last page'):
                                last_page_suffix = self.get_suffix(link['href'])

                        else:
                            link_text = link.get_text()
                            
                            if(link_text in sc.NEXT_TEXT):
                                next_page_suffix = self.get_suffix(link['href'])
                                prev_link = link.find_previous_sibling('a')
                                if prev_link:
                                    back_up_suffix = self.get_suffix(prev_link['href'])
                            elif(link_text in sc.LAST_TEXT):
                                last_page_suffix = self.get_suffix(link['href'])
                
                #Found Pagination buttons
                if next_page_suffix:
                        
                    #print(next_page_suffix)
                    #print(last_page_suffix)
                    #print(back_up_suffix)

                    if last_page_suffix == "":
                        if next_page_suffix != back_up_suffix:
                            last_page_suffix = back_up_suffix


                    if next_page_suffix == back_up_suffix:
                        pages_list.append(next_page_suffix)
                    else:
                        page_link_suffix, query = next_page_suffix.rsplit('=', 1)
                        query = int(query)

                        base, overall = last_page_suffix.rsplit('=', 1)
                        overall = int(overall)
                                                            
                        if query != 2:
                            per_page = query
                            page_number = False

                        if page_number == False and last_page_suffix:
                            num_pages = int(overall/per_page)
                        elif page_number:
                            num_pages = overall

                        #print(num_pages)

                        for page in range(1, (num_pages)+1):
                            if page_number:
                                pages_list.append(f"{page_link_suffix}={page}")
                            else:
                                pages_list.append(f"{page_link_suffix}={int(per_page*page)}")
                    
                    break

                elif nav_match:
                    a_tag = tag.find_all('a')

                    if a_tag:
                        for anchor in a_tag:
                            if self.is_pagination:
                                text = anchor.get_text()
                                if text.isdigit():
                                    page_numbers.append(int(text))                                                           
                            #else:
                                #logger.info(f"Link Tag: {anchor}")
                        break
                    #Nav is likely, but not found
                    else:
                        print("Using binary search to find pages")
                        sleep = Settings.objects.get(settingName = "grab_sleep")

                        start = 1
                        low = 1
                        high = 2
                        #Trying ?page=
                        #ADD CHECKS FOR 404s
                        curr_page = (f"{self.url}?page={high}")

                        page_driver = self.create_driver()
                        page_driver.get(curr_page)
                        time.sleep(int(sleep.addInfo))
                        soup = BeautifulSoup(page_driver.page_source, 'html.parser')
                        page_items = self.page_check(soup)

                        while page_items != 0:
                            low = high
                            high*=2
                            curr_page = (f"{self.url}?page={high}")
                            page_driver.get(curr_page)
                            time.sleep(int(sleep.addInfo))
                            soup = BeautifulSoup(page_driver.page_source, 'html.parser')
                            page_items = self.page_check(soup)

                        while high - low > 1:
                            test = (low + high) // 2
                            curr_page = f"{self.url}?page={test}"
                            page_driver.get(curr_page)
                            time.sleep(int(sleep.addInfo))
                            soup = BeautifulSoup(page_driver.page_source, 'html.parser')
                            page_items = self.page_check(soup)
                            
                            if page_items != 0:
                                low = test   # works, move low up
                            else:
                                high = test  # fails, move high down

                        last_page = low
                        for page in range(2, last_page+1):
                            pages_list.append(f"?page={page}")                      

                    break

            #print(pages_list)
            self.pages = pages_list

        except Exception as e:
            print(f"Get pages: {e}")

    #Get suffix for page queries
    def get_suffix(self, page_link):
        suffix = page_link.split('?', 1)[1]
        suffix = (f"?{suffix}")

        return suffix

class TagProccessingMixin:
    
    #Grabs all tags in self.tags
    def get_tags(self, soup):
        try:
            for tag in soup.find_all(self.tags):
                self.current_items+=1
                thmb = self.check_if_thmb(tag)
                
                if thmb:
                    if tag.parent.name == 'a':
                        parent_tag = tag.parent

                        tag_attr = None
                        for attr in self.attrs:
                            if attr in parent_tag.attrs:
                                tag_attr = parent_tag.get(attr)

                        if tag_attr:
                            print(tag_attr)
                            if any(format.lower() in tag_attr for format in self.FORMATS):
                                self.full_links.append(parent_tag)
                                self.current_tags+=1
                            else:
                                self.thmb_tags.append(tag)
                                self.current_thmb_tags+=1
                    else:
                        self.thmb_tags.append(tag)
                        self.current_thmb_tags+=1
                    continue

                self.full_links.append(tag)
                self.current_tags+=1

        except Exception as e:
            self.logger.error(f"get_tags: {e}")
    
    #Checks if tag is a thumbnail with classes and links
    def check_if_thmb(self, tag):
        try:

            alt = tag.get('alt')
            if alt and "icon" in alt:
                return True

            classes = tag.get('class')
            if classes and any(thmb in class_name.lower() for class_name in classes for thmb in sc.THMB_KEYWORDS):
                return True
            
            if tag.parent.name == 'a':
                parent_tag = tag.parent
                classes = parent_tag.get('class')
                if classes and any(thmb in class_name.lower() for class_name in classes for thmb in sc.THMB_KEYWORDS):
                    return True

            tag_attr = None
            for attr in self.attrs:
                if attr in tag.attrs:
                    tag_attr = tag.get(attr)

                    if tag_attr and any(thmb in tag_attr.lower() for thmb in sc.THMB_KEYWORDS):
                        return True

        except Exception as e:
            self.logger.error(f"check_if_thmb: {e}")

    #Gets the link the thumbnail points too
    def get_full_res_page(self):
        try:
            for tag in self.thmb_tags:
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
                #Checks parents of thmb tag
                for parent in tag.parents:                
                    if parent.name == 'a':
                        anchor_tag = parent
                        cleaned_link = self.clean_link(anchor_tag.get('href'))
                        self.thmb_links.append(cleaned_link)
                        break
                    else:
                        anchor_tag = parent.find('a')
                        if anchor_tag:
                            cleaned_link = self.clean_link(anchor_tag.get('href'))
                            self.thmb_links.append(cleaned_link)
                            break

            #for index, link in enumerate(self.thmb_links):

        except Exception as e:
            self.logger.error(f"get_full_res_page: {e}")
    
    #Gets the file the thumbnail is for
    def get_full_res_file(self):
        file_link = None
        cleaned_link = None
        tag = None

        try:
            for num, link in enumerate(self.thmb_links):
                self.logger.info(f"THMB: {num+1}/{len(self.thmb_links)}")
                
                self.vid_sleep = time.sleep(random.uniform(5, 10))

                ext = link.split('.')[-1]

                if ext in self.VID_FORMATS:
                    self.vid_sleep = True

                self.logger.info("Going to Full Res Page")
                soup = self.sel_scrape(link)

                #if self.vid_sleep:
                    #time.sleep(self.vid_sleep_time)
                time.sleep(random.uniform(7, 10))

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                for tag in soup.find_all(self.tags):
                    if tag.name == "video":
                        #print(tag)
                        sources = tag.find_all("source")
                        
                        if len(sources)>1:
                            #print(sources)
                            for source in sources:
                                for attr in source.attrs:
                                    if attr == "type":
                                        if source[attr] == "video/mp4":
                                            video_link = source['src']
                        else:
                            source = tag.find('source')
                            print(source['src'])
                            video_link = source['src']

                        has_resolution = any(res in video_link.lower() for res in sc.VID_RESOLUTIONS)
                        
                        if has_resolution:
                            for res in sc.VID_RESOLUTIONS:
                                if res in video_link:
                                    file_link = video_link.replace(res, '')
                                    break
                        else:
                            file_link = video_link

                    #only get media based on ext at end, ignore links and .svgs associated with <img>
                    else:
                        #print(tag)
                        tag_attr = None
                        for attr in self.attrs:
                            if attr in tag.attrs:
                                tag_attr = tag.get(attr)
                                

                                if tag_attr:
                                    is_thumbnail = any(thumb in tag_attr.lower() for thumb in sc.THMB_KEYWORDS)
                                    
                                    if not is_thumbnail:
                                        file_link = tag_attr
                                        break
                                    elif tag_attr.count('.') > 1:
                                        split_link = tag_attr.split('.')
                                        for thmb in sc.THMB_KEYWORDS:
                                            if thmb in tag_attr.lower() and thmb == split_link[-2]:
                                                file_link = tag_attr.replace(thmb, '')
                                                break

                                        break
                    #Go up a set range, maybe 2~5 looking at main_tags and main_keywords then
                    #check for sibling media
                    #if file_link:
                        #print(tag.name)
                    
                    if file_link and isinstance(file_link, list):
                        for link in file_link:
                            file_link = re.sub(r'\.{2,}', '.', file_link)
                            cleaned_link = self.clean_link(file_link)

                    elif file_link:
                        file_link = re.sub(r'\.{2,}', '.', file_link)
                        cleaned_link = self.clean_link(file_link)

                    if cleaned_link and isinstance(cleaned_link, list):
                        for link in cleaned_link:
                            self.link_items.append(link)
                            #self.logger.info(f"Full Link: {link}")

                    elif cleaned_link:    
                        self.link_items.append(cleaned_link)
                        #self.logger.info(f"Full Link: {cleaned_link}")
                    self.items_scraped+=1

                #check if thumbnail kywd in link, remove it and if 404 find download btn
                #sys.exit(0)


        except Exception as e:
            self.logger.info(f"get_full_res_file: {e}")

        finally:
            self.vid_sleep = False
        
    #Gets the file for extracting later
    def get_final_link(self, list):
        try:
            for item in list:

                tag_attr = None
                for attr in self.attrs:
                    if attr in item.attrs:
                        full_img = item.get(attr)

                cleaned_link = None

                if '.' in full_img and '?' not in full_img:
                    extension = full_img.split('.')[-1]
                    ext_len = len(extension)
                    if not (2 < ext_len < 6):
                        return
                elif '.' not in full_img:
                    return
                
                cleaned_link = self.clean_link(full_img)
                #self.logger.info(cleaned_link)
                
                if cleaned_link and cleaned_link not in self.link_items:
                    self.link_items.append(cleaned_link)
                    self.items_scraped+=1

        except Exception as e:
            self.logger.error(f"get_final_link: {e}")

    #Makes links usable for extracting
    def clean_link(self, link):
        token = ""

        try:
            if not link:
                return None

            save_icons = Settings.objects.get(settingName = "save_icons")

            if any(i_kword in link.lower() for i_kword in sc.IGNORE_KEYWORDS):
                return None

            if not save_icons.on and "icon" in link:
                return None

            if '?' in link:
                token = link.split('?')[1]
                link = link.split('?')[0]
                

            if '.' in link:
                link_ext = link.split('.')[-1].upper()
                if link_ext not in self.FORMATS:
                    return None

            base_url = f"https://{self.site}"
            cleaned_link = None

            # Handle protocol-relative URLs
            if link.startswith("//"):
                cleaned_link = f"https:{link}"
            
            # Handle relative paths
            elif link.startswith(("/", "../", "./")):
                cleaned_link = urljoin(base_url, link)
            
            # Handle absolute URLs
            else:
                cleaned_link = urljoin(base_url, link)

            # Validate the result
            if cleaned_link == base_url or cleaned_link == base_url + "/" or cleaned_link.endswith('html'):
                    return None

            if token:
                cleaned_link = cleaned_link+'?'+token

            return cleaned_link
            
        except Exception as e:
            self.logger.error(f"clean_link: {e}")

    #region properties
    #Get Scrape numbers
    @property
    def scrape_info(self):
        return{
            'current_items': self.current_items,
            'current_tags': self.current_tags,
            'current_thmb_tags': len(self.thmb_tags)
        }

    #Set Scrape Numbers
    @scrape_info.setter
    def scrape_info(self, values):
        self.current_items = values[0]
        self.current_tags = values[1]

    #Show user and log Scrape numbers
    @property
    def log_scrape_info(self):
        self.logger.info(f"Total Items Grabbed: {self.current_items}")
        self.logger.info(f"Number of Tags grabbed: {self.current_tags}")
        self.logger.info(f"Number of Thumbnail Tags grabbed: {len(self.thmb_tags)}\n")

    #Loop for Thumbnail processing
    @property
    def thmb_processing(self):
        self.log_scrape_info

        if self.thmb_tags:
            self.get_full_res_page()

        if self.thmb_links:
            self.get_full_res_file()

        if self.full_links:
            self.get_final_link(self.full_links)
    #endregion