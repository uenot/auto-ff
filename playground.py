import json
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup
from datetime import datetime
from getpass import getpass
import requests
from game import *

driver = webdriver.Chrome()
driver.get('https://www.google.com/search?q=translate&oq=translate&aqs=chrome..69i57j0l6.14511j0j1&sourceid=chrome&ie=UTF-8')
textarea = driver.find_element_by_id('tw-source-text-ta')

message = 'test\ntest'
textarea.send_keys(message)
