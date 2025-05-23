# FPython

FPython is a personal project for learning Python, by implementing a crude Forth.\
This is currently a single-file project, with simple tests included alongside function/class definitions.

## Features

The main Forth() class is used to contain the state of the Forth session, including the data stack.\
Optionally, a session can be silent, i.e. not printing any output or prompts.\
This is mostly intended for making the tests silent.

As usual, Forth code is case-insensitive.\
The interpreter does the traditional approach of trying to match a token to a defined word, then trying to make it a number in the current base.\
Borrowing from VFXForth, you can also write `#n`, where `n` is some number: this parses `n` as a number in base 10, regardless of the current base.\
The current base is stored at `base`, and `binary`, `decimal`, and `hex` set common bases, as usual.

By default, the data and return stacks, and the "memory", are stored as arrays of 4-byte-minimum-size integers (`'l'`).\
When creating the Forth() object, the cells argument lets you also choose 1-, 2-, or 8-byte sizes ('b', 'l', 'q').\
`cell` puts the selected size on the stack, as usual.
True values are done as 1 rather than -1, because Python's arbitrary-precision integers make it difficult to do anything that depends on a particular integer length or bit layout.\
All non-zero values will be counted as true in conditions, as usual.

Printing the data stack is currently a dedicated Forth class method.\
I'll change this later to be a word within the Forth.

Execution makes use of a return stack, and you can use `>r` and `r>` inside words (not on the top level yet).

Both stacks are emptied on failure, as usual.

Words are stored with their expected minimum input stack size, and relative output stack size.\
This is also done for words defined by the user, and done by making use of the same information for the words it calls.\
If I ever let users define new "basic" words (equivalent to Forth letting words be written in Assembly), then I'd need to think about how to handle it there.\
`trace [word]` can be used to put `[word]`'s stack effect information on the stack.\
When words are executed, the input stack and output are checked against this information.\
For compound words, called words are not themselves checked, because their stack conditions are already satisfied when calculating the conditions for the calling word.\
It can also handle `postpone`, to compile calls to immediate words. `postpone` on a number does nothing.

The name of a word is kept separate from the definition/body.\
This means that words with the same definition all point to the same definition, so the names are really just current aliases.\
This is something I saw being done for the Unison language, which stores the code base in a permanent database, and compiles called words as direct hashes instead of using their given name.\
Outside of these details, Unison function code storage screamed "modern take on a Forth dictionary" to me, so I'm putting it in this Forth.\
Compile-time execution is done using `[` and `]`, as usual.

There are some alternative semicolons.\
`;im` marks the defined word as immediate.\
`;r` checks whether the word is a reference: if it calls another word, then returns, then it is compiled as an alias for that word instead.\
This also means, for example, that `: + + ;r` and `: add + ;r : + add ;r` leave `+` with its original definition, instead of adding layers of indirection.\
Note that a word being an alias of a second word, instead of calling it, has different effects for what goes on the return stack, so keep that in mind if you're doing return stack manipulation.\
`;imr` combines the two.

The orphans method shows which definitions are neither called by other words, nor currently assigned an alias.\
"Called by other words" includes calling itself, which isn't quite right, but there's currently no way to define a word as calling itself.\
The plan for this method is as part of allowing the user to ask the session to prune its dictionary.

`here`, `,` "place", `@` ("fetch"), and `!` ("store") work as normal.\
`create` currently only works at run time.
`create` works a little differently to normal: it doesn't assign any memory.\
The value of `here` is therefore unchanged, and consecutive `create` calls point to the same memory position.\
As with words, the idea is to keep names/aliases and contents separate.

Both `( ... )` and `\ ... \n` styles of comments are supported. This assumes that '\n' is the computer's newline character.

`base` is implemented, to let input/output use a base different to 10. There's nothing stopping you from giving a base outside of the expected range [2, 36], but doing so will give you odd behaviour, or just result in an error.\
`decimal`, `hex`, and `binary` for setting common bases are not added yet.
