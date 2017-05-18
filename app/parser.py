# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import app.log
import app.selectable
import app.prefs
import third_party.pyperclip as clipboard
import curses.ascii
import os
import re
import sys
import time
import traceback


class ParserNode:
  """A parser node represents a span of grammar. i.e. from this point to that
      point is HTML. Another parser node would represent the next segment, of
      grammar (maybe JavaScript, CSS, comment, or quoted string for example."""
  def __init__(self):
    self.grammar = None
    self.begin = None  # Offset from start of file.
    self.col = None  # Offset from start of line.
    self.note = ''

  def debugLog(self, out, indent, data):
    out('%sParserNode %16s %4d %4d %s' % (indent, self.grammar.get('name', 'None'),
        self.begin, self.col, repr(data[self.begin:self.begin+15])[1:-1]), self.note)


class Parser:
  """A parser generates a set of grammar segments (ParserNode objects)."""
  def __init__(self):
    self.data = ""
    self.grammarPrefs = app.prefs.prefs['grammar']
    self.grammarList = []
    self.grammarRowList = []
    app.log.parser('__init__')

  def grammarFromRowCol(self, row, offset):
    sentinel = ParserNode()
    sentinel.grammar = {}
    sentinel.begin = sys.maxint
    sentinel.col = sys.maxint
    app.log.info(len(self.grammarRowList))
    gl = self.grammarRowList[row] + [sentinel]
    low = 0
    high = len(gl)-1
    while True:
      index = (high+low)/2
      if offset >= gl[index+1].col:
        low = index
      elif offset < gl[index].col:
        high = index
      else:
        return gl[index], gl[index+1].col-offset

  def grammarFromOffset(self, offset):
    gl = self.grammarList
    low = 0
    high = len(gl)-1
    while True:
      index = (high+low)/2
      if offset >= gl[index+1].begin:
        low = index
      elif offset < gl[index].begin:
        high = index
      else:
        return gl[index], gl[index+1].begin-offset

  def parse(self, data, grammar):
    app.log.parser('grammar', grammar['name'])
    self.data = data
    node = ParserNode()
    node.grammar = grammar
    node.begin = 0
    node.col = 0
    self.grammarList = [node]
    self.grammarRowList = [[node]]
    startTime = time.time()
    self.buildGrammarList()
    totalTime = time.time() - startTime
    if app.log.enabledChannels.get('parser', False):
      self.debugLog(app.log.parser, data)
    app.log.startup('parsing took', totalTime)

  def buildGrammarList(self):
    # An arbitrary limit to avoid run-away looping.
    leash = 100000
    cursor = 0
    cursorRowStart = 0
    grammarStack = [self.grammarList[-1].grammar]
    while len(grammarStack):
      if not leash:
        app.log.error('grammar likely caught in a loop')
        break
      leash -= 1
      subdata = self.data[cursor:]
      found = grammarStack[-1].get('matchRe').search(subdata)
      if not found:
        grammarStack.pop()
        # todo(dschuyler): mark parent grammars as unterminated (if they expect
        # be terminated. e.g. unmatched string quote or xml tag.
        break
      index = -1
      for i,k in enumerate(found.groups()):
        if k is not None:
          index = i
          break
      assert index >= 0
      reg = found.regs[index+1]
      if index == 0:
        # Found escaped value.
        cursor += reg[1]
        continue
      child = ParserNode()
      if index == len(found.groups()) - 1:
        # Found new line.
        child.grammar = grammarStack[-1]
        child.begin = cursor + reg[1]
        child.col = 0
        cursor = child.begin
        cursorRowStart = child.begin
        self.grammarRowList.append([])
      elif index == 1:
        # Found end of current grammar section (an 'end').
        grammarStack.pop()
        child.grammar = grammarStack[-1]
        child.begin = cursor + reg[1]
        child.col = cursor + reg[1] - cursorRowStart
        cursor = child.begin
        if subdata[reg[0]:reg[1]] == '\n':
          child.col = 0
          cursorRowStart = child.begin
          self.grammarRowList.append([])
      else:
        # A new grammar within this grammar (a 'contains').
        child.grammar = grammarStack[-1].get('matchGrammars', [])[index]
        child.begin = cursor + reg[0]
        child.col = cursor + reg[0] - cursorRowStart
        cursor += reg[1]
        grammarStack.append(child.grammar)
      if len(self.grammarList) and self.grammarList[-1].begin == child.begin:
        child.note = 'replacing row %d' % (len(self.grammarRowList),)
        self.grammarList[-1] = child
        self.grammarRowList[-1][-1] = child
      else:
        child.note = 'appending row %d' % (len(self.grammarRowList),)
        self.grammarList.append(child)
        self.grammarRowList[-1].append(child)
    sentinel = ParserNode()
    sentinel.grammar = {}
    sentinel.begin = sys.maxint
    sentinel.col = sys.maxint
    self.grammarList.append(sentinel)

  def debugLog(self, out, data):
    out('parser debug:')
    out('grammarList ----------------', len(self.grammarList))
    for node in self.grammarList:
      node.debugLog(out, '  ', data)
    out('RowList ----------------', len(self.grammarRowList))
    for i,rowList in enumerate(self.grammarRowList):
      out('row', i+1)
      for node in rowList:
        if node is None:
          out('a None')
          continue
        node.debugLog(out, '  ', data)

