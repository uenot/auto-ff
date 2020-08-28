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


def id_to_name(player_id):
    """
    Finds a player's name given their Yahoo ID number.

    :param player_id: A player ID number.
    :return: The player's name.
    """
    soup = BeautifulSoup(requests.get(f'https://sports.yahoo.com/nfl/players/{player_id}/').text, 'html.parser')
    return soup.find('span', class_='ys-name').text


def get_players_from_page(driver):
    """
    Gets all players on the current driver page. Used for viewing the players on a team or in a trade.

    :param driver: A selenium webdriver object. Players will be fetched from the driver's active page.
    :return: A list of player IDs.
    """
    players = []
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    anchors = soup.find_all('a', href=True)
    for anchor in anchors:
        if 'https://sports.yahoo.com/nfl/players/' in anchor['href'] and 'news' not in anchor['href']:
            players.append(anchor['href'].split('/')[-1])
    return players


class Trade:
    """
    Represents a trade. Contains methods to fetch info about the trade and interact with the trade.
    """

    def __init__(self, url, team_id, driver):
        """
        Constructor for a Trade object.

        :param url: The URL for the trade.
        :param team_id: Your team ID.
        :param driver: A selenium webdriver object. All methods require a session that is logged into Yahoo.
        """
        self.url = url
        self.league_id = self.url.split('/')[-3]
        self.team_id = str(team_id)
        self.driver = driver

    def is_active(self):
        """
        Tests if the trade stil exists. Also navigates to the trade's URL.

        :return: True if the trade exists, False otherwise.
        """
        self.driver.get(self.url)
        # evaluate button exists in sent and received trades
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.LINK_TEXT, 'Evaluate Trade'))
            )
            return True
        except TimeoutException:
            return False

    def get_players_by_team(self):
        """
        Gets the players involved in the trade. Separates them by team.

        :return: Two lists containing each team's players involved in the trade. If trade is not active, will return
            empty lists.
        """
        my_players = []
        other_players = []
        if self.is_active():
            all_players = get_players_from_page(self.driver)
            self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}')
            my_team = get_players_from_page(self.driver)
            for player in all_players:
                if player in my_team:
                    my_players.append(player)
                else:
                    other_players.append(player)
        return my_players, other_players

    def get_players(self):
        """
        Gets the players involved in the trade.

        :return: One list containing all players involved in the trade. If trade is not active, will return an empty
            list.
        """
        my_players, other_players = self.get_players_by_team()
        return my_players + other_players

    def get_teams(self):
        """
        Gets the teams involved in the trade.

        :return: A list of the IDs of each team involved in the trade. If trade is not active, will return an empty
            list.
        """
        players = []
        if self.is_active():
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            anchors = soup.find_all('a', href=True)
            for anchor in anchors:
                anchor_test_list = anchor['href'].split('/')
                if anchor_test_list[:-1] == ['', 'f1', self.league_id] and anchor_test_list[-1].isnumeric():
                    players.append(anchor['href'].split('/')[-1])
        return list(set(players))

    def get_other_team(self):
        """
        Gets the other team in the trade.

        :return: The team ID in the trade that does not match your team ID (given in constructor). If trade is not
            active, returns None.
        """
        teams = self.get_teams()
        for team in teams:
            if team != self.team_id:
                return team
        return None

    def get_message(self):
        """
        Gets the note accompanying the trade.

        :return: A string containing the message sent with the trade. If no message was sent or the trade is not active,
            returns an empty string.
        """
        if self.is_active():
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            message = soup.find('div', class_='tradenote')
            if message is None:
                message = ''
            else:
                message = message.find('p').text
            return message
        return ''

    def was_received(self):
        """
        Checks if the trade was received or sent.

        :return: True if the trade was received, False if the trade was sent or if the trade is not active.
        """
        if self.is_active():
            try:
                self.driver.find_element_by_link_text('Reject Trade')
                return True
            except NoSuchElementException:
                return False
        return False

    def cancel(self):
        """
        Cancels the trade.
        """
        if self.is_active():
            if self.was_received():
                cancel_btn = self.driver.find_element_by_link_text('Reject Trade')
            else:
                cancel_btn = self.driver.find_element_by_link_text('Cancel Trade')
            cancel_btn.click()


class TraderBot:
    """
    Contains bindings for trade actions.
    """

    def __init__(self, league_id, team_id, headless=False):
        """
        Constructor for TraderBot. Also sets up the driver by allowing the user to log into Yahoo.

        :param league_id: Your league ID.
        :param team_id: Your team ID.
        :param headless: Runs headless if True.
        """
        # initialize options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--window-size=1920x1080')
            chrome_options.add_argument('--remote-debugging-port=9222')
        # initialize driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.league_id = league_id
        self.team_id = team_id
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}')

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

            # will sometimes ask if you want to link FB Messenger on startup
            try:
                skip_messenger = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="fb-messenger-linking"]/form[2]/div/a'))
                )
                skip_messenger.click()
            except TimeoutException:
                pass
        else:
            # if not headless, should login through window
            input('confirm login')

    def get_trades(self):
        """
        Gets all active trades.

        :return: A list of Trade objects.
        """
        trades = []
        i = 1
        home_url = f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}'
        self.driver.get(home_url)
        while True:
            if self.driver.current_url != home_url:
                self.driver.get(home_url)
            try:
                team_notes = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, f'//*[@id="teamnotes"]/div/div[{i}]'))
                )
            except TimeoutException:
                # occurs if there are no more team notes
                # could also happen if page doesn't load: unlikely but possible
                break

            team_notes.click()

            # test if teamnote is a trade through evaluate trade button
            try:
                WebDriverWait(self.driver, 4).until(
                    EC.presence_of_element_located((By.LINK_TEXT, 'Evaluate Trade'))
                )
                trades.append(Trade(self.driver.current_url, self.team_id, self.driver))
                i += 1
            except TimeoutException:
                i += 1
                continue
        return trades

    def team_id_to_name(self, team_id):
        """
        Finds a team name given their team ID number.

        :param team_id: A team ID number.
        :return: A string containing the team's name.
        """
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{team_id}')

        team_name = self.driver.find_element_by_xpath('//*[@id="team-card-info"]/div[2]/ul/li/a')
        team_name = ' '.join(team_name.text.strip().split()[:-2])

        return team_name

    def permacancel(self, interval, method=None):
        """
        Cancels all trades repeatedly.

        :param interval: The number of seconds between cancels.
        :param method: Specify whether to cancel sent trades ('Cancel'), reject received trades ('Reject'), or both
            (default).
        """
        i = 0
        while True:
            i += 1
            for trade in self.get_trades():
                received = trade.was_received()
                if method is None or (method == 'Reject' and received) or (method == 'Cancel' and not received):
                    trade.cancel()
            time.sleep(interval)

    def fill_and_submit_trade(self, players, message):
        """
        Selects the players and sends a trade. To be called in other methods. Assumes the current page is the
        "select players" page.

        :param players: A list of players to add to the trade. Team doesn't matter.
        :param message: A string containing a message to send along with the trade.
        :return: The sent trade, as a Trade object. None if the trade can't be found after sending (could happen if
            it is immediately rejected).
        """
        # explicit wait for continue btn: consistent element across all trade pages, also used later
        # located here in order to test for page load
        try:
            continue_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.LINK_TEXT, 'Continue'))
            )
        except TimeoutException:
            return False

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

        # find the sent trade and return it
        possible_trades = []
        for trade in self.get_trades():
            if not trade.was_received():
                if sorted(trade.get_players()) == sorted(players):
                    possible_trades.append(trade)

        possible_trades.sort(key=lambda x: int(x.url.split('=')[-1]), reverse=True)
        try:
            return possible_trades[0]
        except IndexError:
            return None

    def create_trade(self, other_team, players, message=''):
        """
        Submits a trade.
        
        :param other_team: ID of the team to trade with.
        :param players: List of players to trade (on both teams; order doesn't matter)
        :param message: Custom message to send along with the trade.
        :return: The created trade (or None if the trade is immediately rejected).
        """
        # navigate to page of target team, start trade creation
        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{other_team}')
        create_trade_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, 'Create Trade'))
        )
        create_trade_button.click()

        return self.fill_and_submit_trade(players=players, message=message)

    def counter_trade(self, trade, players, message=''):
        """
        Counters a trade

        :param trade: The Trade to counter.
        :param players: List of players to trade (on both teams; order doesn't matter)
        :param message: Custom message to send along with the trade.
        :return: The new trade (or None if the trade is immediately rejected).
        """
        if trade.is_active() and trade.was_received():
            counter_trade_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.LINK_TEXT, 'Make Counter Offer'))
            )
            counter_trade_button.click()

            return self.fill_and_submit_trade(players=players, message=message)
        return None

    def run_hangman(self, log=True):
        """
        Runs the Hangman game through trade counters for each player. Same as run_game but specific to the Hangman game.

        :param log: If True, prints game updates to the console.
        """

        with open('junktrades/trades_to_send.json') as f:
            trades_to_send = json.load(f)

        games = {team: Hangman() for team in trades_to_send.keys()}

        interval = 300
        counter = 0

        while True:
            for trade in self.get_trades():
                if trade.was_received():
                    other_team = trade.get_other_team()
                    current_game = games[other_team]
                    response = trade.get_message()
                    prompt = current_game.action(response)
                    self.counter_trade(trade, trades_to_send[other_team], message=prompt)
                    if log:
                        print(f'{self.team_id_to_name(other_team)}: {current_game.log()})')
                    interval = 0
                    counter = 0
            time.sleep(interval)
            if counter >= 15:
                interval = 10
            elif counter >= 60:
                interval = 60
            else:
                interval = 300
            counter += 1

    def run_game(self, game, log=True):
        """
        Runs a given game by reading and responding to trade notes and countering trades.

        :param game: An extension of the Game abstract class.
        :param log: If True, prints game updates to the console.
        """
        with open('junktrades/trades_to_send.json') as f:
            trades_to_send = json.load(f)

        games = {team: game() for team in trades_to_send.keys()}

        interval = 300
        counter = 0

        while True:
            for trade in self.get_trades():
                if trade.was_received():
                    other_team = trade.get_other_team()
                    current_game = games[other_team]
                    response = trade.get_message()
                    prompt = current_game.action(response)
                    self.counter_trade(trade, trades_to_send[other_team], message=prompt)
                    if log:
                        print(f'{self.team_id_to_name(other_team)}: {current_game.log()})')
                    interval = 0
                    counter = 0
            time.sleep(interval)
            if counter >= 15:
                interval = 10
            elif counter >= 60:
                interval = 60
            else:
                interval = 300
            counter += 1

    def generate_junk_trades(self, write=True):
        """
        Creates .json files containing junk trades for each other team (i.e. my worst player for your best player).
        Used when sending trades with messages and for identifying received trades with messages.

        :param write: If True, writes the .json files; if False, doesn't.
        :return: Two dicts containing the trades to send and the trades to receive (formatted as lists of players).
        """
        trades_to_send = {}
        trades_to_receive = {}
        i = 1
        while True:
            if i == self.team_id:
                i += 1
                continue

            self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{i}')

            # breaks after hitting the last team
            players = get_players_from_page(self.driver)
            if len(players) == 0:
                break

            # switch to projected stats for this season
            projected_stats_button = self.driver.find_element_by_id('P')
            projected_stats_button.click()
            this_season_button = self.driver.find_element_by_xpath('//*[@id="subnav_P"]/li[4]/a')
            this_season_button.click()

            # the first element takes time to switch to projected stats
            # can't be solved with explicit wait since the xpath destination exists prior to change
            time.sleep(2)

            player_list = []
            # takes advantage of the fact that get_players_from_page returns in order of appearance on page
            for j, player in enumerate(players, 1):
                # note: doesn't get kickers/defenses
                # those are in different tables (statTable1, etc.)
                proj_pt_xpath = f'//*[@id="statTable0"]/tbody/tr[{j}]/td[6]/div/span'
                try:
                    player_proj_pts = self.driver.find_element_by_xpath(proj_pt_xpath)
                except NoSuchElementException:
                    # will occur for kickers/defenses
                    break
                player_proj_pts = float(player_proj_pts.text)

                # adjust qb points down to prioritize other positions
                position_xpath = f'//*[@id="statTable0"]/tbody/tr[{j}]/td[2]/div/div/div/span'
                try:
                    player_position = self.driver.find_element_by_xpath(position_xpath)
                except NoSuchElementException:
                    # shouldn't happen since break would occur above if player doesn't exist
                    pass
                player_position = player_position.text.split(' - ')[-1]

                if player_position == 'QB':
                    player_proj_pts -= 150

                player_list.append((player, player_proj_pts))

            # get player w/ highest proj. pts
            trades_to_send[i] = [sorted(player_list, key=lambda x: -x[1])[0][0]]
            trades_to_receive[i] = [sorted(player_list, key=lambda x: x[1])[0][0]]

            i += 1

        self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}')
        my_players = get_players_from_page(self.driver)

        # gets the third to last player on the page
        # usually the last bench slot
        # will be different if team doesn't have a kicker or defense
        player_to_trade_away = my_players[-3]
        for trade in trades_to_send.values():
            trade.append(player_to_trade_away)

        # gets the first player (usually qb)
        player_to_trade_away = my_players[0]
        for trade in trades_to_receive.values():
            trade.append(player_to_trade_away)

        if write:
            self.write_junk_trades(trades_to_send, trades_to_receive)

        return trades_to_send, trades_to_receive

    def write_junk_trades(self, trades_to_send, trades_to_receive):
        """
        Writes the .json files created from generate_junk_trades. Also prints the dicts through view_junk_trades.

        :param trades_to_send: The dict of trades to send.
        :param trades_to_receive: The dict of trades to receive.
        """
        with open('junktrades/trades_to_send.json', 'w') as f:
            json.dump(trades_to_send, f, indent=4)

        with open('junktrades/trades_to_receive.json', 'w') as f:
            json.dump(trades_to_receive, f, indent=4)

        self.view_junk_trades()

    def safe_generate_junk_trades(self):
        """
        Calls generate_junk_trades multiple times with time in between to protect against significant projection
        changes. To be run continuously. Writes the .json files once finalized.
        """
        trades_to_send, trades_to_receive = None, None
        new_trades_to_send, new_trades_to_receive = self.generate_junk_trades(write=False)
        while trades_to_send != new_trades_to_send and trades_to_receive != new_trades_to_receive:
            time.sleep(21600)
            new_trades_to_send, new_trades_to_receive = self.generate_junk_trades(write=False)
        self.write_junk_trades(new_trades_to_send, new_trades_to_receive)

    def view_junk_trades(self):
        """
        Prints the current junk trades, using the player names.
        """
        print('Trades to send:')
        with open('junktrades/trades_to_send.json') as f:
            trades = json.load(f)
        for team, players, in trades.items():
            print(f'Team {team}: {[id_to_name(player) for player in players]}')
        print('\nTrades to receive:')
        with open('junktrades/trades_to_receive.json') as f:
            trades = json.load(f)
        for team, players, in trades.items():
            print(f'Team {team}: {[id_to_name(player) for player in players]}')

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
                self.create_trade(target[0], target[1], message)
            time.sleep(interval)
            for trade in self.get_trades():
                players = sorted(trade.get_players())
                for target in targets:
                    if players == sorted(target[1]):
                        trade.cancel()
                        break

    def shutdown(self):
        """
        Shuts down the driver associated with the TraderBot.
        """
        self.driver.quit()


if __name__ == '__main__':
    bot = TraderBot('your league ID here', 'your team ID here')
    bot.generate_junk_trades()
    bot.shutdown()
