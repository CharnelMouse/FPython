# FPython

FPython is a personal project for learning Python, by implementing a crude Forth.
This is currently a single-file project, with simple tests included alongside function/class definitions.

## Features

The main Forth() class is used to contain the state of the Forth session, including the data stack.
Optionally, a session can be silent, i.e. not printing any output or prompts.
This is mostly intended for making the tests silent.

Printing the data stack is currently a dedicated Forth class method.
I'll change this later to be a word within the Forth.

Words are stored with their expected minimum input stack size, and relative output stack size.
This is also done for words defined by the user, and done by making use of the same information for the words it calls.
If I ever let users define new "basic" words (equivalent to Forth letting words be written in Assembly),
then I'd need to think about how to handle it there.
When words are executed, the input stack and output are checked against this information.
For compound words, called words are not themselves checked, because their stack conditions
are already satisfied when calculating the conditions for the calling word.

The name of a word is kept separate from the definition/body.
This means that words with the same definition all point to the same definition, so the names are really just current aliases.
This is something I saw being done for the Unison language, which stores the code base in a permanent database, and compiles called words as direct hashes instead of using their given name.
Outside of these details, Unison function code storage screamed "modern take on a Forth dictionary" to me, so I'm putting it in this Forth.
If a word is defined as just calling a second word, then it's compiled as an alias of that word.
This allows aliases to be assigned to existing base words.
It also means, for example, that we can write
`: + + ;`
or
`: add + ; : + add ;`
and have `+` end up with its original definition, instead of adding unnecessary layers of indirection.
Compile-time execution is done using `[` and `]`, as usual.
