import requests
from bs4 import BeautifulSoup

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