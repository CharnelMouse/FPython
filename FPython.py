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


class Object(Enum):
    Literal = 1
    Word = 2


class Forth:
    def __init__(self, silent=False):
        self.data = []
        if silent:
            dot_word = (1, 0, Word.Base, lambda x: [])
        else:
            dot_word = (1, 0, Word.Base, fp)
        self.dictionary = [
            (1, 0, Word.Base, lambda x: []),
            dot_word,
            (1, 2, Word.Base, lambda x: x + x),
            (2, 1, Word.Base, lambda x: [x[0] + x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] - x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] * x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] // x[1]]),
            (2, 2, Word.Base, lambda x: list(reversed(x))),
            (2, 3, Word.Base, lambda x: [x[0], x[1], x[0]]),
            (2, 3, Word.Base, lambda x: [x[1], x[0], x[1]]),
            (3, 3, Word.Base, lambda x: [x[1], x[2], x[0]]),
            (3, 3, Word.Base, lambda x: [x[2], x[0], x[1]]),
        ]
        self.names = {
            "drop": 0,
            ".": 1,
            "dup": 2,
            "+": 3,
            "-": 4,
            "*": 5,
            "/": 6,
            "swap": 7,
            "over": 8,
            "tuck": 9,
            "rot": 10,
            "-rot": 11,
        }
        self.silent = silent
        self.state = State.Execute
        self.val = None

    def trace(self, token):
        if token not in self.names.keys():
            raise RuntimeError("Undefined word: " + token)
        lin, lout, _, _ = self.dictionary[self.names[token]]
        return lin, lout

    def reset_state(self, data=False):
        if data:
            self.data.clear()  # intended for runtime errors
        self.state = State.Execute
        self.val = None
        return

    def execute_valid_word(self, index, token):
        lin, lout, word_type, word = self.dictionary[index]
        if (len(self.data) < lin):
            raise RuntimeError(
                "Data stack underflow: " + token)
        match word_type:
            case Word.Base:
                used = self.data[-lin:]
                rest = self.data[:-lin]
                new = word(used)
                if (len(new) != lout):
                    self.reset_state(data=True)
                    raise RuntimeError(
                        "Word output size error: " + token)
                self.data = rest + new
            case Word.Compound:
                for (object_type, object) in word:
                    match object_type:
                        case Object.Literal:
                            self.data.append(object)
                        case Object.Word:
                            self.execute_valid_word(object, token)

    def execute_valid_token(self, token):
        index = self.names[token]
        self.execute_valid_word(index, token)

    def do(self, str):
        for token in tokenise(str):
            match self.state:
                case State.Execute:
                    if token == ":":
                        self.state = State.Word
                    elif token in self.names.keys():
                        self.execute_valid_token(token)
                    else:
                        try:
                            number = int(token)
                        except Exception:
                            self.reset_state(data=True)
                            raise RuntimeError("Undefined word: " + token)
                        self.data.append(number)
                case State.Word:
                    self.state = State.Compile
                    self.val = [token, 0, 0, []]
                case State.Compile:
                    if token == ";":
                        if not self.silent:
                            if self.val[0] in self.names.keys():
                                print(self.val[0] + " is redefined")
                        if (len(self.val[3]) == 1):
                            object_type, object = self.val[3][0]
                            match object_type:
                                case Object.Literal:
                                    name = self.val[0]
                                    entry = (
                                        self.val[1],
                                        self.val[2],
                                        Word.Compound,
                                        self.val[3]
                                    )
                                    try:
                                        index = self.dictionary.index(entry)
                                        self.names[name] = index
                                    except Exception:
                                        self.names[name] = len(self.dictionary)
                                        self.dictionary.append(entry)
                                case Object.Word:
                                    self.names[self.val[0]] = object
                        else:
                            name = self.val[0]
                            entry = (
                                self.val[1],
                                self.val[2],
                                Word.Compound,
                                self.val[3]
                            )
                            try:
                                index = self.dictionary.index(entry)
                                self.names[name] = index
                            except Exception:
                                self.names[name] = len(self.dictionary)
                                self.dictionary.append(entry)
                        self.reset_state(data=False)
                    elif token == "literal":
                        value = self.data.pop()
                        self.val[3].append((Object.Literal, value))
                        self.val[2] += 1
                    elif token in self.names.keys():
                        index = self.names[token]
                        self.val[3].append((Object.Word, index))
                        old_lout = self.val[2]
                        new_lin, new_lout, _, _ = self.dictionary[index]
                        diff = new_lin - old_lout
                        self.val[2] = new_lout
                        if diff > 0:
                            self.val[1] += diff
                        if diff < 0:
                            self.val[2] -= diff
                    else:
                        try:
                            number = int(token)
                        except Exception:
                            self.reset_state()
                            raise RuntimeError("Undefined word: " + token)
                        self.val[3].append((Object.Literal, number))
                        self.val[2] += 1
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

# stack effect induction works
f = Forth(True)
f.do(": tst over dup -rot + ;")
assert f.trace("tst") == (2, 3)
f.do("2 1 tst")
assert f.S() == [2, 2, 3]
del f

# compiling a word preserves the data stack
f = Forth(True)
f.do("1 : tst ;")
assert f.S() == [1]
del f

# words with same definition point to same entry
f = Forth(True)
f.do(": a 1 + ; : b 1 + ;")
assert f.names["a"] == f.names["b"]
del f

# if a defined word just calls a single other word,
# it just takes the same body
f = Forth(True)
f.do(": add + ;")
assert f.names["add"] == f.names["+"]
del f

# compound words call base words properly
f = Forth(True)
f.do(": tst 1 2 + ; tst")
assert f.S() == [3]
del f

# compound words call compound words properly
f = Forth(True)
f.do(": tst 1 2 + ; : tst2 tst 5 * ; tst2")
assert f.S() == [15]
del f
