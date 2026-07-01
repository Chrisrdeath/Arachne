import logging
import os
import re
import requests
import random
import time
import warnings

class Header():

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

    def __init__(self, url, user_agent=None, referer=None):
        self.user_agent = self.generate_ua("Firefox")
        self.referer = self.generate_ref(url)
