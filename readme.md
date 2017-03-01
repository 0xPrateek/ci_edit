## The ci text editor

The world does need another text editor.

There are other fine curses based editors. I found that I was often trying to
tweak them to get just what I wanted. Almost as often, some dark piece of those
editors prevented that last little bit of customization. Writing a text editor
is an interesting project.

This version of ci_edit still doesn't have all the intended features, but it's
a start.

Features of ci

- runs on nCurses
- syntax highlighting
- find within text
- line numbers
- goto line
- cut/copy/paste
- unlimited undo/redo
- file path tab-completion
- written in Python
- select by line, character, or all
- brace matching
- mouse support
- pipe to editor
- nested grammars
- resume at last edit position
- search and replace

Future features (todo)

- bookmarks
- find in files
- spell check
- user customizable keywords
- user customizable color scheme
- build/error tracking
- auto reload of modified files
- trace file
- jump to opposing brace
- saved undo/redo
- a lot more...

Copyright 2016 The ci_edit Authors. All rights reserved.
Use of this source code is governed by an Apache-style license that can be
found in the LICENSE file.
