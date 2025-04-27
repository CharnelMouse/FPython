import re
from enum import Enum


def tokenise(str):
    tokens = re.split(r"\s+", str)
    return [token for token in tokens if token != ""]


# can handle an empty input
assert tokenise("") == []

# can separate on spaces
tokens = tokenise("1 2 +")
assert tokens == ['1', '2', '+']
del tokens

# can separate on other common whitespace
tokens = tokenise("1  \t2\n \r+")
assert tokens == ['1', '2', '+']
del tokens


def fp(x):
    print(x[0], end=' ')
    return []


class Word(Enum):
    Base = 1
    Compound = 2


class State(Enum):
    Execute = 1
    Word = 2
    Compile = 3


class Forth:
    def __init__(self, silent=False):
        self.data = []
        if silent:
            dot_word = (1, 0, Word.Base, lambda x: [])
        else:
            dot_word = (1, 0, Word.Base, fp)
        self.words = {
            "drop": (1, 0, Word.Base, lambda x: []),
            ".": dot_word,
            "dup": (1, 2, Word.Base, lambda x: x + x),
            "+": (2, 1, Word.Base, lambda x: [x[0] + x[1]]),
            "-": (2, 1, Word.Base, lambda x: [x[0] - x[1]]),
            "*": (2, 1, Word.Base, lambda x: [x[0] * x[1]]),
            "/": (2, 1, Word.Base, lambda x: [x[0] // x[1]]),
            "swap": (2, 2, Word.Base, lambda x: list(reversed(x))),
            "over": (2, 3, Word.Base, lambda x: [x[0], x[1], x[0]]),
            "tuck": (2, 3, Word.Base, lambda x: [x[1], x[0], x[1]]),
            "rot": (3, 3, Word.Base, lambda x: [x[1], x[2], x[0]]),
            "-rot": (3, 3, Word.Base, lambda x: [x[2], x[0], x[1]]),
        }
        self.silent = silent
        self.state = State.Execute

    def do(self, str):
        for token in tokenise(str):
            match self.state:
                case State.Execute:
                    if token in self.words.keys():
                        lin, lout, word_type, word = self.words[token]
                        if (len(self.data) < lin):
                            raise RuntimeError(
                                "Data stack underflow: " + token)
                        used = self.data[-lin:]
                        rest = self.data[:-lin]
                        new = word(used)
                        if (len(new) != lout):
                            raise RuntimeError(
                                "Word output size error: " + token)
                        self.data = rest + new
                    else:
                        try:
                            number = int(token)
                        except Exception:
                            raise RuntimeError("Undefined word: " + token)
                        self.data.append(number)
                case _:
                    raise RuntimeError("Not implemented")
        if not self.silent:
            print("ok")
        return

    def S(self):
        return self.data.copy()


f = Forth(True)
f.do("1 2 drop")
assert f.S() == [1]
del f

f = Forth(True)
f.do("1 2 +")
assert f.S() == [3]
del f
