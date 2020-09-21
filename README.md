# Auto-FF
Automatic drafting and trading for Yahoo fantasy football teams.

## Main Features
- DrafterBot
  - Creates customizable rankings based on projections and league settings
  - Analyzes optimal picks dynamically based on rankings and filled positions on a team
  - Automatically drafts the optimal picks
- TraderBot
  - Gets info on any current trades
  - Automatically sends, counters, and cancels trades as specified
  - Uses the "note" section in trades to send and receive messages
    - Can act as standard input for other programs using a simple abstract class API

## To Run

### DrafterBot

To use the DrafterBot, run `drafterbot.py`.

You will be prompted to login to Yahoo a couple times— once for OAuth verification for the Yahoo API, and once for a Selenium-controlled window.

Player rankings can be customized in the program by player ID. A way to use the custom rankings on Yahoo will be added in the future.

### TraderBot

The `traderbot.py` file contains the TraderBot class with multiple methods related to parsing and sending trades.

Any time a TraderBot object is initialized, you will be prompted once to login to Yahoo. This is done either through the Selenium-controlled window, or, if the `headless` property is `True`, through the command line.

You will need to know your league ID and team ID to instantiate TraderBot. To find them, on the Yahoo fantasy football site, click on the "My Team" tab. The URL should be formatted as follows:
```
https://football.fantasysports.yahoo.com/f1/{your_league_id}/{your_team_id}
```

Running `traderbot.py` will run the `generate_junk_trades` method, which creates a file of filler trades which can be referenced in other methods.

To access the other methods, such as `create_trade`, `permacancel`, or `run_game`, you can either write a short script or simply run them in the Python console.

## Running Games

With every trade proposal, you have the opportunity to send an accompanying message. TraderBot contains the `run_game` method, which uses these messages as a way to receive input from your leaguemates.

`run_game` takes in a Game object. The abstract class can be found in `game.py`, but the passed-in object doesn't necessarily have to be derived from Game. All that matters is that the object has an `action(input_str)` method and a `log()` method. `action(input_str)` takes in a string and returns a string, and is called when a response is received. `log()` is used to print updates to the console during `run_game`.

`game.py` includes Hangman, which is a sample Game subclass. Hangman allows you to play games of Hangman through the trade notes.


