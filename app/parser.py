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
    #self.end = 0

  def debugLog(self, out, indent, data):
    out('%sParserNode %12s %4d %s' % (indent, self.grammar['name'], self.begin,
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
    #self.grammar.end = len(self.data)
    startTime = time.time()
    self.findChildren()
    totalTime = time.time() - startTime
    self.debugLog(app.log.parser, data)
    app.log.startup('parsing took', totalTime)

  def findChildren(self):


    limit = 300




    cursor = 0
    app.log.parser('node', self.grammarList[-1].grammar['name'])
    grammarStack = [self.grammarList[-1].grammar]
    while len(grammarStack):
      limit -= 1
      if limit < 0:
        app.log.parser('hit debug limit')
        return
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
      if grammarStack[-1].get('end') and index == 0:
        app.log.parser(grammarStack[-1]['name'], 'we found end of grammar ')
        app.log.parser(grammarStack[-1]['name'], 'grammarStack will pop', len(grammarStack))
        for i in grammarStack:
          app.log.parser(grammarStack[-1]['name'], '  ', i['name'])
        grammarStack.pop()
        child = ParserNode()
        child.grammar = grammarStack[-1]
        child.begin = cursor + found.regs[index+1][1]
        cursor = child.begin
        app.log.parser('ended cursor', cursor)
        if len(self.grammarList) and self.grammarList[-1].begin == child.begin:
          self.grammarList[-1] = child
        else:
          self.grammarList.append(child)
      elif index >= 0:
        app.log.parser(grammarStack[-1]['name'], 'index >= 0')
        reg = found.regs[index+1]
        child = ParserNode()
        child.grammar = grammarStack[-1].get('matchGrammars', [])[index]
        child.begin = cursor + found.regs[index+1][0]
        cursor += found.regs[index+1][1]
        app.log.parser('contents cursor', cursor)
        if len(self.grammarList) and self.grammarList[-1].begin == child.begin:
          self.grammarList[-1] = child
        else:
          self.grammarList.append(child)
        grammarStack.append(child.grammar)
        app.log.parser(grammarStack[-1]['name'], 'grammarStack after append', len(grammarStack))
        for i in grammarStack:
          app.log.parser(grammarStack[-1]['name'], '  ', i['name'])
      else:
        app.log.parser(grammarStack[-1]['name'], 'grammar get else')

  def xfindChildren(self, node):
    app.log.info('node', node)
    starts = []
    for grammarName in node.grammar.get('contains', []):
      starts.append(self.grammarPrefs[grammarName]['begin'])
    app.log.info('starts', starts)
    if not len(starts):
      return
    regex = r"|".join(starts)
    app.log.info('regex', regex)
    beginRe = re.compile(regex)
    subdata = self.data[node.begin:node.end]
    app.log.info('subdata', subdata)
    found = beginRe.search(subdata)
    app.log.info('found', found.regs)
    if found:
      node.end = found.regs[0][0]
      child = ParserNode()
      child.grammar = self.grammarPrefs['py']
      child.begin = found.regs[0][0]
      child.end = found.regs[0][1]
      node.next = child
      self.findChildren(child)

  def debugLog(self, out, data):
    out('parser debug:')
    for node in self.grammarList:
      node.debugLog(out, '  ', data)




