from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
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


def id_to_name(player_id):
    soup = BeautifulSoup(requests.get(f'https://sports.yahoo.com/nfl/players/{player_id}/').text, 'html.parser')
    return soup.find('span', class_='ys-name').text


def get_players_from_page(driver):
    players = []
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    anchors = soup.find_all('a', href=True)
    for anchor in anchors:
        if 'https://sports.yahoo.com/nfl/players/' in anchor['href'] and 'news' not in anchor['href']:
            players.append(anchor['href'].split('/')[-1])
    return players


class Trade:
    def __init__(self, url, driver):
        self.url = url
        self.league_id = self.url.split('/')[-3]
        self.driver = driver

    def is_active(self):
        self.driver.get(self.url)
        # test if page is loaded: evaluate btn exists in sent and received trades
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.LINK_TEXT, 'Evaluate Trade'))
            )
            return True
        except TimeoutException:
            return False

    def get_players(self):
        my_players = []
        other_players = []
        if self.is_active():
            all_players = get_players_from_page(self.driver)
            self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/3')
            my_team = get_players_from_page(self.driver)
            for player in all_players:
                if player in my_team:
                    my_players.append(player)
                else:
                    other_players.append(player)
        return my_players, other_players

    def was_received(self):
        if self.is_active():
            try:
                reject_btn = self.driver.find_element_by_link_text('Reject Trade')
                return True
            except NoSuchElementException:
                return False

    def cancel(self):
        if self.is_active():
            if self.was_received():
                cancel_btn = self.driver.find_element_by_link_text('Reject Trade')
            else:
                cancel_btn = self.driver.find_element_by_link_text('Cancel Trade')
            cancel_btn.click()


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

    def get_trades(self):
        trades = []
        i = 1
        while True:
            if self.driver.current_url != f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/3':
                self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/3')
            try:
                team_notes = WebDriverWait(self.driver, 3).until(
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
                trades.append(Trade(self.driver.current_url, self.driver))
                i += 1
            except TimeoutException:
                i += 1
                continue
        return trades

    def cancel_trades(self, target_players=None, log=False):
        """
        Cancels some or all active trades.

        :param target_players: List of player IDs. Any trade with only these players will be canceled.
        If not specified, cancels all trades.
        :param method: Specify whether to cancel sent trades, reject received trades, or both.
        :param message: A message to send upon rejecting a trade. Applies only to trades received; not to those sent.
        :param log: Specify whether to print cancelled trades to the console or not.
        """

        for trade in self.get_trades():
            my_players, other_players = trade.get_players()
            if target_players is None or sorted(target_players) == sorted(my_players + other_players):
                if log:
                    log_str = f'{", ".join([id_to_name(player) for player in my_players])} for '
                    log_str += f'{", ".join([id_to_name(player) for player in other_players])}'
                    print(log_str)
                trade.cancel()

    def permacancel(self, interval, method=None):
        """
        Runs cancel_trades within a while loop.

        :param interval: The number of seconds between cancels.
        :param method: Specify whether to cancel sent trades, reject received trades, or both.
        """
        i = 0
        while True:
            i += 1
            self.cancel_trades(log=True)
            time.sleep(interval)

    def submit_trade(self, other_team, players, message=''):
        """
        Submits a trade.
        
        :param other_team: ID of the team to trade with.
        :param players: List of players to trade (on both teams; order doesn't matter)
        :param message: Custom message to send along with the trade.
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
        :param interval: The number of seconds to wait between sending (and cancelling) trades.
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

    def shutdown(self):
        self.driver.quit()
