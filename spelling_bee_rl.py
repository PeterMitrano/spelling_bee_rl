"""spelling_bee_rl.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JR4kuwTTiDfV74zlrYxx5Ik_HDjl-aw7
"""
import pathlib
import pickle
import random
from dataclasses import dataclass
from itertools import product
from multiprocessing import Pool
from time import perf_counter
from time import time
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon
from tqdm import trange


def load_dictionary():
    # res = requests.get("https://raw.githubusercontent.com/PeterMitrano/spelling_bee_rl/master/valid_words.txt")
    # text = res.text
    # valid_words = text.split('\n')[:-1]
    with open("valid_words.txt", "r") as f:
        valid_words = [l.strip("\n") for l in f.readlines()]
    return valid_words


def add_to_dict_tree(word_dict, word):
    known_words_dict = word_dict
    for c in word:
        if c not in known_words_dict:
            known_words_dict[c] = {}
        known_words_dict = known_words_dict[c]


LETTER_FREQUENCIES = {
    'e': 12.1607,
    'm': 3.0129,
    'a': 9.4966,
    'h': 3.0034,
    'r': 7.5809,
    'g': 2.4705,
    'i': 8.5448,
    'b': 2.0720,
    'o': 8.1635,
    'f': 1.8121,
    't': 6.9509,
    'y': 1.7779,
    'n': 6.6544,
    'w': 1.2899,
    's': 5.7351,
    'k': 1.1016,
    'l': 5.4893,
    'v': 1.0074,
    'c': 4.5388,
    'x': 0.2902,
    'u': 4.6308,
    'z': 0.2722,
    'd': 3.3844,
    'j': 0.1965,
    'p': 3.1671,
    'q': 0.1962,
}

CORRECT_REWARD = 100
INCORRECT_REWARD = -1
MAX_GUESS_LEN = 10
chars = [chr(i) for i in range(97, 97 + 26)]
vowels = ['a', 'e,', 'i', 'o', 'u']
consonants = [c for c in chars if c not in vowels]
dictionary_list = load_dictionary()
dictionary_tree = {}
for w in dictionary_list:
    add_to_dict_tree(dictionary_tree, w)

outer_color = "#ccc"
inner_color = "y"


def sample_puzzle(rng):
    p = list(LETTER_FREQUENCIES.values())
    p = p / np.sum(p)
    return rng.choice(list(LETTER_FREQUENCIES.keys()), p=p, size=7, replace=False).tolist()


def create_game_ui():
    fig = plt.figure(figsize=(5, 10))
    ax = plt.gca()
    plt.xticks([])
    plt.yticks([])
    return fig, ax


def make_hexagon(ax, x, y, color, letter):
    points = np.array([[x, y]]) + np.array([
        [0.5, 0],
        [0.25, np.sqrt(3) / 4],
        [-0.25, np.sqrt(3) / 4],
        [-0.5, 0],
        [-0.25, -np.sqrt(3) / 4],
        [0.25, -np.sqrt(3) / 4],
    ]) * 0.26
    patch = Polygon(points, facecolor=color)
    ax.add_patch(patch)
    ax.text(x - .03, y - .03, letter.upper(), fontdict={"fontsize": 20})

    return patch


def init_ui(ax, puzzle):
    patches = []
    patches.append(make_hexagon(ax, 0.5, 0.5, inner_color, puzzle[0]))
    patches.append(make_hexagon(ax, 0.5, 0.75, outer_color, puzzle[1]))
    patches.append(make_hexagon(ax, np.sqrt(3) / 8 + 0.5, 0.625, outer_color, puzzle[2]))
    patches.append(make_hexagon(ax, np.sqrt(3) / 8 + 0.5, 0.375, outer_color, puzzle[3]))
    patches.append(make_hexagon(ax, 0.5, 0.25, outer_color, puzzle[4]))
    patches.append(make_hexagon(ax, -np.sqrt(3) / 8 + 0.5, 0.375, outer_color, puzzle[5]))
    patches.append(make_hexagon(ax, -np.sqrt(3) / 8 + 0.5, 0.625, outer_color, puzzle[6]))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 2)
    guess_text = ax.text(0.1, 1, "", fontdict={"fontsize": 20})
    words_found_text = ax.text(0.05, 2 - 0.105 * 1, "", fontdict={"fontsize": 10})

    return guess_text, words_found_text, patches


def word_in_dict(word, root_dict):
    dict_tmp = root_dict
    for c in word:
        if c not in dict_tmp:
            return False
        dict_tmp = dict_tmp[c]
    return True


class SpellingBeeEnv:
    MAX_GUESSES_PER_PUZZLE = 900_000_000

    def __init__(self, viz: bool):
        random.seed(1)
        self.rng = np.random.RandomState(3)
        self.action_rng = np.random.RandomState(1)
        self.words_found = []
        self.possible_words = None
        self.puzzle = None
        self.state = None
        self.n_actions = None
        self.len_possible_words = None
        self.len_words_found = 0

        self.patches = []
        self.viz = viz
        if self.viz:
            self.fig, self.ax = create_game_ui()
            plt.show(block=False)
        else:
            self.fig = None
            self.ax = None

    def reset(self):
        # sample a new spelling bee puzzle
        self.state = []
        self.words_found = []
        self.n_actions = 0
        self.len_words_found = 0

        while True:
            self.puzzle = sample_puzzle(self.rng)
            self.possible_words = set()
            for w in dictionary_list:
                if can_make(self.puzzle, w):
                    self.possible_words.add(w)
            if 10 < len(self.possible_words):
                self.len_possible_words = len(self.possible_words)
                print(f"Longest possible word has {max([len(w) for w in self.possible_words])}")
                break

        if self.fig is None or self.ax is None:
            self.fig, self.ax = create_game_ui()
            plt.show(block=False)
        if self.viz:
            self.ax.clear()
            for p in self.patches:
                p.remove()
            self.guess_text, self.words_found_text, self.patches = init_ui(self.ax, self.puzzle)

    def step(self, action):
        # takes in the action (an integer from 0-7, 7 meaning check dictionary)
        # returns the next state, reward, and whether the episode is over
        word = "".join(self.state)
        if action == 7:
            if self.puzzle[0] in word and word_in_dict(word, dictionary_tree):
                self.words_found.append(word)
                self.len_words_found = len(self.words_found)
                reward = CORRECT_REWARD
            else:
                reward = INCORRECT_REWARD
            # reset state after guessing
            self.state = []
        elif len(word) >= MAX_GUESS_LEN:
            reward = INCORRECT_REWARD
            # no state update
        else:
            next_character = self.puzzle[action]
            reward = 0
            self.state = self.state + [next_character]

        self.n_actions += 1

        solved = self.len_words_found == self.len_possible_words
        if solved:
            print("Solved!!!!")
        done = solved or self.n_actions > SpellingBeeEnv.MAX_GUESSES_PER_PUZZLE

        if self.viz:
            self.guess_text.set_text(word)
            self.words_found_text.set_text(self.words_found)
            plt.pause(0.01)

        return self.state, reward, done

    def random_action(self):
        return self.action_rng.randint(0, 8)


class AbstractAgent:

    def __init__(self, env):
        self.env = env

    def reset(self):
        pass

    def policy(self, state):
        raise NotImplementedError()

    def post_step(self, state, next_state, action, reward):
        raise NotImplementedError()

    def save(self, path: pathlib.Path):
        with path.open('wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path):
        with path.open('rb') as f:
            return pickle.load(f)


class RandomAgent(AbstractAgent):
    def policy(self, state):
        return self.env.random_action()

    def post_step(self, state, next_state, action, reward):
        pass


def can_make(puzzle, word):
    return set(word).issubset(set(puzzle)) and (puzzle[0] in word)


def p_enter(l):
    b = -3 / (MAX_GUESS_LEN - 3)
    return max(min((1 / (MAX_GUESS_LEN - 3)) * l + b, 1), 0)


def softmax(x):
    z = x - max(x)
    numerator = np.exp(z)
    denominator = np.sum(numerator)
    softmax = numerator / denominator
    return softmax


class HeuristicAgent1(AbstractAgent):
    def __init__(self, env):
        super().__init__(env)
        self.guessed_words = None
        self.known_words = []
        self.known_not_words = []
        self.pair_counts = {}
        for l1 in chars:
            self.pair_counts[l1] = {}
            for l2 in chars:
                self.pair_counts[l1][l2] = 0
        self.rng = np.random.RandomState(0)

    def flat_pair_counts(self):
        flat_pair_counts = {}
        for l1 in self.pair_counts.keys():
            for l2 in self.pair_counts[l1].keys():
                v = self.pair_counts[l1][l2]
                if v != 0:
                    flat_pair_counts[l1 + l2] = v
        return flat_pair_counts

    def print_pair_counts(self):
        for l1 in self.pair_counts.keys():
            for l2 in self.pair_counts[l1].keys():
                v = self.pair_counts[l1][l2]
                if v != 0:
                    print(l1, l2, v)

    def reset(self):
        self.guessed_words = []

    def policy(self, state):
        # loop through every word we know exists, and check if we can make that word with the letters in the puzzle
        # if we can, return the action corresponding to the next letter we need to append to state to spell that word
        # if we've fully matched state to the known word we return the action 7 and ...
        # (1) add that to our list of guessed words
        # (2) add all pairs of letters to the pair counts

        # if none of the known words can be spelled,
        # if len(state) == 0:
        #   randomly select a first letter
        # if len(state) >= 1:
        #   given the first letter, sample a next letter proportional to the probabilities of two letter pairs we have
        #   or with some small probability return 7
        #   but don't hit enter if the word is in known_not_words

        word_so_far = ''.join(state)
        for w in self.known_words:
            if w not in self.guessed_words:
                if can_make(self.env.puzzle, w):
                    if word_so_far == w:
                        return self.guess_word(state)
                    else:
                        next_letter = w[len(word_so_far)]
                        return self.env.puzzle.index(next_letter)

        r = self.rng.rand()
        if r < p_enter(len(state)) and word_so_far not in self.known_not_words:
            # print("guessing!", state)
            return 7

        if len(state) == 0:
            return self.rng.randint(0, 7)
        elif len(state) == MAX_GUESS_LEN:
            return 7
        else:
            l1 = state[-1]
            relevant_l2_counts = np.array([self.pair_counts[l1][l2] for l2 in self.env.puzzle])
            relevant_l2_probabilities = softmax(relevant_l2_counts)
            l2 = self.rng.choice(self.env.puzzle, p=relevant_l2_probabilities)

            return self.env.puzzle.index(l2)

    def post_step(self, state, next_state, action, reward):
        word = ''.join(state)
        if reward == CORRECT_REWARD:
            for l1, l2 in zip(word[:-1], word[1:]):
                self.pair_counts[l1][l2] += 1
            if word not in self.known_words:
                self.known_words.append(word)
            self.guessed_words.append(word)
            # print(word, "is a word!")
        elif reward == INCORRECT_REWARD:
            for l1, l2 in zip(word[:-1], word[1:]):
                self.pair_counts[l1][l2] -= 1
            if word not in self.known_not_words:
                self.known_not_words.append(word)
            self.guessed_words.append(word)

    def guess_word(self, state):
        self.guessed_words.append(''.join(state))
        return 7


def generate_all_guesses(max_len):
    """
    recursively yields...
    0 0 0 0 7 (7 means enter)
    0 0 0 1 7
    0 0 0 2 7
    ...
    0 0 0 6 7
    0 0 1 0 7
    ...
    0 0 6 6 7
    ...
    6 6 6 6 7
    0 0 0 0 0 7
    ...
    6 6 6 6 6 7
    ...
    6 6 6 6 6 6 ... 6 7
    """
    for l in range(4, max_len + 1):
        for i in range(l):
            for c in product(range(7), repeat=l - 1):
                c = list(c)
                guess = c[:i] + [0] + c[i:] + [7]
                if i == l - 1 or 0 != c[i]:
                    yield guess


def heuristic_score1(args):
    puzzle, guess = args
    word = [puzzle[i] for i in guess[:-1]]
    # _, counts = np.unique(word, return_counts=True)
    # high_duplication_cost = np.square(counts).sum()
    # letter_freq_score = sum([LETTER_FREQUENCIES[c] for c in word])
    # no_consonants_cost = np.all([(c in consonants) for c in word]).astype(int) * 10
    # no_vowels_cost = np.all([(c in vowels) for c in word]).astype(int) * 10

    score = np.exp(-len(word))
    # score -= high_duplication_cost
    # score += letter_freq_score
    # score -= no_vowels_cost
    # score -= no_consonants_cost

    return score


class ExhaustiveAgent(AbstractAgent):
    def __init__(self, env):
        super().__init__(env)
        self.guessed_words = None
        self.known_words = {}
        self.known_not_words = {}

        self.possible_guesses = np.array(list(generate_all_guesses(8)), dtype=object)
        self.len_possible_guesses = len(self.possible_guesses)
        self.current_word_guess_idx = 0
        self.current_letter_guess_idx = 0
        self.has_guessed_all_known_words = False
        self.possible_known_words = None
        # TODO: incorporate known not words so we don't repeat words that don't exist

    def reset(self):
        self.guessed_words = []

        self.has_guessed_all_known_words = False
        self.possible_known_words = []
        # FIXME: this is wrong
        for w in self.known_words:
            if can_make(self.env.puzzle, w):
                self.possible_known_words.append(w)
        self.current_word_guess_idx = 0
        self.current_letter_guess_idx = 0

        print("Ranking guesses...")
        with Pool() as p:
            args = [(self.env.puzzle, g) for g in self.possible_guesses]
            possible_guesses_scores = list(p.imap_unordered(heuristic_score1, args, chunksize=10000))
        print("done!")

        sorted_indices = np.argsort(possible_guesses_scores)
        self.sorted_possible_guesses = self.possible_guesses[sorted_indices]

    def policy(self, state):
        # word_so_far = ''.join(state)
        # self.guessed_words[state[0]]
        # for w in self.known_words:
        #     if w not in self.guessed_words:
        #         if can_make(self.env.puzzle, w):
        #             if word_so_far == w:
        #                 return self.guess_word(state)
        #             else:
        #                 next_letter = w[len(word_so_far)]
        #                 return self.env.puzzle.index(next_letter)

        while True:
            if self.current_word_guess_idx % 50000 == 0 and self.current_letter_guess_idx == 0:
                print(f"{100 * self.current_word_guess_idx / self.len_possible_guesses:.1f}%")
            if self.current_word_guess_idx < self.len_possible_guesses:
                current_word_guess = self.sorted_possible_guesses[self.current_word_guess_idx]
                # first check if it's a known not-word
                if self.is_word_known(current_word_guess):
                    self.current_word_guess_idx += 1
                    self.current_letter_guess_idx = 0
                else:
                    current_letter_guess = current_word_guess[self.current_letter_guess_idx]
                    self.current_letter_guess_idx += 1
                    if self.current_letter_guess_idx > len(current_word_guess) - 1:
                        self.current_word_guess_idx += 1
                        self.current_letter_guess_idx = 0
                    if current_letter_guess == 7:
                        self.guessed_words.append(''.join(state))
                    return current_letter_guess
            else:
                return 8

    def is_word_known(self, word):
        return word_in_dict(word, self.known_not_words)

    def guess_word(self, state):
        self.guessed_words.append(''.join(state))
        return 7

    def post_step(self, state, next_state, action, reward):
        word = ''.join(state)
        if reward == CORRECT_REWARD:
            if word not in self.known_words:
                add_to_dict_tree(self.known_words, word)
            self.guessed_words.append(word)
        elif reward == INCORRECT_REWARD:
            add_to_dict_tree(self.known_not_words, word)
            self.guessed_words.append(word)


def main():
    env = SpellingBeeEnv(viz=False)
    # agent = HeuristicAgent1(env)
    agent = ExhaustiveAgent(env)

    for _ in trange(2000):
        env.reset()
        agent.reset()
        state = env.state

        t0 = perf_counter()
        while True:
            action = agent.policy(state)
            if action == 8:
                break
            next_state, reward, done = env.step(action)
            agent.post_step(state, next_state, action, reward)
            state = next_state
            if done:
                break
        print(perf_counter() - t0)
        pass

    out = pathlib.Path(f"agent_{int(time())}")
    print(f"Saved to {out.as_posix()}")
    agent.save(out)

    agent = AbstractAgent.load(pathlib.Path("agent_1647573965"))
    agent.env = env
    env = agent.env
    # EVALUATION
    env.viz = True
    env.reset()
    agent.reset()
    state = env.state
    while True:
        action = agent.policy(state)
        if action == 8:
            break
        next_state, reward, done = env.step(action)
        agent.post_step(state, next_state, action, reward)
        state = next_state
        if done:
            break

    print(agent.known_words)

    flat_pair_counts = agent.flat_pair_counts()
    plt.figure()
    ax = plt.gca()
    letters = flat_pair_counts.keys()
    counts = flat_pair_counts.values()
    ax.plot(letters, counts)

    print(agent.guessed_words)
    plt.show()


if __name__ == '__main__':
    main()
