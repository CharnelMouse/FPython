import re


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


class Forth:
    def __init__(self, silent=False):
        self.data = []
        if silent:
            dot_word = (1, 0, lambda x: [])
        else:
            dot_word = (1, 0, fp)
        self.words = {
            "drop": (1, 0, lambda x: []),
            ".": dot_word,
            "dup": (1, 2, lambda x: x + x),
            "+": (2, 1, lambda x: [x[0] + x[1]]),
            "-": (2, 1, lambda x: [x[0] - x[1]]),
            "*": (2, 1, lambda x: [x[0] * x[1]]),
            "/": (2, 1, lambda x: [x[0] // x[1]]),
            "swap": (2, 2, lambda x: list(reversed(x))),
            "over": (2, 3, lambda x: [x[0], x[1], x[0]]),
            "tuck": (2, 3, lambda x: [x[1], x[0], x[1]]),
            "rot": (3, 3, lambda x: [x[1], x[2], x[0]]),
            "-rot": (3, 3, lambda x: [x[2], x[0], x[1]]),
        }
        self.silent = silent

    def do(self, str):
        for token in tokenise(str):
            if token in self.words.keys():
                lin, lout, word = self.words[token]
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
