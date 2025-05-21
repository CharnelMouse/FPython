from tempfile import NamedTemporaryFile as tempfile  # for tests only
from array import array
from enum import Enum


class Word(Enum):
    Base = 0
    Compound = 1


class Speed(Enum):
    Normal = 0
    Immediate = 1


class State(Enum):
    Execute = 0
    Compile = 1


class Object(Enum):
    Literal = 0
    Word = 1
    Return = 2


class Definition:
    def __init__(self, name):
        self.name = name
        self.lin = 0
        self.lout = 0
        self.body = []

    def call(self, index, callee):
        new_lin, new_lout, _, _ = callee
        self.body.append((Object.Word, index))
        old_lout = self.lout
        diff = new_lin - old_lout
        self.lout = new_lout
        if diff > 0:
            self.lin += diff
        if diff < 0:
            self.lout -= diff

    def lit(self, value):
        self.body.append((Object.Literal, value))
        self.lout += 1

    def ret(self):
        self.body.append((Object.Return, 0))

    def end(self):
        return (
            self.name,
            (
                self.lin,
                self.lout,
                Word.Compound,
                self.body
            )
        )


class Forth:
    def __init__(self, silent=False, cell=4):
        cell_types = {1: 'b', 2: 'h', 4: 'l', 8: 'q'}
        try:
            cell_type = cell_types[cell]
        except KeyError:
            raise RuntimeError("Invalid cell size: " + str(cell))
        self.cell = cell
        self.data = array(cell_type, [])
        self.memory = array(cell_type, [])
        self.ret = array(cell_type, [])
        self.input_buffer = ""
        self.pad = ""
        self.silent = True
        self.here = 0

        def bw(instack, outstack, fun, im=False):
            return (
                instack,
                outstack,
                Word.Base,
                Speed.Immediate if im else Speed.Normal,
                fun
            )
        base_words = {
            "bd": bw(0, 0, lambda x: self.begin_definition()),
            "postpone": bw(0, 0, lambda x: self.postpone(), im=True),
            "word": bw(0, 0, lambda x: self.read_word()),
            "include": bw(0, 0, lambda x: self.include()),
            ";": bw(0, 0, lambda x: self.end_compile(), im=True),
            ";im": bw(0, 0, lambda x: self.end_compile(im=True), im=True),
            ";r": bw(0, 0, lambda x: self.end_compile(reduce1=True), im=True),
            ";imr": bw(0, 0, lambda x: self.end_compile(True, True), im=True),
            "[": bw(0, 0, lambda x: self.execute_mode(), im=True),
            "]": bw(0, 0, lambda x: self.compile_mode()),
            "cell": bw(0, 1, lambda x: [self.cell]),
            "here": bw(0, 1, lambda x: [self.here]),
            "trace": bw(0, 2, lambda x: self.trace()),
            ",": bw(1, 0, lambda x: self.place(x[0])),
            "literal": bw(1, 0, lambda x: self.compile_literal(x[0]), im=True),
            "drop": bw(1, 0, lambda x: []),
            ".": bw(1, 0, lambda x: self.fp(x)),
            "@": bw(1, 1, lambda x: self.fetch(x[0])),
            "r>": bw(0, 1, lambda x: self.rFetch()),
            "dup": bw(1, 2, lambda x: x + x),
            "!": bw(2, 0, lambda x: self.store(x[0], x[1])),
            ">r": bw(1, 0, lambda x: self.rStore(x[0])),
            "+": bw(2, 1, lambda x: [x[0] + x[1]]),
            "-": bw(2, 1, lambda x: [x[0] - x[1]]),
            "*": bw(2, 1, lambda x: [x[0] * x[1]]),
            "/": bw(2, 1, lambda x: [x[0] // x[1]]),
            "=": bw(2, 1, lambda x: [int(x[0] == x[1])]),
            "<": bw(2, 1, lambda x: [int(x[0] < x[1])]),
            "<=": bw(2, 1, lambda x: [int(x[0] <= x[1])]),
            ">": bw(2, 1, lambda x: [int(x[0] > x[1])]),
            ">=": bw(2, 1, lambda x: [int(x[0] >= x[1])]),
            "<>": bw(2, 1, lambda x: [int(x[0] != x[1])]),
            "swap": bw(2, 2, lambda x: list(reversed(x))),
            "over": bw(2, 3, lambda x: [x[0], x[1], x[0]]),
            "tuck": bw(2, 3, lambda x: [x[1], x[0], x[1]]),
            "rot": bw(3, 3, lambda x: [x[1], x[2], x[0]]),
            "-rot": bw(3, 3, lambda x: [x[2], x[0], x[1]]),
        }
        self.dictionary = [
            (lin, lout, word_type, body)
            for (lin, lout, word_type, _, body)
            in base_words.values()
        ]
        self.names = {
            k.upper(): list(base_words).index(k)
            for k
            in list(base_words)
        }
        self.speeds = {
            k.upper(): speed
            for (k, (_, _, _, speed, _))
            in base_words.items()
        }
        self.lengths = array(cell_type, [
            1 if x[2] == Word.Base
            else len(x[3])
            for x in self.dictionary
        ])
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
        self.names["BASE"] = len(self.dictionary) - 1
        self.speeds["BASE"] = Speed.Normal
        self.lengths.append(1)

        # : must be compiled more implicitly, then it can be used
        # to define the other initial compound words
        self.val = Definition(":")
        self.resolve_word_compile("WORD")
        self.resolve_word_compile("BD")
        self.resolve_word_compile("]")
        self.end_compile()

        # initial compound words
        self.do(
            ": create postpone : postpone here postpone literal postpone ; ;"
        )
        self.do(": binary #2 base ! ;")
        self.do(": decimal #10 base ! ;")
        self.do(": hex #16 base ! ;")

        self.silent = silent

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

    def read_word(self):
        self.input_buffer = self.input_buffer.lstrip()
        if len(self.input_buffer) == 0:
            self.fail("No target for create")
        self.pad = self.pop_token()
        return []

    def include(self):
        self.read_word()
        try:
            with open(self.pad, "r") as file:
                txt = str(file.read())
                file.close()
            self.input_buffer = txt + " " + self.input_buffer
        except FileNotFoundError:
            self.fail("File not found: " + self.pad)
        return []

    def execute_mode(self):
        self.state = State.Execute
        return []

    def begin_definition(self):
        self.val = Definition(self.pad)
        return []

    def compile_mode(self):
        self.state = State.Compile
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
            self.memory += array(self.memory.typecode, extra*[0])
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

    def trace(self):
        self.read_word()
        token = self.pad.upper()
        if token not in self.names.keys():
            raise RuntimeError("Undefined word: " + token)
        lin, lout, _, _ = self.dictionary[self.names[token]]
        return [lin, lout]

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

    def postpone(self):
        self.read_word()
        name = self.pad
        if name in self.names.keys():
            self.compile_call(name)
        else:
            number = self.number_or_fail(name)
            self.compile_literal(number)
        return []

    def compile_literal(self, value):
        self.val.lit(value)
        return []

    def compile_call(self, token):
        index = self.names[token]
        callee = self.dictionary[index]
        self.val.call(index, callee)
        return []

    def compile_ret(self):
        self.val.ret()

    def resolve_word_compile(self, token):
        if token in self.names.keys():
            speed = self.speeds[token]
            match speed:
                case Speed.Normal:
                    self.compile_call(token)
                case Speed.Immediate:
                    self.execute_valid_token(token)
        else:
            number = self.number_or_fail(token)
            self.compile_literal(number)

    def end_definition(self, im=False):
        self.compile_ret()
        name, entry = self.val.end()
        try:
            index = self.dictionary.index(entry)
            self.names[name] = index
        except Exception:
            self.names[name] = len(self.dictionary)
            self.dictionary.append(entry)
            self.lengths.append(len(self.val.body))
        finally:
            self.speeds[name] = Speed.Immediate if im else Speed.Normal

    def end_compile(self, im=False, reduce1=False):
        name = self.val.name
        if not self.silent and name in self.names.keys():
            print(name + " is redefined")
        body = self.val.body
        if (reduce1 and len(body) == 1):
            object_type, object = body[0]
            match object_type:
                case Object.Literal:
                    self.end_definition(im=im)
                case Object.Word:
                    self.names[name] = object
                    self.speeds[name] = Speed.Immediate if im else Speed.Normal
        else:
            self.end_definition(im=im)
        self.reset_state(data=False)
        return []

    def number_or_fail(self, token):
        base = self.memory[0]
        if len(token) > 0 and token[0] == "#":
            base = 10
            token = token[1:]
        try:
            number = int(token, base=base)
            return number
        except Exception:
            self.fail("Undefined word: " + token)

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
                    self.data = rest + array(rest.typecode, new)
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

    def skip(self, char, fail=None):
        try:
            index = self.input_buffer.index(char)
        except Exception:
            if fail is None:
                index = len(self.input_buffer)
            else:
                self.fail("Incomplete " + fail + " comment")
        self.input_buffer = self.input_buffer[index + 1:]
        return

    def pop_token(self):
        res = self.input_buffer.split(maxsplit=1)
        if len(res) == 1:
            self.input_buffer = ""
        else:
            self.input_buffer = res[1]
        return res[0].upper()

    def do(self, str):
        self.input_buffer = str
        self.input_buffer = self.input_buffer.strip()
        while len(self.input_buffer) > 0:
            self.read_word()
            token = self.pad
            if token == "(":
                self.skip(")", "(")
                continue
            if token == "\\":
                self.skip("\n")
                continue
            match self.state:
                case State.Execute:
                    if token in self.names.keys():
                        self.execute_valid_token(token)
                    else:
                        number = self.number_or_fail(token)
                        self.data.append(number)
                case State.Compile:
                    self.resolve_word_compile(token)
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
f.do(": tst over dup -rot + ; trace tst")
assert f.S() == [2, 3]
f.do("drop drop")
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
assert f.names["A"] == f.names["B"]
del f

# if a defined word just calls a single other word,
# it just takes the same body, if ;r is used
f = Forth(True)
f.do(": add + ;r")
assert f.names["ADD"] == f.names["+"]
del f

# is case-insensitive
f = Forth(True)
try:
    f.do("1 DrOp")
    assert f.S() == []
finally:
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
start = f.names["A"]
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
f.do(": tst ( n n -- n ) + ;r")
assert f.names["TST"] == f.names["+"]
del f

# cannot take comment before defined word name
f = Forth(True)
try:
    f.do(": ( same as plus ) tst + ;")
except Exception:
    pass
else:
    raise AssertionError("( before word name in definition does not fail")
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

# can use return stack for co-routines
f = Forth(True)
try:
    f.do(": ;: >r ;")
    f.do(": callee 2 r> ;: 4 ;")
    f.do(": caller 1 callee 3 ;")
    f.do("caller")
    assert f.S() == [1, 2, 3, 4]
finally:
    del f
f = Forth(True)
try:
    f.do(": yield r> r> swap >r >r ;")
    f.do(": callee 2 yield 4 ;")
    f.do(": caller 1 callee 3 yield 5 ;")
    f.do("caller")
    assert f.S() == [1, 2, 3, 4, 5]
finally:
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

# can compile immediate words
f = Forth(True)
f.do(": tst 1 + ;im 3 : tst2 tst literal ; tst2")
assert f.S() == [4]
del f

# can use postpose to compile immediate words
f = Forth(True)
f.do(": tst 1 + ;im : tst2 3 postpone tst ; tst2")
assert f.S() == [4]
del f

# can postpone literals
f = Forth(True)
f.do(": tst postpone 1 ; tst")
assert f.S() == [1]
del f

# keeps simple postponed callers of immediate words non-immediate
f = Forth(True)
f.do(": tst-im 1 + ;im")
f.do(": tst-non postpone tst-im ;r")
try:
    assert f.names["TST-NON"] == f.names["TST-IM"]
    f.do(": tst 4 tst-non ;")
    f.do("tst")
    assert f.S() == [5]
finally:
    del f

# keeps simple copies of immediate words non-immediate
f = Forth(True)
f.do(": tst-im 1 + ;im")
f.do(": tst-non 1 + ;")
try:
    assert f.names["TST-NON"] == f.names["TST-IM"]
    f.do(": tst 4 tst-non ;")
    f.do("tst")
    assert f.S() == [5]
finally:
    del f

# keeps immediate callers of non-immediate words immediate
f = Forth(True)
f.do(": tst-non 1 + ;")
f.do(": tst-im tst-non ;imr")
try:
    assert f.names["TST-NON"] == f.names["TST-IM"]
    f.do("4 : tst tst-im literal ;")
    f.do("tst")
    assert f.S() == [5]
finally:
    del f

# keeps immediate copies of non-immediate words immediate
f = Forth(True)
f.do(": tst-non 1 + ;")
f.do(": tst-im 1 + ;im")
try:
    assert f.names["TST-NON"] == f.names["TST-IM"]
    f.do("4 : tst tst-im literal ;")
    f.do("tst")
    assert f.S() == [5]
finally:
    del f

# can include files
file = tempfile(delete=False)
file.write(b': tst 1 + ;\n: tst2 tst tst ;')
file.close()
f = Forth(True)
try:
    f.do("include " + file.name)
    f.do("3 tst2")
    assert f.S() == [5]
finally:
    del file
    del f

# can take #n, for decimal number n, as a literal if #n isn't a defined word
f = Forth(True)
try:
    f.do("16 base ! #100")
    assert f.S() == [100]
finally:
    del f

# can use binary, decimal, and hex for common bases
f = Forth(True)
try:
    f.do("binary 1010 hex A decimal 10")
    assert f.S() == [10, 10, 10]
finally:
    del f

# can retrieve a defined word's stack effect ( -- in out )
f = Forth(True)
try:
    f.do("trace = trace hex")
    assert f.S() == [2, 1, 0, 0]
finally:
    del f

# can pick a cell size in 1, 2, 4, 8 bytes; CELL returns this size
try:
    f = Forth(True, cell=1)
    assert f.data.typecode == 'b'
    f.do("cell")
    f.S() == 1
    del f
except Exception:
    raise
try:
    f = Forth(True, cell=2)
    assert f.data.typecode == 'h'
    f.do("cell")
    f.S() == 2
    del f
except Exception:
    raise
try:
    f = Forth(True, cell=4)
    assert f.data.typecode == 'l'
    f.do("cell")
    f.S() == 4
    del f
except Exception:
    raise
try:
    f = Forth(True, cell=8)
    assert f.data.typecode == 'q'
    f.do("cell")
    f.S() == 8
    del f
except Exception:
    raise
try:
    f = Forth(True, cell=7)
    del f
    raise AssertionError("Forth(cell = 7) doesn't fail")
except Exception:
    pass
