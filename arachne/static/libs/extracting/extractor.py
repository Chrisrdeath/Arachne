import logging
import os
import re
import requests
import random
import time
import warnings
import multiprocessing
import psutil
import json

from background_task import background
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from django.utils import timezone
from multiprocessing import Pool
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urljoin

from istos.models import *
from static.libs.utils import exceptions as exc

from static.libs.utils.header import Header


file_label = '-EXTRACTOR'

logger = logging.LoggerAdapter(logging.getLogger('spider'), {'file': file_label})
debug_logger = logging.LoggerAdapter(logging.getLogger('spider_debug'), {'file': file_label})

JSON_MEDIA = Path(__file__).parents[2] /"json"
MAX_WORKERS = max(1, int(psutil.cpu_count(logical=False) * 0.4))

class Extractor():
    #Save the items that are passed to the function
    def __init__(self, link, save_info, index=None):
        self.PIC_FORMATS = list(Formats.objects.filter(type='pic', formSave=True).values_list('formName', flat=True))
        self.VID_FORMATS = list(Formats.objects.filter(type='vid', formSave=True).values_list('formName', flat=True))

        self.save_info = save_info

        if index:
            self.index = index
        else:
            self.index = 0

        extract_paths = os.path.join(JSON_MEDIA, f'extract-{self.index}.json')

        self.link = link
        
        self.header_obj = Header(self.link.url)

    def download_items(self, curr_job):

        if self.index:
            global logger
            file_label = f'-EXTRACTOR-{self.index}'
            logger = logging.LoggerAdapter(logging.getLogger('spider'), {'file': file_label})

        browsers = ['Chrome', 'Opera', 'Edge', 'Firefox']

        self.header = {
            "User-Agent": self.header_obj.user_agent,
            "Referer": self.save_info["prev_page"],
            "Accept-Encoding": "gzip, deflate, br"
        }

        #self.header['User-Agent'] = self.generate_ua(random.choice(browsers))
        
        if(not os.path.exists(self.save_info["save_dir"])):
            os.makedirs(self.save_info["save_dir"])

        if curr_job.currIndex is not None:
            start_index = curr_job.currIndex
        else:
            start_index = 0

        if start_index != 0:
            logger.info("Resuming Extraction")

        item_len = len(self.save_info["items"])

        for index, item in enumerate(self.save_info["items"], start=start_index):

            curr_job.refresh_from_db(fields=["status"])
            if curr_job.status == 'paused':
                #ScrapeJob.objects.filter(id=curr_job.id).update(currIndex=index)
                curr_job.currIndex = index
                curr_job.save(update_fields=["currIndex"])
                return


            file = item['url'].split('/')[-1]

            #Makes sure it can be used as a file name
            if "?" in file:
                    file = file.split('?')[0]

            file_name = re.sub(r'[<>:"/\\|?*]', '', file)
            file_name = re.sub(r'\s+', ' ', file_name).strip()
            save_path = f"{self.save_info["save_dir"]}\\{file_name}"

            save_dir_sel = f"{self.save_info["save_dir"]}"
            
            if(os.path.exists(save_path)):
                logger.info("Item Exists")
                curr_item = Items.objects.filter(id=item['id']).first()
                if(curr_item.saved == True and curr_item.dateSaved):
                    continue
                else:
                    curr_item.saved = True
                    curr_item.dateSaved = timezone.now()
                    curr_item.save()
                    continue

            if item['download_btn']:
                try:
                    user_agent = self.header_obj.generate_ua("Firefox")

                    options = webdriver.FirefoxOptions()
                    options.add_argument("-headless")
                    options.set_preference("general.useragent.override", user_agent)

                    options.set_preference("browser.download.folderList", 2)  # 2 = custom folder
                    options.set_preference("browser.download.dir", save_dir_sel)
                    options.set_preference("browser.helperApps.neverAsk.saveToDisk", 
                                        "image/png,image/jpg,video/mp4")  
                    options.set_preference("pdfjs.disabled", True)  # Avoid opening PDFs in browser

                    driver = webdriver.Firefox(options=options)

                    driver.get(item['url'])
                    time.sleep(2)
                    main_window = driver.current_window_handle

                    angular_menu = ['mat-mdc-menu-trigger', 'mat-menu-trigger']

                    wait = WebDriverWait(driver, 10)

                    for menu_class in angular_menu:
                        button = driver.find_elements(By.CLASS_NAME, menu_class)
                        if button:
                            self.safe_click(driver, main_window, button[0])
                            
                            #Menu Panel opens
                            menu_panel = wait.until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, '[id^="mat-menu-panel-"]'))
                            )

                            time.sleep(2)
                            
                            break
                        

                    download_btn = menu_panel.find_element(By.XPATH, ".//*[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')]")
                    download_btn.click()

                    download_btn.click()
                    time.sleep(10)

                    continue

                    '''
                    if len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        file_url = driver.current_url
                        item['url'] = file_url
                    else:
                        continue
                    '''

                except Exception as e:
                    logger.error(e)

                finally:
                    driver.quit()
                
            sleep = Settings.objects.get(settingName = "save_sleep")
            #logger.info(sleep.addInfo)
            #if(sleep.on):
                #time.sleep(int(sleep.addInfo))

            time.sleep(random.uniform(3, 8))

            item_request = requests.get(item['url'], headers=self.header)
            sc = item_request.status_code

            match sc:
                case 200:
                    with open(save_path, 'wb') as f:
                            f.write(item_request.content)
                            logger.info(f"Item {index+1}/{item_len} saved")
                    
                case 403:
                    engines = ["Firefox", "Chrome"]
                    #engine_choice = random.choice(engines)
                    engine_choice = "Firefox"

                    user_agent = self.header_obj.generate_ua(engine_choice)

                    match engine_choice:
                        case "Firefox":
                            options = self.sel_save_firefox(user_agent, self.save_info["save_dir"])
                            driver = webdriver.Firefox(options=options)
                            driver.set_page_load_timeout(10)
                        case "Chrome":
                            options = self.sel_save_chrome(user_agent, self.save_info["save_dir"])
                            driver = webdriver.Chrome(options=options)
                            driver.set_page_load_timeout(15)
                    try:
                        driver.get(item['url'])
                    except TimeoutException:
                        driver.quit()

                case 429:
                    self.save_tmr_loop(item_request)
                    self.save_info = {'save_dir': self.save_info["save_dir"], 'items': item['url']}

            curr_item = Items.objects.filter(id=item['id']).first()
            curr_item.saved = True
            curr_item.dateSaved = timezone.now()
            curr_item.save()

    #Saving videos with Selenium - Firefox
    def sel_save_firefox(self, ua, save_dir):
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        options.set_preference("general.useragent.override", ua)
        options.set_preference("media.play-stand-alone", False)
        options.set_preference("browser.download.folderList", 2) 
        options.set_preference("browser.download.dir", save_dir)
        options.set_preference(
            "browser.helperApps.neverAsk.saveToDisk",
            "image/jpeg,image/png,image/gif,image/webp,image/bmp,"
            "video/mp4,video/webm,video/ogg,video/quicktime,video/x-msvideo"
        )
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.download.manager.focusWhenStarting", False)
        options.set_preference("security.fileuri.strict_origin_policy", False)

        return options

    #Saving videos with Selenium - Chrome
    def sel_save_chrome(self, ua, save_dir):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument(f"user-agent={ua}")
        options.add_argument("media")

        prefs = {
            "profile.default_content_settings.popups": 0,
            "download.prompt_for_download": False,
            "download.default_directory": save_dir,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "plugins.always_open_pdf_externally": True,
            "profile.content_settings.exceptions.media_stream_camera": {"*": {"setting": 2}},
            "profile.content_settings.exceptions.media_stream_mic": {"*": {"setting": 2}},
            "profile.content_settings.exceptions.media_stream": {"*": {"setting": 2}},
            "profile.default_content_setting_values.media_stream": 2
        }

        mime_types = [
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
            "video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-msvideo"
        ]
        
        options.add_experimental_option("prefs", prefs)

        return options

    def save_tmr_loop(self, item_request):
        print("429 Too Many Requests - Saving")
        time.sleep(10)
        browsers = ['Chrome', 'Opera', 'Edge', 'Firefox']
        self.header['User-Agent'] = self.header_obj.generate_ua(random.choice(browsers))
        #retries = 5
        #wait = 10
        #while retries>0:
            #time.sleep(10)    

    def intercept_download(self, driver):
        allowed_formats = self.PIC_FORMATS + self.VID_FORMATS

        driver.execute_cdp_cmd('Network.enable', {})

        file_url = None

        def check_request(request):
            nonlocal file_url
            url = request['params']['request']['url']
            if any(url.lower().endswith(f'.{fmt.lower()}') for fmt in allowed_formats):
                file_url = url

        driver.add_cdp_listener('Network.requestWillBeSent', check_request)

        time.sleep(5)

        driver.remove_cdp_listener('Network.requestWillBeSent', check_request)
        return file_url

    def close_popups(self, driver, main_window):
        windows = driver.window_handles

        for window in windows:
            if window != main_window:
                driver.switch_to.window(window)
                driver.close()

        driver.switch_to.window(main_window)

    def safe_click(self, driver, main_window, button):
        button.click()
        time.sleep(1)
        self.close_popups(driver, main_window)
        time.sleep(1)
        button.click()

class Parallel_Extractor():
    def __init__(self, link, save_info):
        self.PIC_FORMATS = list(Formats.objects.filter(type='pic', formSave=True).values_list('formName', flat=True))
        self.VID_FORMATS = list(Formats.objects.filter(type='vid', formSave=True).values_list('formName', flat=True))

        self.link = link
        self.page_links = save_info['items']
        self.save_info = save_info

        self.header_obj = Header(self.link.url)

    def parallel_extracting(self, curr_job, max_workers=MAX_WORKERS):
        try:
            logger.info("Starting Parrallel Extracting")

            self.actual_workers = min(max_workers, len(self.page_links))
            logger.info(f"Amount of Workers: {self.actual_workers}")

            base_size = len(self.page_links) // self.actual_workers
            remainder = len(self.page_links) % self.actual_workers

            batches = []
            start_index = 0

            for i in range(self.actual_workers):
                batch_size = base_size + (1 if i < remainder else 0)
                batch = self.page_links[start_index:start_index + batch_size]
                batches.append(batch)
                start_index += batch_size

            logger.info(f"Created {len(batches)} batches with sizes: {[len(b) for b in batches]}")

            self.save_info['items'] = []

            with Pool(processes=min(self.actual_workers, len(batches))) as pool:
                indexed_batches = [(idx, batch, self.link, self.save_info, curr_job) for idx, batch in enumerate(batches)]
                results = pool.starmap(process_media_standalone, indexed_batches)

        except Exception as e:
            print(f"Parrallel Extracting Failed: {e}")

def process_media_standalone(idx, batch_data, link, save_info, curr_job):
    save_info['items'] = batch_data

    extract_paths = os.path.join(JSON_MEDIA, f'extract-{idx}.json')

    with open(extract_paths, 'w') as file:
        json.dump(save_info, file, indent=4)

    Saver = Extractor(link, save_info, idx)
    Saver.download_items(curr_job)
