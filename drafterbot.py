# TODO: allow for choice to save files or not
# TODO: create function just to save files (to prepare)
# TODO: make functions (ex: get_df()) that get file if exists, else create
# TODO: allow for better ranking choice
# TODO: allow for built-in yahoo rankings


import pandas as pd
from yahoo_oauth import OAuth2
import json
import requests
import yahoo_fantasy_api as yfa
import objectpath
import numpy as np
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import time
from datetime import datetime
import os

# override this method to show stat_id
def new_stat_categories(self):
    """Return the stat categories for a league
    :returns: Each dict entry will have the stat name along
        with the position type ('B' for batter or 'P' for pitcher).
    :rtype: list(dict)
    >>> lg.stat_categories('370.l.56877')
    [{'display_name': 'R', 'position_type': 'B'}, {'display_name': 'HR',
    'position_type': 'B'}, {'display_name': 'W', 'position_type': 'P'}]
    """
    if self.stat_categories_cache is None:
        t = objectpath.Tree(self.yhandler.get_settings_raw(self.league_id))
        json = t.execute('$..stat_categories..stat')
        simple_stat = []
        for s in json:
            # Omit stats that are only for display purposes
            if 'is_only_display_stat' not in s:
                simple_stat.append({"stat_id": s["stat_id"],
                                    "display_name": s["display_name"],
                                    "position_type": s["position_type"]})
        self.stat_categories_cache = simple_stat
    return self.stat_categories_cache


yfa.league.League.stat_categories = new_stat_categories

CONSUMER_KEY = ''
CONSUMER_SECRET = ''
current_year = datetime.today().year


def create_creds(key, secret):
    creds = {'consumer_key': CONSUMER_KEY, 'consumer_secret': CONSUMER_SECRET}
    with open('yahoo_creds.json', 'w') as f:
        json.dump(creds, f, indent=4)


def create_oauth(key, secret, use_file=False):
    if use_file:
        try:
            return OAuth2(None, None, from_file='yahoo_creds.json')
        except FileNotFoundError:
            creds = {'consumer_key': key, 'consumer_secret': secret}
            with open('yahoo_creds.json', 'w') as f:
                json.dump(creds, f, indent=4)
    return OAuth2(key, secret)


def get_league(oauth, n=0):
    game = yfa.game.Game(oauth, 'nfl')
    league_ids = game.league_ids(year=current_year)
    try:
        league = yfa.league.League(oauth, league_ids[n])
    except IndexError:
        return None
    return league


def create_player_lists(league, save=True):

    qbs = [(player['player_id'], player['name']) for player in league.free_agents('QB')]
    rbs = [(player['player_id'], player['name']) for player in league.free_agents('RB')]
    wrs = [(player['player_id'], player['name']) for player in league.free_agents('WR')]
    tes = [(player['player_id'], player['name']) for player in league.free_agents('TE')]
    ks = [(player['player_id'], player['name']) for player in league.free_agents('K')]
    defs = [(player['player_id'], player['name']) for player in league.free_agents('DEF')]

    if save:
        with open('player-lists/qbs.json', 'w') as f:
            json.dump(qbs, f, indent=4)

        with open('player-lists/rbs.json', 'w') as f:
            json.dump(rbs, f, indent=4)

        with open('player-lists/wrs.json', 'w') as f:
            json.dump(wrs, f, indent=4)

        with open('player-lists/tes.json', 'w') as f:
            json.dump(tes, f, indent=4)

        with open('player-lists/ks.json', 'w') as f:
            json.dump(ks, f, indent=4)

        with open('player-lists/defs.json', 'w') as f:
            json.dump(defs, f, indent=4)
            
    return qbs, rbs, wrs, tes, ks, defs


def load_player_lists():
    with open('player-lists/qbs.json', 'r') as f:
        qbs = json.load(f)

    with open('player-lists/rbs.json', 'r') as f:
        rbs = json.load(f)

    with open('player-lists/wrs.json', 'r') as f:
        wrs = json.load(f)

    with open('player-lists/tes.json', 'r') as f:
        tes = json.load(f)

    with open('player-lists/ks.json', 'r') as f:
        ks = json.load(f)

    with open('player-lists/defs.json', 'r') as f:
        defs = json.load(f)
        
    return qbs, rbs, wrs, tes, ks, defs


# missing point calcs for kickers + defenses
def create_df(league, load_players=True, save=True, get_projs=True):
    
    data = {}

    # flattens tuple output from load_player_lists, takes only the player id
    print('Loading players...')
    if load_players:
        player_ids = [player[0] for position in load_player_lists() for player in position]
    else:
        player_ids = [player[0] for position in create_player_lists(league, save=False) for player in position]
    
    print('Getting player data...')
    season_data = league.player_stats(player_ids, 'season', season=current_year-1)
    for player_data in season_data:
        data[player_data['player_id']] = player_data

    df = pd.DataFrame.from_dict(data, orient='index')

    print('Updating stats...')
    df.rename_axis('Player ID', inplace=True)
    del df['player_id']

    # find primary position of players
    def find_position(player_ids):
        player_info = league.player_details(player_ids)
        return [player['primary_position'] for player in player_info]

    df['position'] = find_position(list(df.index.to_numpy()))
    del df['position_type']
    
    df.fillna(value=0, inplace=True)

    # calculate fantasy_points
    df['Fantasy Pts'] = 0

    stats_to_ids = {stat['display_name']: stat['stat_id'] for stat in league.stat_categories()}

    stat_mods_list = league.settings()['stat_modifiers']['stats']
    ids_to_mods = {stat['stat']['stat_id']: float(stat['stat']['value']) for stat in stat_mods_list}
    
    stat_mods = {name: ids_to_mods[stat_id] for name, stat_id in stats_to_ids.items()}

    for label, content in df.iteritems():
        try:
            df['Fantasy Pts'] += content * stat_mods[label]
        except KeyError:
            pass

    df.sort_values(by=['Fantasy Pts'], ascending=False, inplace=True)
    
    # scrape 2020 projections
    
    if get_projs:
    
        print('Getting 2020 projections...')
        
        
        driver = webdriver.Chrome('/Users/School/Desktop/repos/auto-ff/chromedriver', service_log_path='/dev/null')

        proj_2020_link = f'https://football.fantasysports.yahoo.com/f1/{league.settings()["league_id"]}/players'
        proj_2020_link += '?status=ALL&pos=O&cut_type=9&stat1=S_PS_2020&myteam=1&sort=PR&sdir=1&count=0'
        driver.get(proj_2020_link)

        input('Press enter once logged in: ')

        player_projs = {}

        for i in range(0, 425, 25):
            for row_num in range(1, 26):
                row_xpath = f'/html/body/div[1]/div[2]/div[2]/div[2]/div/div/div[2]/div[2]/section/div/div/div[3]/' \
                            f'section[2]/div/div/div[2]/table/tbody/tr[{row_num}]/'
                name_xpath = row_xpath + 'td[2]/div/div[1]/div/a'
                anchor = driver.find_element_by_xpath(name_xpath)
                player_id = anchor.get_attribute('href').split('/')[-1]

                # get projection
                # using soup doesnt work for some reason— not all trs are fully loaded???
                proj_path = row_xpath + 'td[7]/div/span'
                proj = driver.find_element_by_xpath(proj_path)
                player_projs[int(player_id)] = float(proj.text)

            next_page_button = driver.find_element_by_link_text('Next 25')
            next_page_button.click()
            time.sleep(3)
            
        proj_column = []
            
        for player_id in df.index:
            pts = player_projs.get(player_id, 0)
            proj_column.append(pts)
        df['2020 Projections'] = proj_column

        df.sort_values(by=['2020 Projections'], ascending=False, inplace=True)

    if save:
        df.to_csv('player-data/raw_player_data.csv')
    
    return df

def load_df(adjust=True):
    df = pd.read_csv('player-data/raw_player_data.csv')
    # set index to player name
    df.rename(columns={'Unnamed: 0': 'Player ID'}, inplace=True)
    df.set_index('Player ID', inplace=True)
    if adjust:
        # wrs

        # dadams
        df.at[27581, '2020 Projections'] = 235
        # odell
        df.at[27540, '2020 Projections'] = 201
        #amari
        df.at[28392, '2020 Projections'] = 215
        # chark
        df.at[31031, '2020 Projections'] = 207
        # juju
        df.at[30175, '2020 Projections'] = 196
        # sutton
        df.at[31010, '2020 Projections'] = 205
        # deebo
        df.at[31868, '2020 Projections'] = 195
        # julio
        df.at[24793, '2020 Projections'] = 230
        # dj moore
        df.at[30994, '2020 Projections'] = 209
        # parker
        df.at[28402, '2020 Projections'] = 206
        # terry
        df.at[31908, '2020 Projections'] = 200
        # ajb
        df.at[31883, '2020 Projections'] = 211
        # thielen
        df.at[27277, '2020 Projections'] = 208
        # gallup
        df.at[31051, '2020 Projections'] = 195
        # landry
        df.at[27591, '2020 Projections'] = 175
        # boyd
        df.at[29288, '2020 Projections'] = 192
        # ty
        df.at[25802, '2020 Projections'] = 203
        # ajg
        df.at[24791, '2020 Projections'] = 174
        # jerry jeudy
        df.at[32685, '2020 Projections'] = 157
        # jalen reagor
        df.at[32691, '2020 Projections'] = 155
        # brandon aiyuk
        df.at[32695, '2020 Projections'] = 150
        # diontae
        df.at[31898, '2020 Projections'] = 183
        # anthony miller
        df.at[31021, '2020 Projections'] = 140
        # crowder
        df.at[28493, '2020 Projections'] = 156
        # ridley
        df.at[30996, '2020 Projections'] = 205.6
        # lockett
        df.at[28457, '2020 Projections'] = 206
        # mjj
        df.at[25876, '2020 Projections'] = 158

        # rbs

        # zeke
        df.at[29238, '2020 Projections'] = 275.00
        #aaron jones
        df.at[30295, '2020 Projections'] = 230
        # clyde edwards
        df.at[32702, '2020 Projections'] = 210.00
        # johnathan taylor
        df.at[32711, '2020 Projections'] = 183
        # singletary
        df.at[31906, '2020 Projections'] = 177
        # fournette
        df.at[30117, '2020 Projections'] = 200
        # mostert
        df.at[28654, '2020 Projections'] = 175
        # sony
        df.at[31001, '2020 Projections'] = 162.5
        # bell
        df.at[26671, '2020 Projections'] = 185
        # ingram
        df.at[24815, '2020 Projections'] = 186

        # tes

        # kittle
        df.at[30259, '2020 Projections'] = 225
        # ertz
        df.at[26658, '2020 Projections'] = 187.5
        # waller
        df.at[28592, '2020 Projections'] = 190
        # hooper
        df.at[32685, '2020 Projections'] = 130
        # gesicki
        df.at[31012, '2020 Projections'] = 152
        # ertz
        df.at[26658, '2020 Projections'] = 170

        # qbs

        # kyler
        df.at[31833, '2020 Projections'] = 355
        # josh allen
        df.at[29236, '2020 Projections'] = 325
        # tannehil
        df.at[25718, '2020 Projections'] = 300

        df.sort_values(by=['2020 Projections'], ascending=False, inplace=True)
    return df


class Roster:
    
    def __init__(self, league, positions=None):
        self.all_players = load_df()
        self.roster = pd.DataFrame(columns=self.all_players.columns)
        
        if positions is None:
            self.max_positions = {pos: info['count'] for pos, info in league.positions().items()}
            rb_wr_bench_split = int(self.max_positions['BN'] / 2)
            self.max_positions['BN/WR'] = rb_wr_bench_split
            self.max_positions['BN/RB'] = self.max_positions['BN'] - rb_wr_bench_split
            del self.max_positions['BN']
            del self.max_positions['IR']
        else:
            self.max_positions = positions
        
        self.positions = {pos: 0 for pos in self.max_positions.keys()}
        
        self.round = 1
        
    def get_position(self, player_id):
        if player_id in self.roster.index:
            return self.roster.at[player_id, 'position']
        else:
            return self.all_players.at[player_id, 'position']
        
    def positions_open(self, player_id):
        
        pos = self.get_position(player_id)
        
        if pos == 'QB':
            if self.positions['QB'] < self.max_positions['QB']:
                return True
        elif pos == 'RB':
            if self.positions['RB'] < self.max_positions['RB'] or self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return True
            elif self.positions['BN/RB'] < self.max_positions['BN/RB']:
                return True
        elif pos == 'WR':
            if self.positions['WR'] < self.max_positions['WR'] or self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return True
            elif self.positions['BN/WR'] < self.max_positions['BN/WR']:
                return True
        elif pos == 'TE':
            if self.positions['TE'] < self.max_positions['TE'] or self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return True
            elif self.positions['BN/WR'] < self.max_positions['BN/WR']:
                return True
        elif pos == 'K':
            if self.positions['K'] < self.max_positions['K']:
                return True
        elif pos == 'DEF':
            if self.positions['DEF'] < self.max_positions['DEF']:
                return True
        return False
        
    def fill_positions(self, player_id):
        
        pos = self.get_position(player_id)
        
        if self.positions[pos] < self.max_positions[pos]:
            self.positions[pos] += 1
        elif pos in ['WR', 'RB', 'TE'] and self.positions['W/R/T'] < self.max_positions['W/R/T']:
            self.positions['W/R/T'] += 1
        elif pos == 'RB' and self.positions['BN/RB'] < self.max_positions['BN/RB']:
            self.positions['BN/RB'] += 1
        elif pos in ['WR', 'TE'] and self.positions['BN/WR'] < self.max_positions['BN/WR']:
            self.positions['BN/WR'] += 1
        else: # if there are no slots for player
            return False
        return True
    
    def is_full(self):
        for pos, count in self.positions.items():
            if count < self.max_positions[pos]:
                return False
        return True
    
    def draft(self, player_id):
        player = self.all_players.loc[player_id]
        player_name = player['name']
        print(f"Drafted {player_name}.")
        if self.fill_positions(player_id):
            self.roster = self.roster.append(player) #check this
            self.all_players.drop(player_id, inplace=True)
            return True
        print('No space for player.')
        return False
              
    def remove_player(self, player_id):
        self.all_players.drop(player_id, inplace=True)
              
    def add_to_roster(self, player_id):
        if self.fill_positions(player_id):
            row = self.all_players.loc[player_id]
            self.roster = self.roster.append(row)
            self.remove_player(player_id)
            self.round += 1
            return True
        return False
              
    def remove_best(self):
        self.all_players.drop(self.all_players.iloc[0].name, inplace=True)
    
    def static_position_mod(self, player_id):
        pos = self.get_position(player_id)
        if pos == 'QB':
            return 0.05
        elif pos == 'RB':
            return 1
        elif pos == 'WR':
            return 1
        elif pos == 'TE':
            return 1
        elif pos == 'K':
            return 0.05
        elif pos == 'DEF':
            return 0.05
              
    def dynamic_position_mod(self, player_id):
        pos = self.get_position(player_id)
        
        if pos == 'RB':
            # best available until rb slots filled
            if self.positions['RB'] < self.max_positions['RB']:
                return 1
            elif self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return 0.9
            elif self.positions['BN/RB'] < self.max_positions['BN/RB']:
                if self.positions['BN/RB'] <= 2:
                    return 0.125
                return 0.1
            else:
                return 0
        elif pos == 'WR':
            if self.positions['WR'] < self.max_positions['WR']:
                return 0.925
            elif self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return 0 # fill flex w/ rb
            elif self.positions['BN/WR'] < self.max_positions['BN/WR']:
                return 0.1
            else:
                return 0
        elif pos == 'TE':
            if self.positions['TE'] < self.max_positions['TE']:
                return 1
            elif self.positions['W/R/T'] < self.max_positions['W/R/T']:
                return 0.9
            elif self.positions['BN/WR'] < self.max_positions['BN/WR']:
                return 0.05
            else:
                return 0
        elif pos == 'QB':
            if self.positions['QB'] < self.max_positions['QB']:
                return 1
            else:
                return 0
        elif pos == 'K' or pos == 'DEF':
            for slot in ['QB', 'RB', 'WR', 'TE', 'W/R/T', 'BN/RB', 'BN/WR']:
                if self.positions[slot] < self.max_positions[slot]:
                    return 0
            return 1
        else:
            return 1
        
    def te_hack_mod(self):
        if 26686 in self.roster.index and self.round == 3:
            self.all_players.at[30259, 'Value'] = 100000
            
    def set_value(self):
              
        self.all_players['Value'] = self.all_players['2020 Projections']
        
        self.all_players['Value'] *= self.all_players.index.map(self.static_position_mod)
        self.all_players['Value'] *= self.all_players.index.map(self.dynamic_position_mod)
        
        self.te_hack_mod()
        
        self.all_players.sort_values(by='Value', ascending=False, inplace=True)
    
    def get_best_player(self, n=0):
        self.set_value()
        
        # returns index
        return self.all_players.iloc[n].name
              
    def get_ids(self):
        self.set_value()
              
        # returns list of indexes
        return self.all_players.index.tolist()
    
    def autodraft(self):
        player = self.get_best_player()
        i = 1
        while not self.draft(player):
            player = self.get_best_player(i)
            i += 1
        return player


def draft_team(league, mock=False):
    driver = webdriver.Chrome(os.path.join(os.getcwd(), 'chromedriver'))
    base_url = f'https://football.fantasysports.yahoo.com/f1/{league.settings()["league_id"]}/'
    if mock:
        base_url += 'mock_lobby'
    driver.get(base_url)
    
    try:
        confirm_recovery = driver.find_element_by_xpath('//*[@id="login-body"]/div[2]/div[1]/div[4]/form/div[2]/button')
        confirm_recovery.click()
    except NoSuchElementException:
        pass

    if mock:
        input('Press enter once you have logged in: ')

        time.sleep(2)

        draft_selected = False
        while not draft_selected:
            try:
                # hardcoded to 8team mocks
                mockdraft_start = driver.find_element_by_link_text('8 Team')
                mockdraft_start.click()
                draft_selected = True
            except StaleElementReferenceException:
                time.sleep(3)
            except NoSuchElementException:
                input('join a draft and press enter')
                draft_selected = True
    else:
        input('Press enter once you have logged in and entered the draft (in the rightmost tab): ')

    time.sleep(1)

    driver.switch_to.window(driver.window_handles[-1])

    draft_started = False
    while not draft_started:
        try:
            draft_started_detector = driver.find_element_by_class_name('ys-player')
            draft_started = True
        except NoSuchElementException:
            time.sleep(10)

    print('Draft started.')

    time.sleep(3)

    try:
        overlay_exit_btn = driver.find_element_by_class_name('Close')
        overlay_exit_btn.click()
    except NoSuchElementException:
        pass

    time.sleep(2)

    roster = Roster(league)
    
    # add keepers here

    while not roster.is_full():

        my_turn = False
        while not my_turn:
            turn_indicator = driver.find_element_by_id('draft-now').text
            if turn_indicator == "It's your turn to draft!":
                print('Your turn.')
                my_turn = True

            time.sleep(3)

        for player_id in roster.get_ids():
            try:
                player = driver.find_element_by_css_selector(f'tr[data-id="{player_id}"]')
                if roster.positions_open(player_id):
                    print(roster.positions)
                    print(roster.max_positions)
                    roster.add_to_roster(player_id)
                    break
            except NoSuchElementException:
                roster.remove_player(player_id)

        player.click()

        time.sleep(2)

        draft_button = driver.find_element_by_css_selector('.Btn.ys-can-draft.ys-draft-player')
        draft_button.click()

        time.sleep(5)

    print('Draft complete.')


def main():
    oauth = create_oauth(CONSUMER_KEY, CONSUMER_SECRET)
    found_league = False
    league_index = 0
    while not found_league:
        league = get_league(oauth, league_index)
        if league is None:
            league_index = 0
            continue
        print(f'Selected league: {league.settings()["name"]}')
        confirm_league = input('Type "next" to select another league, or anything else to continue: ')
        if confirm_league != 'next':
            found_league = True
        league_index += 1
    create_df(league)
    draft_team(league, mock=True)


if __name__ == '__main__':
    main()

