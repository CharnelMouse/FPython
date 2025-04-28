import re
from array import array
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
        self.data = array('b', [])
        self.memory = array('b', [])
        self.here = 0
        if silent:
            dot_word = (1, 0, Word.Base, lambda x: [])
        else:
            dot_word = (1, 0, Word.Base, fp)
        self.dictionary = [
            (0, 1, Word.Base, lambda x: [self.here]),
            (1, 0, Word.Base, lambda x: self.place(x[0])),
            (1, 0, Word.Base, lambda x: []),
            dot_word,
            (1, 1, Word.Base, lambda x: self.fetch(x[0])),
            (1, 2, Word.Base, lambda x: x + x),
            (2, 0, Word.Base, lambda x: self.store(x[0], x[1])),
            (2, 1, Word.Base, lambda x: [x[0] + x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] - x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] * x[1]]),
            (2, 1, Word.Base, lambda x: [x[0] // x[1]]),
            (2, 1, Word.Base, lambda x: [int(x[0] == x[1])]),
            (2, 1, Word.Base, lambda x: [int(x[0] < x[1])]),
            (2, 1, Word.Base, lambda x: [int(x[0] <= x[1])]),
            (2, 1, Word.Base, lambda x: [int(x[0] > x[1])]),
            (2, 1, Word.Base, lambda x: [int(x[0] >= x[1])]),
            (2, 1, Word.Base, lambda x: [int(x[0] != x[1])]),
            (2, 2, Word.Base, lambda x: list(reversed(x))),
            (2, 3, Word.Base, lambda x: [x[0], x[1], x[0]]),
            (2, 3, Word.Base, lambda x: [x[1], x[0], x[1]]),
            (3, 3, Word.Base, lambda x: [x[1], x[2], x[0]]),
            (3, 3, Word.Base, lambda x: [x[2], x[0], x[1]]),
        ]
        self.names = {
            "here": 0,
            ",": 1,
            "drop": 2,
            ".": 3,
            "@": 4,
            "dup": 5,
            "!": 6,
            "+": 7,
            "-": 8,
            "*": 9,
            "/": 10,
            "=": 11,
            "<": 12,
            "<=": 13,
            ">": 14,
            ">=": 15,
            "<>": 16,
            "swap": 17,
            "over": 18,
            "tuck": 19,
            "rot": 20,
            "-rot": 21,
        }
        self.silent = silent
        self.state = State.Execute
        self.val = None

    def place(self, value):
        self.memory.append(value)
        self.here += 1  # measured in cells for now
        return []

    def fetch(self, index):
        return [0] if index >= len(self.memory) else [self.memory[index]]

    def store(self, value, index):
        if index >= len(self.memory):
            extra = index - len(self.memory) + 1
            self.memory += array('b', extra*[0])
        self.memory[index] = value
        return []

    def reset_state(self, data):
        if data:
            del self.data[:]  # intended for runtime errors (~= list.clear())
        self.state = State.Execute
        self.val = None
        return

    def fail(self, str):
        self.reset_state(data=True)
        raise RuntimeError(str)

    def trace(self, token):
        if token not in self.names.keys():
            raise RuntimeError("Undefined word: " + token)
        lin, lout, _, _ = self.dictionary[self.names[token]]
        return lin, lout

    def orphans(self):
        old = []
        new = list(set(self.names.values()))
        while len(new) > 0:
            old.append(new[0])
            new = new[1:]
            for index in new:
                _, _, word_type, word = self.dictionary[index]
                match word_type:
                    case Word.Compound:
                        children = [
                            index
                            for (type, index) in word
                            if type == Object.Word
                            and index not in old
                            and index not in new
                        ]
                        new += children
        return [
            index
            for index in range(len(self.dictionary))
            if index not in old
        ]

    def compile_word(self):
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

    def number_or_fail(self, token):
        try:
            number = int(token)
        except Exception:
            self.fail("Undefined word: " + token)
        return number

    def execute_valid_word(self, index, token, check=False):
        lin, lout, word_type, word = self.dictionary[index]
        if check:
            if (len(self.data) < lin):
                self.fail("Data stack underflow: " + token)
        match word_type:
            case Word.Base:
                if lin == 0:
                    used = []
                    rest = self.data
                else:
                    used = self.data[-lin:]
                    rest = self.data[:-lin]
                new = word(used)
                if check:
                    if (len(new) != lout):
                        self.fail("Word output size error: " + token)
                self.data = rest + array('b', new)
            case Word.Compound:
                for (object_type, object) in word:
                    match object_type:
                        case Object.Literal:
                            self.data.append(object)
                        case Object.Word:
                            # no check for subwords, since we checked they will
                            # have sufficient stack at compile time
                            self.execute_valid_word(object, token)

    def execute_valid_token(self, token):
        index = self.names[token]
        self.execute_valid_word(index, token, check=True)

    def do(self, str):
        tokens = tokenise(str)
        while len(tokens) > 0:
            token = tokens.pop(0)
            match self.state:
                case State.Execute:
                    if token == "(":
                        end = False
                        index = -1
                        pos = None
                        while not end and index < len(tokens):
                            index += 1
                            nxt = tokens[index]
                            try:
                                pos = nxt.index(')')
                                end = True
                            except Exception:
                                pass
                        if not end:
                            self.fail("Incomplete ( comment")
                        tokens = tokens[index:]
                        tokens[0] = tokens[0][pos+1:]
                        if len(tokens[0]) == 0:
                            tokens = tokens[1:]
                    elif token == ":":
                        self.state = State.Word
                    elif token == "]":
                        self.state = State.Compile
                    elif token == "create":
                        if len(tokens) == 0:
                            self.fail("No target for create")
                        name = tokens.pop(0)
                        self.val = (name, 0, 1, [(Object.Literal, self.here)])
                        self.compile_word()
                        self.reset_state(data=False)
                    elif token in self.names.keys():
                        self.execute_valid_token(token)
                    else:
                        number = self.number_or_fail(token)
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
                                    self.compile_word()
                                case Object.Word:
                                    self.names[self.val[0]] = object
                        else:
                            self.compile_word()
                        self.reset_state(data=False)
                    elif token == "[":
                        self.state = State.Execute
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
                        number = self.number_or_fail(token)
                        self.val[3].append((Object.Literal, number))
                        self.val[2] += 1
        if self.state != State.Execute:
            self.fail("Incomplete program")
        if not self.silent:
            print("ok")
        return

    def S(self):
        return list(self.data).copy()


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

# fails if stopped half-way through a definition
f = Forth(True)
try:
    f.do(": tst 1")
    raise RuntimeError("didn't fail")
except Exception:
    pass
del f

# allows execution at compile time
f = Forth(True)
f.do("1 : tst literal ; : tst2 [ 2 3 + ] literal ; tst tst2")
assert f.S() == [1, 5]
del f

# words are correctly marked as orphans
f = Forth(True)
f.do(": a 1 ; : b a 2 ; : c b 3 ;")
start = f.names["a"]
assert f.orphans() == []
f.do(": a 4 ;")
assert f.orphans() == []
f.do(": b 5 ;")
assert f.orphans() == []
f.do(": c 6 ;")
assert f.orphans() == list(range(start, start + 3))
del start
del f

# create points to proper address
f = Forth(True)
f.do("here")
assert f.S() == [0]
f.do("drop create a1")
f.do("here a1")
assert f.S() == [0, 0]
f.do("drop drop 0 ,  create a2 a1 a2 here")
assert f.S() == [0, 1, 1]
del f

# create doesn't move here, so consecutive creates point to same address
f = Forth(True)
f.do("create a1 create a2 a1 a2")
assert f.S() == [0, 0]
del f

# create doesn't leave info around for next definition
f = Forth(True)
f.do("create a1 : tst ; tst")
assert f.S() == []
del f

# can use here and , within a word
f = Forth(True)
f.do(": tst here 2 * , ; tst tst")
assert list(f.memory) == [0, 2]
del f

# can fetch
f = Forth(True)
f.do("10 , 0 @")
assert f.S() == [10]
del f

# can "fetch" from unassigned memory, returning 0
f = Forth(True)
f.do("0 @")
assert f.S() == [0]
del f

# can store within memory already allocated
f = Forth(True)
f.do("0 , 10 0 ! 0 @")
assert f.S() == [10]
del f

# can store within memory not previously allocated, placing zeroes in gap,
# doesn't move here
f = Forth(True)
f.do("10 5 ! 0 @ 1 @ 2 @ 3 @ 4 @ 5 @ here")
assert f.S() == [0, 0, 0, 0, 0, 10, 0]
del f

# does inequalities
ops = ["=", "<", "<=", ">", ">=", "<>"]
ops = [" " + x + " ," for x in ops]
ops[:-1] = [" over over" + x for x in ops[:-1]]
checks = "".join(ops)
f = Forth(True)
f.do("0 0" + checks)
res = [x != 0 for x in list(f.memory)]
assert res == [True, False, True, False, True, False]
del res
del f
f = Forth(True)
f.do("0 1" + checks)
res = [x != 0 for x in list(f.memory)]
assert res == [False, True, True, False, False, True]
del res
del f
f = Forth(True)
f.do("1 0" + checks)
res = [x != 0 for x in list(f.memory)]
assert res == [False, False, False, True, True, True]
del res
del f
del checks
del ops

# takes ( ... ) comments
f = Forth(True)
f.do("1 ( 2 + ) 3 +")
assert f.S() == [4]
del f

# stops on ) at any time
f = Forth(True)
f.do("1 ( 2 +) 3 +")
assert f.S() == [4]
del f

# continues straight after )
f = Forth(True)
f.do("1 ( 2 +)3 +")
assert f.S() == [4]
del f
f = Forth(True)
f.do("1 3 ( 2 +)+")
assert f.S() == [4]
del f
