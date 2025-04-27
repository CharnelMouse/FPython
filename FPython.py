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


def do(str):
    data = []
    words = {
        "drop": (1, 0, lambda x: []),
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
    for token in tokenise(str):
        if token in words.keys():
            lin, lout, word = words[token]
            if (len(data) < lin):
                raise RuntimeError(
                    "Data stack underflow: " + token)
            used = data[-lin:]
            rest = data[:-lin]
            new = word(used)
            if (len(new) != lout):
                raise RuntimeError(
                    "Word output size error: " + token)
            data = rest + new
        else:
            try:
                number = int(token)
            except Exception:
                raise RuntimeError("Undefined word: " + token)
            data.append(number)
    return data


assert do("1 2 drop") == [1]
assert do("1 2 +") == [3]
