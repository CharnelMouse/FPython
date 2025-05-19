from array import array
from enum import Enum


class Word(Enum):
    Base = 0
    Compound = 1


class State(Enum):
    Execute = 0
    Word = 1
    Compile = 2


class Object(Enum):
    Literal = 0
    Word = 1
    Return = 2


class Forth:
    def __init__(self, silent=False):
        self.data = array('l', [])
        self.memory = array('l', [])
        self.ret = array('l', [])
        self.input_buffer = ""
        self.silent = silent
        self.here = 0
        base_words = {
            "create": (0, 0, Word.Base, lambda x: self.create()),
            ":": (0, 0, Word.Base, lambda x: self.word_mode()),
            "]": (0, 0, Word.Base, lambda x: self.compile_mode()),
            "here": (0, 1, Word.Base, lambda x: [self.here]),
            ",": (1, 0, Word.Base, lambda x: self.place(x[0])),
            "drop": (1, 0, Word.Base, lambda x: []),
            ".": (1, 0, Word.Base, lambda x: self.fp(x)),
            "@": (1, 1, Word.Base, lambda x: self.fetch(x[0])),
            "r>": (0, 1, Word.Base, lambda x: self.rFetch()),
            "dup": (1, 2, Word.Base, lambda x: x + x),
            "!": (2, 0, Word.Base, lambda x: self.store(x[0], x[1])),
            ">r": (1, 0, Word.Base, lambda x: self.rStore(x[0])),
            "+": (2, 1, Word.Base, lambda x: [x[0] + x[1]]),
            "-": (2, 1, Word.Base, lambda x: [x[0] - x[1]]),
            "*": (2, 1, Word.Base, lambda x: [x[0] * x[1]]),
            "/": (2, 1, Word.Base, lambda x: [x[0] // x[1]]),
            "=": (2, 1, Word.Base, lambda x: [int(x[0] == x[1])]),
            "<": (2, 1, Word.Base, lambda x: [int(x[0] < x[1])]),
            "<=": (2, 1, Word.Base, lambda x: [int(x[0] <= x[1])]),
            ">": (2, 1, Word.Base, lambda x: [int(x[0] > x[1])]),
            ">=": (2, 1, Word.Base, lambda x: [int(x[0] >= x[1])]),
            "<>": (2, 1, Word.Base, lambda x: [int(x[0] != x[1])]),
            "swap": (2, 2, Word.Base, lambda x: list(reversed(x))),
            "over": (2, 3, Word.Base, lambda x: [x[0], x[1], x[0]]),
            "tuck": (2, 3, Word.Base, lambda x: [x[1], x[0], x[1]]),
            "rot": (3, 3, Word.Base, lambda x: [x[1], x[2], x[0]]),
            "-rot": (3, 3, Word.Base, lambda x: [x[2], x[0], x[1]]),
        }
        self.dictionary = list(base_words.values())
        self.names = {k: list(base_words).index(k) for k in list(base_words)}
        self.lengths = array('l', [
            1 if x[2] == Word.Base
            else len(x[3])
            for x in self.dictionary
        ])
        self.silent = silent
        self.state = State.Execute
        self.val = None

        # base must be added without using .do(), since without it
        # input-output base isn't defined
        self.dictionary += [(
            0,
            1,
            Word.Compound,
            [(Object.Literal, self.here)]
        )]
        self.place(10)
        self.names["base"] = len(self.dictionary) - 1
        self.lengths.append(1)

    def fp(self, x):
        if self.silent:
            return []
        val = x[0]
        base = self.memory[0]
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:base]
        if val == 0:
            print(val, end=' ')
            return []
        if val < 0:
            print("-", end='')
            val = val * -1
        val_str = ""
        while val > 0:
            cur, val = val % base, val // base
            val_str = chars[cur] + val_str
        print(val_str, end=' ')
        return []

    def word_mode(self):
        self.state = State.Word
        return []

    def compile_mode(self):
        self.state = State.Compile
        return []

    def create(self):
        self.input_buffer = self.input_buffer.lstrip()
        if len(self.input_buffer) == 0:
            self.fail("No target for create")
        name = self.pop_token()
        self.val = (name, 0, 1, [(Object.Literal, self.here)])
        self.compile_word()
        self.reset_state(data=False)
        return []

    def place(self, value):
        self.memory.append(value)
        self.here += 1  # measured in cells for now
        return []

    def fetch(self, index):
        return [0] if index >= len(self.memory) else [self.memory[index]]

    def rFetch(self):
        caller_ret = self.ret.pop()
        res = [self.ret.pop()]
        self.ret.append(caller_ret)
        return res

    def store(self, value, index):
        if index >= len(self.memory):
            extra = index - len(self.memory) + 1
            self.memory += array('l', extra*[0])
        self.memory[index] = value
        return []

    def rStore(self, value):
        caller_ret = self.ret.pop()
        self.ret.append(value)
        self.ret.append(caller_ret)
        return []

    def reset_state(self, data):
        if data:
            # intended for runtime errors (~= list.clear())
            del self.data[:]
            del self.ret[:]
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
        self.val[3].append((Object.Return, 0))
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
            self.lengths.append(len(self.val[3]))

    def number_or_fail(self, token):
        try:
            number = int(token, base=self.memory[0])
        except Exception:
            self.fail("Undefined word: " + token)
        return number

    def resolve_return_stack(self, token):
        while len(self.ret) > 0:
            current = self.ret.pop()
            if current < 0 or current >= sum(self.lengths):
                self.fail("Invalid return stack item: " + token)

            dictionary_index = 0
            offset = 0
            s = 0
            # while current is start of next entry or later
            while dictionary_index < len(self.lengths):
                s2 = s + self.lengths[dictionary_index]
                if s2 > current:
                    break
                s += self.lengths[dictionary_index]
                dictionary_index += 1
            if dictionary_index == len(self.lengths):
                self.fail("Return stack lookup failure: " + token)
            assert s == sum(self.lengths[:dictionary_index])
            offset = current - s
            assert 0 <= offset < self.lengths[dictionary_index]

            lin, lout, word_type, word = self.dictionary[dictionary_index]
            match word_type:
                case Word.Base:
                    # execute the word, leave nothing back on the return stack
                    assert offset == 0
                    if lin == 0:
                        used = []
                        rest = self.data
                    else:
                        used = self.data[-lin:]
                        rest = self.data[:-lin]
                    new = word(used)
                    self.data = rest + array('l', new)
                case Word.Compound:
                    # add all initial literals
                    while offset < len(word):
                        object_type, object = word[offset]
                        if object_type != Object.Literal:
                            break
                        self.data.append(object)
                        offset += 1
                    if offset == len(word):
                        continue
                    object_type, object = word[offset]
                    if object_type == Object.Return:
                        continue
                    assert object_type == Object.Word
                    nxt = sum(self.lengths[:object])
                    # not Return -> not last element, so can push next one
                    self.ret.append(s + offset + 1)
                    self.ret.append(nxt)

    def execute_valid_token(self, token):
        index = self.names[token]
        lin = len(self.data)
        min_lin, add_lout, _, _ = self.dictionary[index]
        if lin < min_lin:
            self.fail("Data stack underflow: " + token)
        word_offset = sum(self.lengths[:index])
        self.ret.append(word_offset)
        self.resolve_return_stack(token)
        lout = len(self.data)
        if lout != lin + add_lout - min_lin:
            self.fail("Word output size error: " + token)

    def pop_token(self):
        res = self.input_buffer.split(maxsplit=1)
        if len(res) == 1:
            self.input_buffer = []
        else:
            self.input_buffer = res[1]
        return res[0]

    def do(self, str):
        self.input_buffer = str
        self.input_buffer = self.input_buffer.strip()
        while len(self.input_buffer) > 0:
            token = self.pop_token()
            if token == "(":
                try:
                    index = self.input_buffer.index(')')
                except Exception:
                    self.fail("Incomplete ( comment")
                self.input_buffer = self.input_buffer[index + 1:]
                continue
            if token == "\\":
                try:
                    index = self.input_buffer.index('\n')
                except Exception:
                    break
                self.input_buffer = self.input_buffer[index + 1:]
                continue
            match self.state:
                case State.Execute:
                    if token in self.names.keys():
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
        if len(self.ret) > 0:
            self.fail("Return stack must be emptied")
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
start = f.here
f.do("here")
assert f.S() == [start]
f.do("drop create a1")
f.do("here a1")
assert f.S() == [start, start]
f.do("drop drop 0 ,  create a2 a1 a2 here")
assert f.S() == [start, start + 1, start + 1]
del start
del f

# create doesn't move here, so consecutive creates point to same address
f = Forth(True)
start = f.here
f.do("create a1 create a2 a1 a2")
assert f.S() == [start, start]
del f

# create doesn't leave info around for next definition
f = Forth(True)
f.do("create a1 : tst ; tst")
assert f.S() == []
del f

# can use here and , within a word
f = Forth(True)
start = f.here
f.do(": tst here 2 * , ; tst tst")
assert list(f.memory[start:]) == [2, 4]
del start
del f

# can fetch
f = Forth(True)
f.do("here 12 , @")
assert f.S() == [12]
del f

# can "fetch" from unassigned memory, returning 0
f = Forth(True)
f.do("10 @")
assert f.S() == [0]
del f

# can store within memory already allocated
f = Forth(True)
f.do("here 0 , 12 over ! @")
assert f.S() == [12]
del f

# can store within memory not previously allocated, placing zeroes in gap,
# doesn't move here
f = Forth(True)
start = f.here
f.do("10 5 ! 0 @ 1 @ 2 @ 3 @ 4 @ 5 @ here")
assert f.S()[start:] == [0, 0, 0, 0, 10, 1]
del start
del f

# does inequalities
ops = ["=", "<", "<=", ">", ">=", "<>"]
ops = [" " + x + " ," for x in ops]
ops[:-1] = [" over over" + x for x in ops[:-1]]
checks = "".join(ops)
f = Forth(True)
memstart = f.here
f.do("0 0" + checks)
res = [x != 0 for x in list(f.memory[memstart:])]
assert res == [True, False, True, False, True, False]
del res
del memstart
del f
f = Forth(True)
memstart = f.here
f.do("0 1" + checks)
res = [x != 0 for x in list(f.memory[memstart:])]
assert res == [False, True, True, False, False, True]
del res
del memstart
del f
f = Forth(True)
memstart = f.here
f.do("1 0" + checks)
res = [x != 0 for x in list(f.memory[memstart:])]
assert res == [False, False, False, True, True, True]
del res
del memstart
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

# takes comments in definitions
f = Forth(True)
f.do(": tst ( n n -- n ) + ;")
assert f.names["tst"] == f.names["+"]
del f
f = Forth(True)
f.do(": ( same as plus ) tst + ;")
assert f.names["tst"] == f.names["+"]
del f

# takes \ comments
f = Forth(True)
f.do("1 \\ 2 +")
assert f.S() == [1]
del f
# continues after newline
f = Forth(True)
f.do("1 \\ 2 + \n 3 +")
assert f.S() == [4]
del f

# can use return stack to store values
f = Forth(True)
f.do(": tst >r r> ; 123 tst")
assert f.S() == [123]
del f
f = Forth(True)
f.do(": tst >r r> dup >r r> drop ; 123 tst")
assert f.S() == [123]
del f

# uses return stack for returns, tracks by word index and current position
f = Forth(True)
f.do(": tst r> drop ; : tst2 1 tst 2 + ; tst2")
assert f.S() == [1]
del f

# empties return stack on failure
f = Forth(True)
try:
    f.do(": tst 1 drop drop -1 >r 2 ; : tst2 3 tst 4 ; tst2")
    raise RuntimeError("didn't fail")
except Exception:
    assert len(f.ret) == 0
del f

# "base" fetches the current integer base
f = Forth(True)
f.do("base @")
assert f.S() == [10]
f.do("drop 16 base ! base @")
assert f.S() == [16]
del f

# can work in non-decimal bases
f = Forth(True)
f.do("16 base ! A")
assert f.S() == [10]
del f
f = Forth(True)
f.do("36 base ! LBA")
assert f.S() == [27622]
del f
