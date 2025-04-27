# FPython

FPython is a personal project for learning Python, by implementing a crude Forth.
This is currently a single-file project, with simple tests included alongside function/class definitions.

## Features

The main Forth() class is used to contain the state of the Forth session, including the data stack.

The defined words are stored with their expected minimum input stack size, and relative output stack size.
Later, this will be used to infer the same information for words defined by the user.
