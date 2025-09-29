import logging
import os
import re
import requests
import random
import time
import warnings

from background_task import background
from bs4 import BeautifulSoup
from django.utils import timezone
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from urllib.parse import urljoin

from .models import *
from static.libs import exceptions as exc

logger = logging.getLogger('background_task')

class Validate:
    def URL(url):
        url = url.lower()

        if not url.startswith(('http://', 'https://')):
            raise exc.URLError()
      
class Scrape():
    #These are the most important connection codes for scraping
    connect_codes = {
        200: "Connected",
        403: "Forbidden",
        404: "Not Found",
        429: "To Many Requests",
        503: "Service Unavailable",
    }

    #These are for the 429 loop
    wait_time = 0
    retries = 0

    #items for the link being scraped
    link_items = []

    header = None

    def __init__(self):
        pass

    #This is helpfule to differentiate the links that come from the same site 
    def get_title(self, url):
        engines = ["Firefox", "Chrome"]
        #engine_choice = random.choice(engines)
        engine_choice = "Firefox"

        match engine_choice:
            case "Chrome":
                driver = webdriver.Chrome()
                driver.get(url)
                time.sleep(10)
            
            case "Firefox":
                user_agent = self.generate_ua(engine_choice)

                options = webdriver.FirefoxOptions()
                options.add_argument("-headless")
                options.set_preference("general.useragent.override", user_agent)
                driver = webdriver.Firefox(options=options)

                driver.get(url)
                title = driver.title
                #makes them usable as file names
                title = re.sub(r'[<>:"/\\|?*]', '', title)
                title = re.sub(r'\s+', ' ', title).strip()

                return title
    
    def set_info(self, site, link):
        self.site = site
        self.link = link

    #Creates a header and tries to scrape with requests first
    def get_items(self, url, selenium=False):
        engines = ['Chrome', 'Firefox']
        browsers = ['Chrome', 'Opera', 'Edge', 'Firefox']

        header = {
            "User-Agent": "",
            "Referer": "",
            "Accept-Encoding": "gzip, deflate, br"
        }

        header['Referer'] = self.generate_ref(url)

        if(selenium == False):
            header['User-Agent'] = self.generate_ua(random.choice(browsers))
            self.req_scrape(url, header)
        else:
            header['User-Agent'] = self.generate_ua(random.choice(engines))
            self.sel_scrape(url)

    #Request Scraping - Non JS loading
    def req_scrape(self, url, header):
        logger.info("Requests Scraper")
        self.link_items = []

        request = requests.get(url, headers=header)

        match request.status_code:
            case 200:

                soup = BeautifulSoup(request.content, 'html.parser')

                if '\uFFFD' in soup.get_text():
                    logger.info("Warning: Replacement characters detected!")
                    self.sel_scrape(url)


                for tag in soup.find_all():
                    for attr in ['href', 'src', 'url']:
                        if attr in tag.attrs:
                            self.link_items.append(tag[attr])


            #Likely scraper seen as bot
            case 403:
                self.sel_scrape(url)

            #Link doesn't exist anymore
            case 404:
                Link.objects.filter(url=url).first().delete()

            #Need to wait longer and retry in a little bit
            case 429:
                self.tmr_loop()
                self.req_scrape(self, url, header)

    #Selenium Scraping - JS loading
    def sel_scrape(self, url):
        logger.info("Selenium Scraper")
        engines = ["Firefox", "Chrome"]
        #engine_choice = random.choice(engines)
        engine_choice = "Firefox"
        driver = ""
        self.link_items = []

        match engine_choice:
            case "Chrome":
                driver = webdriver.Chrome()
                driver.get(url)
                time.sleep(10)
            
            case "Firefox":
                user_agent = self.generate_ua(engine_choice)

                options = webdriver.FirefoxOptions()
                options.add_argument("-headless")
                options.set_preference("general.useragent.override", user_agent)
                driver = webdriver.Firefox(options=options)

                driver.get(url)
                #Makes look less like a bot
                sleep = Settings.objects.get(settingName = "grab_sleep")
                if(sleep.on):
                    logger.info(sleep.addInfo)
                    time.sleep(int(sleep.addInfo))

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        for tag in soup.find_all():
            for attr in ['href', 'src', 'url']:
                if attr in tag.attrs:
                    self.link_items.append(tag[attr])
        
        #Rules
        abs_look_rules = Rules.objects.filter(type='abs', choice1="LF")
        rel_look_rules = Rules.objects.filter(type='rel', choice1="LF")

        

        for rule in abs_look_rules:
            #logger.info(rule.text)
            if(rule.choice2 == "T"):
                for tag in soup.find_all(rule.choice3):
                    logger.info(tag)
            elif(rule.choice2 == "ID"):
                for ruleClass in soup.find_all(id=rule.text):
                    logger.info(ruleClass)
            elif(rule.choice2 == "C"):
                for ruleClass in soup.find_all(class_=rule.text):
                    #for a_tag in ruleClass.find_all('a', href=True):
                    abs_link = ruleClass.get('href')

                    if not Items.objects.filter(url=abs_link).exists():
                        Items.objects.create(url=abs_link, site=self.site, type='abs', link_id=self.link.id)

                
        driver.quit()

    #Logs items to DB
    def log_items(self, link, site):

        abs_link_prefix = ("//", "https://", "http://")
        rel_link_prefix = ("../", "./", "/")
        
        #chosen formats
        pic_forms = Formats.objects.filter(type='pic', formSave=True).values_list('formName', flat=True)
        vid_forms = Formats.objects.filter(type='vid', formSave=True).values_list('formName', flat=True)

        #settings
        abs_sett = Settings.objects.get(settingName = "absolute_links")
        abs_rel_sett = Settings.objects.get(settingName = "related_links")
        rel_sett = Settings.objects.get(settingName = "relative_links")

        #rules
        pic_ignore_rules = Rules.objects.filter(type='pic', choice1="I")
        vid_ignore_rules = Rules.objects.filter(type='vid', choice1="I")
        
        try:
            for link_item in self.link_items:
                should_break = False
                format = link_item.split('.')[-1].upper().rstrip('/')

                if format in pic_forms:
                    #logger.info(link_item)

                    for rule in pic_ignore_rules:
                        if rule.choice2=="N":
                            if rule.choice3=="C":
                                if rule.text.lower() in link_item.lower():
                                    should_break = True
                                    break
                            elif rule.choice3=="EW":
                                if link_item.rstrip(f".{format.lower()}").endswith(rule.text):
                                    should_break = True
                                    break
                            elif rule.choice3=="BW":
                                if link_item.rstrip(f".{format.lower()}").beginswith(rule.text):
                                    should_break = True
                                    break

                    if should_break==True:
                        continue

                    clean_item = self.clean_links(link_item, site)

                    if not Items.objects.filter(url=clean_item).exists():
                        Items.objects.create(url=clean_item, site=site, type='pic', link_id=link.id)
                elif format in vid_forms:

                    for rule in vid_ignore_rules:
                        if rule.choice2=="N":
                            if rule.choice3=="C":
                                if rule.text.lower() in link_item.lower():
                                    should_break = True
                                    break
                            elif rule.choice3=="EW":
                                if link_item.rstrip(f".{format.lower()}").endswith(rule.text):
                                    should_break = True
                                    break
                            elif rule.choice3=="BW":
                                if link_item.rstrip(f".{format.lower()}").beginswith(rule.text):
                                    should_break = True
                                    break

                    if should_break==True:
                        continue

                    clean_item = self.clean_links(link_item, site)

                    if not Items.objects.filter(url=clean_item).exists():
                        Items.objects.create(url=clean_item, site=site, type='vid', link_id=link.id)

                elif link_item.startswith(abs_link_prefix):
                    if abs_sett.on:
                        if not abs_rel_sett.on or (abs_rel_sett.on and site in link_item):
                            #logger.info(link_item)
                            clean_item = self.clean_links(link_item, site)
                            if not Items.objects.filter(url=clean_item).exists():
                                Items.objects.create(url=clean_item, site=site, type='abs', link_id=link.id)

                elif link_item.startswith(rel_link_prefix):
                    if rel_sett.on:
                        clean_item = self.clean_links(link_item, site)

                        if not Items.objects.filter(url=clean_item).exists():
                            Items.objects.create(url=clean_item, site=site, type='rel', link_id=link.id)

        except Exception as e:
            logger.info(e)

    #This makes links useable for saving and scraping
    def clean_links(self, link, site):
        clean_link = ""
        rel_link_prefix = ("../", "./", "/")

        if link.startswith("//"):
            clean_link = f"https:{link}"
        
        elif link.startswith(rel_link_prefix):
            for prefix in rel_link_prefix:
                    if link.startswith(prefix):
                        link = link.removeprefix(prefix)
                        break
            clean_link = urljoin((f"https://{site}"), link)

        else:
            clean_link = link
            
            clean_link = urljoin(site, link)

        
        return clean_link

    #This is for 429 Codes
    def tmr_loop(self):
        print("429 Too Many Requests")
        time.sleep(15+self.wait_time)
        self.wait_time += 10

    #Generates User-Agents for headers
    def generate_ua(self, browser):
        os_list = ["Mac", "Linux", "Windows"]
        os_weights = [.18, .07, .75]

        c_mac = ["Intel Mac OS X 10_14_6", "Intel Mac OS X 10_15_7", "Intel Mac OS X 11_0_1", "Intel Mac OS X 12_3_1", "Intel Mac OS X 13_0", "Intel Mac OS X 14_4_1"]
        f_mac = ["Intel Mac OS X 10.14.6", "Intel Mac OS X 10.15.7", "Intel Mac OS X 11.0.1", "Intel Mac OS X 12.3.1", "Intel Mac OS X 13.0", "Intel Mac OS X 14.4.1"]

        chrome_version = ["138.0.7204.157", "138.0.7204.100", "138.0.7204.96"]#https://chromereleases.googleblog.com/search/label/Desktop%20Update
        fox_version = random.randrange(138, 141)#https://www.mozilla.org/en-US/firefox/releases/
        opera_version = ["120.0.5543.93", "119.0.5497.131", "118.0.5461.83"]#https://blogs.opera.com/desktop/
        edge_version = ["138.0.3351.95", "138.0.3351.83", "138.0.3351.77"]#https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel

        lin = ["x86_64", "i686", "aarch64"]

        if browser == "Firefox": curr_ver = fox_version

        ua_templates = {
            "Chrome": {
                "Mac": lambda: f"Mozilla/5.0 (Macintosh; {random.choice(c_mac)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36",
                "Linux": lambda: f"Mozilla/5.0 (X11; {random.choice(lin)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36", 
                "Windows": lambda: f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36"
            },
            
            "Firefox":{
                "Mac": lambda: f"Mozilla/5.0 (Macintosh; {random.choice(f_mac)}; rv:{curr_ver}.0) Gecko/20100101 Firefox/{curr_ver}.0",
                "Linux": lambda: f"Mozilla/5.0 (X11; {random.choice(lin)}; rv:{curr_ver}.0) Gecko/20100101 Firefox/{curr_ver}.0",
                "Windows": lambda: f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{curr_ver}.0) Gecko/20100101 Firefox/{curr_ver}.0"
  
            },

            "Opera":{
                "Mac": lambda: f"Mozilla/5.0 (Macintosh; {random.choice(c_mac)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 OPR/{random.choice(opera_version)}",
                "Linux": lambda: f"Mozilla/5.0 (X11; {random.choice(lin)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 OPR/{random.choice(opera_version)}", 
                "Windows": lambda: f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 OPR/{random.choice(opera_version)}"
            },

            "Edge":{
                "Mac": lambda: f"Mozilla/5.0 (Macintosh; {random.choice(c_mac)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 Edg/{random.choice(edge_version)}",
                "Linux": lambda: f"Mozilla/5.0 (X11; {random.choice(lin)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 Edg/{random.choice(edge_version)}", 
                "Windows": lambda: f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(chrome_version)} Safari/537.36 Edg/{random.choice(edge_version)}"
            }
        }

        curr_os = random.choices(os_list, weights=os_weights, k=1)[0]

        return ua_templates[browser][curr_os]()

    #Generates Referers for headers
    def generate_ref(self, url):
        
        "https://www.google.com/search?client=firefox-b-d&q="#%20
        "https://www.google.com/search?q="#+

        referer = [
            "https://www.google.com/",
            "https://www.yahoo.com/",
            "https://www.bing.com/",
        ]

        return random.choice(referer)

    #Save the items that are passed to the function
    def save_items(self, save_info):
        save_items = save_info['items']

        browsers = ['Chrome', 'Opera', 'Edge', 'Firefox']

        self.header = {
            "User-Agent": "",
            "Referer": save_info["prev_page"],
            "Accept-Encoding": "gzip, deflate, br"
        }

        self.header['User-Agent'] = self.generate_ua(random.choice(browsers))

        if(not os.path.exists(save_info["save_dir"])):
            os.makedirs(save_info["save_dir"])

        for item in save_items:
            file = item['url'].split('/')[-1]
            #Makes sure it can be used as a file name
            file_name = re.sub(r'[<>:"/\\|?*]', '', file)
            file_name = re.sub(r'\s+', ' ', file_name).strip()
            save_path = f"{save_info["save_dir"]}\\{file_name}"
            
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
                
            sleep = Settings.objects.get(settingName = "save_sleep")
            #logger.info(sleep.addInfo)
            if(sleep.on):
                time.sleep(int(sleep.addInfo))

            item_request = requests.get(item['url'], headers=self.header)
            sc = item_request.status_code
            #print(sc)

            match sc:
                case 200:
                    with open(save_path, 'wb') as f:
                            f.write(item_request.content)
                            logger.info("Item saved")
                      
                case 403:
                    engines = ["Firefox", "Chrome"]
                    #engine_choice = random.choice(engines)
                    engine_choice = "Firefox"

                    user_agent = self.generate_ua(engine_choice)

                    match engine_choice:
                        case "Firefox":
                            options = self.sel_save_firefox(user_agent, save_info["save_dir"])
                            driver = webdriver.Firefox(options=options)
                            driver.set_page_load_timeout(10)
                        case "Chrome":
                            options = self.sel_save_chrome(user_agent, save_info["save_dir"])
                            driver = webdriver.Chrome(options=options)
                            driver.set_page_load_timeout(15)
                    try:
                        driver.get(item['url'])
                    except TimeoutException:
                        driver.quit()

                case 429:
                    self.save_tmr_loop(item_request)
                    save_info = {'save_dir': save_info["save_dir"], 'items': item['url']}

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
        self.header['User-Agent'] = self.generate_ua(random.choice(browsers))
        #retries = 5
        #wait = 10
        #while retries>0:
            #time.sleep(10)    

#Scrapes Pages
@background
def scrape_items(url):
    logger.info(f"Scraping site {url}")
    try:
        Scraper = Scrape()
        logger.info("Scraping Started")
        
        site = url.split('/')[2]

        if 'www' in site:
            period = site.split('.')
            period = period[1:]
            site = '.'.join(period)

        url = url.rstrip('/') #+ '/'

        if not Link.objects.filter(url=url).exists():
            title = Scraper.get_title(url)
            link = Link.objects.create(url=url, site=site, title=title)
        else:
            link = Link.objects.get(url=url)

        Scraper.set_info(site, link)

        Scraper.get_items(url)

        logger.info("Site Scraped Successfully")
        logger.info("Saving Items to DB")

        Scraper.log_items(link, site)

        logger.info("Items Saved Successfully")
    
    except Exception as e:
        logger.exception(f"Task failed {e}")

#Saves Items that user selected
@background
def start_save(parent_id, ids):
    save_dir = Settings.objects.filter(settingName='save_loc').values_list("addInfo", flat=True).first()
    link = Link.objects.get(id=parent_id)
    txt = link.title
    folder = link.title
    logger.info(f"Scraping site {folder}")
    prev_page = link.url

    #Creates a directory Structure based on how pages were scraped
    while link.hasParent:
        link = link.hasParent
        folder = os.path.join(link.title, folder)

    files_save_dir = os.path.join(save_dir, folder)

    logger.info(files_save_dir)

    save_info = {
        "save_dir": files_save_dir,
        "prev_page": prev_page,
        "items": []
    }

    id_list = ids.split(',')

    for url_id in id_list:

        item_info = Items.objects.filter(id=url_id).values_list("id", "url").first()
        item = {
            "id": item_info[0],
            "url": item_info[1]
        }
        save_info["items"].append(item)

    Saver = Scrape()
    Saver.save_items(save_info)
    
    txt_save_dir = os.path.join(files_save_dir, f"{txt}.txt")

    #info for when page was scraped last
    with open(txt_save_dir, 'w') as f:
        f.write(f"{folder} last scraped at {timezone.now()}")

#delete indiviual Item or Link
def delete_items(parent_id, ids):
    split_ids = ids.split(',')
    for id in split_ids:
        Items.objects.filter(id=id, link_id=parent_id).first().delete()

def parent_link(id, p_id):
    link = Link.objects.get(id=id)
    p_link = Link.objects.get(id=p_id)
    link.hasParent = p_link
    link.save()

