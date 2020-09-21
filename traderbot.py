import json
import time
from datetime import datetime

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ffbot import FFBot
from ffbot_globals import *


def detect_trade(driver):
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.LINK_TEXT, 'Evaluate Trade'))
        )
        return True
    except TimeoutException:
        return False


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
        # trade info attributes
        self.my_players = []
        self.other_players = []
        self.teams = []
        self.message = ''
        self.received = None

    def is_active(self):
        """
        Tests if the trade stil exists. Also navigates to the trade's URL.

        :return: True if the trade exists, False otherwise.
        """
        self.driver.get(self.url)
        return detect_trade(self.driver)

    def get_info(self):
        """

        :return:
        """
        if self.is_active():
            # check if was received or sent
            try:
                self.driver.find_element_by_link_text('Reject Trade')
                self.received = True
            except NoSuchElementException:
                self.received = False
            # get teams
            teams = []
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            anchors = soup.find_all('a', href=True)
            for anchor in anchors:
                anchor_test_list = anchor['href'].split('/')
                if anchor_test_list[:-1] == ['', 'f1', self.league_id] and anchor_test_list[-1].isnumeric():
                    teams.append(anchor['href'].split('/')[-1])
            self.teams = list(set(teams))
            # get message
            message = soup.find('div', class_='tradenote')
            if message is None:
                message = ''
            else:
                message = message.find('p').text
            self.message = message
            # get involved players
            my_players = []
            other_players = []
            all_players = get_players_from_page(self.driver)
            self.driver.get(f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}')
            my_team = get_players_from_page(self.driver)
            for player in all_players:
                if player in my_team:
                    my_players.append(player)
                else:
                    other_players.append(player)
            self.my_players = my_players
            self.other_players = other_players

    def get_other_team(self):
        """
        Gets the other team in the trade.

        :return: The team ID in the trade that does not match your team ID (given in constructor). If trade is not
            active, returns None.
        """
        for team in self.teams:
            if team != self.team_id:
                return team
        return None

    def get_players(self):
        return self.my_players + self.other_players

    def cancel(self):
        """
        Cancels the trade.
        """
        if self.is_active() and self.received is not None:
            if self.received:
                cancel_btn = self.driver.find_element_by_link_text('Reject Trade')
            else:
                cancel_btn = self.driver.find_element_by_link_text('Cancel Trade')
            cancel_btn.click()


class TraderBot(FFBot):
    """
    Contains bindings for trade actions.
    """

    def get_trades(self):
        """
        Gets all active trades.

        :return: A list of Trade objects.
        """

        trades = self.get_transactions(detect_trade)

        return [Trade(trade, self.team_id, self.driver) for trade in trades]

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
                trade.get_info()
                received = trade.received
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
            trade.get_info()
            if not trade.received:
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
        Counters a trade.

        :param trade: The Trade to counter. Must have run get_info() to ensure trade was received.
        :param players: List of players to trade (on both teams; order doesn't matter)
        :param message: Custom message to send along with the trade.
        :return: The new trade (or None if the trade is immediately rejected).
        """
        if trade.is_active() and trade.received:
            counter_trade_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.LINK_TEXT, 'Make Counter Offer'))
            )
            counter_trade_button.click()

            return self.fill_and_submit_trade(players=players, message=message)
        return None

    def run_game(self, game, log=True):
        """
        Runs a given game by reading and responding to trade notes and countering trades.

        :param game: An extension of the Game abstract class.
        :param log: If True, prints game updates to the console.
        """
        with open('junktrades/trades_to_send.json') as f:
            trades_to_send = json.load(f)

        games = {team: game() for team in trades_to_send.keys()}

        interval = 0
        counter = 0

        while True:
            log_str = 'Checking for trades...'
            current_time = datetime.now().time()
            log_str += f'\tTime: {current_time.hour}:{current_time.minute}:{current_time.second}'
            log_str += f'\tInterval: {interval}s'
            print(log_str)
            for trade in self.get_trades():
                trade.get_info()
                if trade.received:
                    other_team = trade.get_other_team()
                    current_game = games[other_team]
                    prompt = current_game.action(trade.message)
                    self.counter_trade(trade, trades_to_send[other_team], message=prompt)
                    if log:
                        print(f'{self.team_id_to_name(other_team)}: {current_game.log()}')
                    counter = 0
            time.sleep(interval)
            if counter < 5:
                interval = 5
            elif counter < 15:
                interval = 10
            elif counter < 60:
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
                    player_position = ''
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

        # gets the last player on the page
        # usually the kicker (doesn't count defenses)
        # takes last bench player (or IR) if team doesn't have a kicker
        player_to_trade_away = my_players[-1]
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


if __name__ == '__main__':
    bot = TraderBot('your league ID here', 'your team ID here')
    bot.generate_junk_trades()
    bot.shutdown()
