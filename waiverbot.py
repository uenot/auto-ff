from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from datetime import datetime
from ffbot import FFBot
from ffbot_globals import *


def detect_waiver(driver):
    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.ID, 'viewwaiver-submit-container'))
        )
        return True
    except TimeoutException:
        return False


class Waiver:

    def __init__(self, url, driver):
        self.url = url
        self.driver = driver

    def is_active(self):
        self.driver.get(self.url)
        return detect_waiver(self.driver)

    def get_info(self):
        if self.is_active():
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            self.bid = soup.find('input', id='faab-bid-amount')['value']

            process_time = soup.find('fieldset', id='faab-bid-fieldset').contents[5].contents[3].text
            self.process_time = datetime.strptime(process_time, '%b %d')

            self.players = list(set(get_players_from_page(self.driver)))
            # search for players on my team; separate
            # move from Trade to globals

    def cancel(self):
        if self.is_active():
            cancel_btn = self.driver.find_element_by_xpath('//*[@id="viewwaiver-submit-container"]/input[2]')
            cancel_btn.click()


class WaiverBot(FFBot):

    def get_waivers(self):
        waivers = self.get_transactions(detect_waiver)
        return [Waiver(waiver, self.driver) for waiver in waivers]

    def create_waiver(self, player_to_add, player_to_drop, bid=0):
        # TODO: make player_to_drop optional
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/addplayer?apid={player_to_add}')
        player_drop_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, f'//*[@id="checkbox-{player_to_drop}"]/preceding-sibling::button')
            )
        )
        player_drop_btn.click()
        bid_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'faab-bid-amount'))
        )
        bid_field.send_keys(Keys.DELETE)
        bid_field.send_keys(bid)
        submit_waiver_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'submit-add-drop-button'))
        )
        submit_waiver_btn.click()




    def check_other_claims(self):
        # check if waivers can be cancelled (not possible if invalid player in IR)
        # get info from all waivers
        # save that info (preferably to a temp file)
        # cancel all waivers
        # wait until 12:00AM on waiver processing day (for any player in the list)
        # check if they are a free agent or are still on waivers
        # if free agent: pick up, dropping original player
        # if waiver: resubmit original claim
        pass
