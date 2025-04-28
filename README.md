# FPython

FPython is a personal project for learning Python, by implementing a crude Forth.\
This is currently a single-file project, with simple tests included alongside function/class definitions.

## Features

The main Forth() class is used to contain the state of the Forth session, including the data stack.\
Optionally, a session can be silent, i.e. not printing any output or prompts.\
This is mostly intended for making the tests silent.

The data stack, and the "memory", are stored as arrays of 1-byte-minimum-size integers (`'b'`).\
True values are done as 1 rather than -1, because Python's arbitrary-precision integers make it difficult to do anything that depends on a particular integer length or bit layout.\
All non-zero values will be counted as true in conditions, as usual.

Printing the data stack is currently a dedicated Forth class method.\
I'll change this later to be a word within the Forth.

Execution makes use of a return stack, and you can use `>r` and `r>` inside words (not on the top level yet).

Both stacks are emptied on failure, as usual.

Words are stored with their expected minimum input stack size, and relative output stack size.\
This is also done for words defined by the user, and done by making use of the same information for the words it calls.\
If I ever let users define new "basic" words (equivalent to Forth letting words be written in Assembly), then I'd need to think about how to handle it there.\
When words are executed, the input stack and output are checked against this information.\
For compound words, called words are not themselves checked, because their stack conditions are already satisfied when calculating the conditions for the calling word.

The name of a word is kept separate from the definition/body.\
This means that words with the same definition all point to the same definition, so the names are really just current aliases.\
This is something I saw being done for the Unison language, which stores the code base in a permanent database, and compiles called words as direct hashes instead of using their given name.\
Outside of these details, Unison function code storage screamed "modern take on a Forth dictionary" to me, so I'm putting it in this Forth.\
If a word is defined as just calling a second word, then it's compiled as an alias of that word.\
This allows aliases to be assigned to existing base words.\
It also means, for example, that we can write\
`: + + ;`\
or\
`: add + ; : + add ;`\
and have `+` end up with its original definition, instead of adding unnecessary layers of indirection.\
Compile-time execution is done using `[` and `]`, as usual.

The orphans method shows which definitions are neither called by other words, nor currently assigned an alias.\
"Called by other words" includes calling itself, which isn't quite right, but there's currently no way to define a word as calling itself.\
The plan for this method is as part of allowing the user to ask the session to prune its dictionary.

`here`, `,` "place", `@` ("fetch"), and `!` ("store") work as normal.\
`create` currently only works at run time.
`create` works a little differently to normal: it doesn't assign any memory.\
The value of `here` is therefore unchanged, and consecutive `create` calls point to the same memory position.\
As with words, the idea is to keep names/aliases and contents separate.

Only the `( ... )` style of comments is supported, because I don't want to make around with device-dependents issues like how to end a line.
