from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from getpass import getpass


class TraderBot:
    def __init__(self, league_id, headless=False):
        # initialize options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--window-size=1920x1080')
            chrome_options.add_argument('--remote-debugging-port=9222')
        # initialize driver
        self.driver = webdriver.Chrome(chrome_options=chrome_options)
        self.league_id = league_id
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/3')
        if headless:
            # have to login through command prompt if headless
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login-username'))
            )
            username_field.send_keys(input('Username/Email: ') + Keys.ENTER)

            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login-passwd'))
            )
            password_field.send_keys(getpass() + Keys.ENTER)
        else:
            # if not headless, should login through window
            input('confirm login')

    def cancel_trades(self, target_players=None, message='', log=False):
        """
        Cancels some or all active trades.

        :param target_players: List of player IDs. Any trade with only these players will be canceled.
        If not specified, cancels all trades.
        :type target_players: list(str)
        :param message: A message to send upon rejecting a trade. Applies only to trades received; not to those sent.
        :type message: str
        """
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/3')
        i = 1
        while True:
            try:
                team_notes = WebDriverWait(self.driver, 4).until(
                    EC.presence_of_element_located((By.XPATH, f'//*[@id="teamnotes"]/div/div[{i}]'))
                )
            except TimeoutException:
                break
                # occurs if there are no more team notes
                # could also happen if page doesn't load: unlikely but possible

            team_notes.click()

            # test if page is loaded: evaluate btn exists in sent and received trades
            try:
                WebDriverWait(self.driver, 4).until(
                    EC.presence_of_element_located((By.LINK_TEXT, 'Evaluate Trade'))
                )
            except TimeoutException:
                continue

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # find player ids involved in trade via anchor source links
            players = []
            anchors = soup.find_all('a', href=True)
            for anchor in anchors:
                if 'https://sports.yahoo.com/nfl/players/' in anchor['href'] and 'news' not in anchor['href']:
                    players.append(anchor['href'].split('/')[-1])

            # test if found players matches specified (or no specification)
            if target_players is None or sorted(players) == sorted(target_players):
                # different text based on if trade was sent or received
                try:
                    cancel_button = self.driver.find_element_by_link_text('Cancel Trade')
                except NoSuchElementException:
                    cancel_button = self.driver.find_element_by_link_text('Reject Trade')
                    try:
                        message_box = self.driver.find_element_by_id('tradenote')
                        message_box.send_keys(message)
                    except NoSuchElementException:
                        pass
                if log:
                    print(sorted(players))
                cancel_button.click()
                # redirects to my team page after cancel automatically
            else:
                # executes javascript to simulate browser "back" button
                self.driver.execute_script('window.history.go(-1)')
                # does not increment if trade deleted: would skip a teamnote
                i += 1

    def permacancel(self, interval):
        """
        Runs cancel_trades within a while loop.

        :param interval: The number of seconds between cancels.
        """
        i = 0
        while True:
            i += 1
            self.cancel_trades(message=f'Cancellation round {i}, Time cancelled: {datetime.now()}', log=True)
            time.sleep(interval)

    def submit_trade(self, other_team, players, message=''):
        """
        Submits a trade.
        
        :param other_team: ID of the team to trade with.
        :type other_team: str
        :param players: List of players to trade (on both teams; order doesn't matter)
        :type players: list(str)
        :param message: Custom message to send along with the trade.
        :type message: str
        """
        # navigate to page of target team, start trade creation
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{other_team}')
        create_trade_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, 'Create Trade'))
        )
        create_trade_button.click()

        # explicit wait for continue btn: consistent element across all trade pages, also used later
        # located here in order to test for page load
        continue_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, 'Continue'))
        )

        # iterate through all players in list; select all for trade
        # team doesn't matter
        for player in players:
            player_checkbox = self.driver.find_element_by_id(f'checkbox-{player}')
            player_checkbox.click()

        continue_button.click()

        # send custom message
        message_box = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'tradenote'))
        )
        message_box.send_keys(message)

        # send trade
        send_trade_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, 'Send Trade Proposal'))
        )
        send_trade_button.click()

    def trade_spam(self, targets, n, interval):
        """
        Sends and cancels trades automatically over time.
        
        :param targets: List of tuples, each containing the target team ID and a list of target player IDs.
        Example: [('1', ['27581', '30259', '25802']), ('6', ['25802', '31056', '31268'])]
        :param n: The number of times to send the specified trades.
        :type n: int
        :param interval: The number of seconds to wait between sending (and cancelling) trades.
        :type n: int
        """
        for i in range(n):
            # sends custom message with number and time sent
            message = f'Trade {i + 1}/{n}, Time sent: {datetime.now()}'
            print('\r' + message, end='')
            for target in targets:
                self.submit_trade(target[0], target[1], message)
            time.sleep(interval)
            for target in targets:
                self.cancel_trades(target_players=target[1])
