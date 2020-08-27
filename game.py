import requests
import random
from abc import ABC, abstractmethod


class Game(ABC):

    @abstractmethod
    def action(self, input_str) -> str:
        # return
        pass

    @abstractmethod
    def log(self) -> str:
        pass


class Hangman(Game):
    def __init__(self):
        words = requests.get('https://users.cs.duke.edu/~ola/ap/linuxwords').text.split()
        self.words = [word.lower().strip() for word in words if not word[0].isupper() and len(word) >= 3]
        self.reset()

    def reset(self):
        self.word = [[char, False] for char in list(random.choice(self.words))]
        self.wrong_guesses_left = 6
        self.guesses = []
        self.started = False

    def guess(self, letter):
        matching_chars = 0
        self.guesses.append(letter)
        for char in self.word:
            if not char[1] and char[0] == letter:
                char[1] = True
                matching_chars += 1
        if matching_chars == 0:
            self.wrong_guesses_left -= 1

    def get_knowns(self):
        knowns = ''
        for char in self.word:
            if char[1]:
                knowns += char[0] + ' '
            else:
                knowns += '_ '
        knowns.strip()
        return knowns

    def get_word(self):
        return ''.join([char[0] for char in self.word])

    def check_victory(self):
        for char in self.word:
            if not char[1]:
                return False
        return True

    def check_loss(self):
        if self.wrong_guesses_left > 0:
            return False
        return True

    def get_possible_words(self):
        possible_words = []
        for word in self.words:
            if len(word) == len(self.word):
                matching_known_chars = True
                for i, char in enumerate(self.word):
                    if (char[1] and char[0] != word[i]) or (not char[1] and word[i] in self.guesses):
                        matching_known_chars = False
                        break
                if matching_known_chars:
                    possible_words.append(word)
        return possible_words

    def cheat(self):
        possible_words = self.get_possible_words()
        if len(possible_words) >= 1:
            possible_words.append(self.get_word())
            new_word = random.choice(possible_words)
            for i, char in enumerate(self.word):
                char[0] = new_word[i]

    def check_input(self, input_str):
        if len(input_str) == 1 and input_str.isalpha():
            return True
        return False

    def start(self):
        self.started = True
        message = self.get_knowns()
        message += '\n\nTo guess, counter this trade and enter a letter in the trade note area.'
        return message

    def action(self, input_str):
        if not self.started:
            return self.start()
        if self.check_input(input_str):
            input_str = input_str.lower()
            self.guess(input_str)
            message = self.get_knowns()
            message += f'\tGuesses left: {self.wrong_guesses_left} \t Previous guesses: {", ".join(self.guesses)}'
            if self.check_victory():
                message += '\n\nYou won!'
                self.reset()
                message += '\n\nTo play again, submit another trade.'
            elif self.check_loss():
                message += '\n\nYou ran out of guesses.'
                message += f'The word was: {self.get_word()}'
                self.reset()
                message += '\n\nTo play again, submit another trade.'
            else:
                message += '\n\nTo guess, counter this trade and enter a letter in the trade note area.'
        else:
            message = f'The input {input_str} was invalid. Type exactly one letter into the trade note box.'
        return message

    def log(self):
        return f'{game.get_knowns()} ({game.get_word()})'


if __name__ == '__main__':
    game = Hangman()
    while not game.check_victory() and not game.check_loss():
        print(game.action(input()))
