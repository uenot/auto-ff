from getpass import getpass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class FFBot:
    """
    Contains common Selenium bindings for the Yahoo website.
    """

    def __init__(self, league_id, team_id, headless=False):
        """
        Constructor for FFBot. Also sets up the driver by allowing the user to log into Yahoo.

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

    def get_transactions(self, verify_callback=None):
        """
        Gets all active transactions.

        :param link_text: Text contained within a link to search for on each transaction. If specified, only
            transactions where link_text is found will be returned.
        :return: A list of URLs pointing to the transactions.
        """
        transactions = []
        i = 0
        home_url = f'https://football.fantasysports.yahoo.com/f1/{self.league_id}/{self.team_id}'
        self.driver.get(home_url)
        while True:
            if self.driver.current_url != home_url:
                self.driver.get(home_url)
            i += 1
            try:
                team_notes = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, f'//*[@id="teamnotes"]/div/div[{i}]'))
                )
            except TimeoutException:
                # occurs if there are no more team notes
                # could also happen if page doesn't load: unlikely but possible
                break

            team_notes.click()

            # random notifications (like about IR slots) are detected in teamnotes
            # won't route the bot to another page, so they are filtered here
            if self.driver.current_url != home_url:
                # filter by type of trade through verify_callback
                if verify_callback is None or verify_callback(self.driver):
                    transactions.append(self.driver.current_url)
        return transactions

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

    def shutdown(self):
        """
        Shuts down the driver associated with the TraderBot.
        """
        self.driver.quit()


if __name__ == '__main__':
    bot = TraderBot('your league ID here', 'your team ID here')
    bot.generate_junk_trades()
    bot.shutdown()
