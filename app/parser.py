# Copyright 2016 The ci_edit Authors. All rights reserved.
# Use of this source code is governed by an Apache-style license that can be
# found in the LICENSE file.

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
    self.begin = None

  def debugLog(self, out, indent, data):
    out('%sParserNode %16s %4d %s' % (indent, self.grammar['name'], self.begin,
        repr(data[self.begin:self.begin+15])[1:-1]))


class Parser:
  """A parser generates a set of grammar segments (ParserNode objects)."""
  def __init__(self):
    self.data = ""
    self.grammarPrefs = app.prefs.prefs['grammar']
    self.grammarList = []
    app.log.parser('__init__')

  def parse(self, data, grammar):
    app.log.parser('grammar', grammar['name'])
    self.data = data
    node = ParserNode()
    node.grammar = grammar
    node.begin = 0
    self.grammarList = [node]
    startTime = time.time()
    self.findChildren()
    totalTime = time.time() - startTime
    self.debugLog(app.log.parser, data)
    app.log.startup('parsing took', totalTime)

  def findChildren(self):
    cursor = 0
    app.log.parser('node', self.grammarList[-1].grammar['name'])
    grammarStack = [self.grammarList[-1].grammar]
    while len(grammarStack):
      subdata = self.data[cursor:]
      app.log.parser(grammarStack[-1]['name'], 'subdata@@', repr(subdata)[:40])
      found = grammarStack[-1].get('matchRe').search(subdata)
      if not found:
        app.log.parser(grammarStack[-1]['name'], 'not found')
        app.log.parser(grammarStack[-1]['name'], 'grammarStack will pop', len(grammarStack))
        for i in grammarStack:
          app.log.parser(grammarStack[-1]['name'], '  ', i['name'])
        grammarStack.pop()
        continue
      app.log.parser(grammarStack[-1]['name'], 'found regs', found.regs)
      app.log.parser(grammarStack[-1]['name'], 'found groups', found.groups())
      index = -1
      for i,k in enumerate(found.groups()):
        if k is not None:
          index = i
          break
      assert index >= 0
      child = ParserNode()
      if index == 0:
        if 0:
                  app.log.parser(grammarStack[-1]['name'], 'we found end of grammar ')
                  app.log.parser(grammarStack[-1]['name'], 'grammarStack will pop', len(grammarStack))
                  for i in grammarStack:
                    app.log.parser(grammarStack[-1]['name'], '  ', i['name'])
        grammarStack.pop()
        child.grammar = grammarStack[-1]
        child.begin = cursor + found.regs[index+1][1]
        cursor = child.begin
        app.log.parser('ended cursor', cursor)
      else:
        app.log.parser(grammarStack[-1]['name'], 'index >= 0')
        reg = found.regs[index+1]
        child.grammar = grammarStack[-1].get('matchGrammars', [])[index]
        child.begin = cursor + found.regs[index+1][0]
        cursor += found.regs[index+1][1]
        app.log.parser('contents cursor', cursor)
        grammarStack.append(child.grammar)
        if 0:
                  app.log.parser(grammarStack[-1]['name'], 'grammarStack after append', len(grammarStack))
                  for i in grammarStack:
                    app.log.parser(grammarStack[-1]['name'], '  ', i['name'])
      if len(self.grammarList) and self.grammarList[-1].begin == child.begin:
        self.grammarList[-1] = child
      else:
        self.grammarList.append(child)

  def debugLog(self, out, data):
    out('parser debug:')
    for node in self.grammarList:
      node.debugLog(out, '  ', data)




