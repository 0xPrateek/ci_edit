# Copyright 2016 The ci_edit Authors. All rights reserved.
# Use of this source code is governed by an Apache-style license that can be
# found in the LICENSE file.

import app.buffer_manager
import app.log
import app.history
import app.parser
import app.prefs
import app.selectable
import third_party.pyperclip as clipboard
import curses.ascii
import difflib
import os
import re
import sys
import traceback


def addVectors(a, b):
  """Add two list-like objects, pair-wise."""
  return tuple([a[i]+b[i] for i in range(len(a))])


class Mutator(app.selectable.Selectable):
  """Track changes to a body of text."""
  def __init__(self):
    app.selectable.Selectable.__init__(self)
    self.debugRedo = False
    self.findRe = None
    self.findBackRe = None
    self.fileExtension = ''
    self.fullPath = ''
    self.cursorGrammar = None
    self.parser = None
    self.relativePath = ''
    self.scrollRow = 0
    self.scrollToRow = 0
    self.scrollCol = 0
    self.redoChain = []
    self.redoIndex = 0
    self.savedAtRedoIndex = 0
    self.shouldReparse = False

  def addLine(self, msg):
    """Direct manipulator for logging to a read-only buffer."""
    self.lines.append(msg)
    self.cursorRow += 1

  def getCursorOffset(self, row, col):
    """inefficent test hack. wip on parser"""
    offset = 0
    for i in range(row):
      offset += len(self.lines[i])
    return offset + row + col

  def cursorGrammarName(self):
    """inefficent test hack. wip on parser"""
    if not self.parser:
      return 'no parser'
    self.cursorGrammar = self.parser.grammarFromOffset(self.getCursorOffset(
        self.cursorRow, self.cursorCol))[0]
    if self.cursorGrammar is None:
      return 'None'
    return self.cursorGrammar.grammar.get('name', 'unknown')

  def cursorGrammarRemaining(self):
    """inefficent test hack. wip on parser"""
    if not self.parser:
      return -2
    remaining = self.parser.grammarFromOffset(self.getCursorOffset(
        self.cursorRow, self.cursorCol))[1]
    if remaining is None:
      return -1
    return remaining

  def isDirty(self):
    """Whether the buffer contains non-trival changes since the last save."""
    clean = self.savedAtRedoIndex >= 0 and (
        self.savedAtRedoIndex == self.redoIndex or
        (self.redoIndex + 1 == self.savedAtRedoIndex and
          self.redoChain[self.redoIndex][0] == 'm') or
        (self.redoIndex - 1 == self.savedAtRedoIndex and
          self.redoChain[self.redoIndex-1][0] == 'm'))
    return not clean

  def isSafeToWrite(self):
    if not os.path.exists(self.fullPath):
      return True
    s1 = os.stat(self.fullPath)
    s2 = self.fileStat
    app.log.info('st_mode', s1.st_mode, s2.st_mode)
    app.log.info('st_ino', s1.st_ino, s2.st_ino)
    app.log.info('st_dev', s1.st_dev, s2.st_dev)
    app.log.info('st_uid', s1.st_uid, s2.st_uid)
    app.log.info('st_gid', s1.st_gid, s2.st_gid)
    app.log.info('st_size', s1.st_size, s2.st_size)
    app.log.info('st_mtime', s1.st_mtime, s2.st_mtime)
    app.log.info('st_ctime', s1.st_ctime, s2.st_ctime)
    return (s1.st_mode == s2.st_mode and
        s1.st_ino == s2.st_ino and
        s1.st_dev == s2.st_dev and
        s1.st_uid == s2.st_uid and
        s1.st_gid == s2.st_gid and
        s1.st_size == s2.st_size and
        s1.st_mtime == s2.st_mtime and
        s1.st_ctime == s2.st_ctime)

  def redo(self):
    """Replay the next action on the redoChain."""
    if self.redoIndex < len(self.redoChain):
      change = self.redoChain[self.redoIndex]
      if self.debugRedo:
        app.log.info('redo', self.redoIndex, repr(change))
      if change[0] != 'm':
        self.shouldReparse = True
      self.redoIndex += 1
      if change[0] == 'b':
        line = self.lines[self.cursorRow]
        self.cursorCol -= len(change[1])
        x = self.cursorCol
        self.lines[self.cursorRow] = line[:x] + line[x+len(change[1]):]
      elif change[0] == 'd':
        line = self.lines[self.cursorRow]
        x = self.cursorCol
        self.lines[self.cursorRow] = line[:x] + line[x+len(change[1]):]
      elif change[0] == 'dr':  # Redo delete range.
        self.doDelete(*change[1])
      elif change[0] == 'ds':  # Redo delete selection.
        self.doDeleteSelection()
      elif change[0] == 'i':  # Redo insert.
        line = self.lines[self.cursorRow]
        x = self.cursorCol
        self.lines[self.cursorRow] = line[:x] + change[1] + line[x:]
        self.cursorCol += len(change[1])
        self.goalCol = self.cursorCol
      elif change[0] == 'j':  # Redo join lines.
        self.lines[self.cursorRow] += self.lines[self.cursorRow+1]
        del self.lines[self.cursorRow+1]
      elif change[0] == 'ld':  # Redo line diff.
        lines = []
        index = 0
        for ii in change[1]:
          if type(ii) is type(0):
            for line in self.lines[index:index+ii]:
              lines.append(line)
            index += ii
          elif ii[0] == '+':
            lines.append(ii[2:])
          elif ii[0] == '-':
            index += 1
        app.log.info('ld', self.lines == lines)
        self.lines = lines
      elif change[0] == 'm':  # Redo move
        assert self.cursorRow+change[1][0] >= 0, "%s %s"%(self.cursorRow, change[1][0])
        assert self.cursorCol+change[1][1] >= 0, "%s %s"%(self.cursorCol, change[1][1])
        assert self.scrollRow+change[1][3] >= 0, "%s %s"%(self.scrollRow, change[1][3])
        assert self.scrollCol+change[1][4] >= 0, "%s %s"%(self.scrollCol, change[1][4])
        self.cursorRow += change[1][0]
        self.cursorCol += change[1][1]
        self.goalCol += change[1][2]
        self.scrollRow += change[1][3]
        self.scrollCol += change[1][4]
        self.markerRow += change[1][5]
        self.markerCol += change[1][6]
        self.markerEndRow += change[1][7]
        self.markerEndCol += change[1][8]
        self.selectionMode += change[1][9]
      elif change[0] == 'n':
        # Redo split lines.
        line = self.lines[self.cursorRow]
        self.lines.insert(self.cursorRow+1, line[self.cursorCol:])
        self.lines[self.cursorRow] = line[:self.cursorCol]
        for i in range(max(change[1][0] - 1, 0)):
          self.lines.insert(self.cursorRow+1, "")
      elif change[0] == 'v':  # Redo paste.
        self.insertLines(change[1])
      elif change[0] == 'vb':
        self.cursorCol -= len(change[1])
        row = min(self.markerRow, self.cursorRow)
        rowEnd = max(self.markerRow, self.cursorRow)
        for i in range(row, rowEnd+1):
          line = self.lines[i]
          x = self.cursorCol
          self.lines[self.cursorRow] = line[:x] + line[x+len(change[1]):]
      elif change[0] == 'vd':  # Redo vertical delete.
        upperRow = min(self.markerRow, self.cursorRow)
        lowerRow = max(self.markerRow, self.cursorRow)
        x = self.cursorCol
        for i in range(upperRow, lowerRow+1):
          line = self.lines[i]
          self.lines[i] = line[:x] + line[x+len(change[1]):]
      elif change[0] == 'vi':  # Redo vertical insert.
        text = change[1]
        col = self.cursorCol
        row = min(self.markerRow, self.cursorRow)
        rowEnd = max(self.markerRow, self.cursorRow)
        app.log.info('do vi')
        for i in range(row, rowEnd+1):
          line = self.lines[i]
          self.lines[i] = line[:col] + text + line[col:]
      else:
        app.log.info('ERROR: unknown redo.')
    # Redo again if there is a move next.
    if (self.redoIndex < len(self.redoChain) and
        self.redoChain[self.redoIndex][0] == 'm'):
      self.redo()

  def redoAddChange(self, change):
    """Push a change onto the end of the redoChain. Call redo() to enact the
        change."""
    if self.debugRedo:
      app.log.info('redoAddChange', change)
    # When the redoChain is trimmed we may lose the saved at.
    if self.redoIndex < self.savedAtRedoIndex:
      self.savedAtRedoIndex = -1
    self.redoChain = self.redoChain[:self.redoIndex]
    if 1: # optimizer
      if len(self.redoChain) and self.savedAtRedoIndex != self.redoIndex:
        if (self.redoChain[-1][0] == change[0] and
            change[0] in ('d', 'i')):
          change = (change[0], self.redoChain[-1][1] + change[1])
          self.undoOne()
          self.redoChain.pop()
        elif change[0] == 'm':
          if self.redoChain[-1][0] == 'm':
            change = (change[0], addVectors(self.redoChain[-1][1], change[1]))
            self.undoOne()
            self.redoChain.pop()
        elif self.redoChain[-1][0] == change[0] and change[0] == 'n':
          change = (change[0], addVectors(self.redoChain[-1][1], change[1]))
          self.undoOne()
          self.redoChain.pop()
    if 1:
      # Eliminate no-op entries
      noOpInstructions = set([
        ('m', (0,0,0,0,0,0,0,0,0,0)),
      ])
      assert ('m', (0,0,0,0,0,0,0,0,0,0)) in noOpInstructions
      if change in noOpInstructions:
        return
      #app.log.info('opti', change)
    self.redoChain.append(change)
    if self.debugRedo:
      app.log.info('--- redoIndex', self.redoIndex)
      for i,c in enumerate(self.redoChain):
        app.log.info('%2d:'%i, repr(c))

  def undo(self):
    """Undo a set of redo nodes."""
    while self.undoOne():
      pass

  def undoOne(self):
    """Undo the most recent change to the buffer.
    return whether undo should be repeated."""
    app.log.detail('undo')
    if self.redoIndex > 0:
      self.redoIndex -= 1
      change = self.redoChain[self.redoIndex]
      if change[0] != 'm':
        self.shouldReparse = True
      if self.debugRedo:
        app.log.info('undo', self.redoIndex, repr(change))
      if change[0] == 'b':
        line = self.lines[self.cursorRow]
        x = self.cursorCol
        self.lines[self.cursorRow] = line[:x] + change[1] + line[x:]
        self.cursorCol += len(change[1])
      elif change[0] == 'd':
        line = self.lines[self.cursorRow]
        x = self.cursorCol
        self.lines[self.cursorRow] = line[:x] + change[1] + line[x:]
      elif change[0] == 'dr':  # Undo delete range.
        app.log.detail('undo dr', change[1])
        self.insertLinesAt(change[1][0], change[1][1], change[2])
      elif change[0] == 'ds':  # Undo delete selection.
        app.log.detail('undo ds', change[1])
        self.insertLines(change[1])
      elif change[0] == 'i':
        line = self.lines[self.cursorRow]
        x = self.cursorCol
        self.cursorCol -= len(change[1])
        self.lines[self.cursorRow] = line[:x-len(change[1])] + line[x:]
        self.goalCol = self.cursorCol
      elif change[0] == 'j':
        # Join lines.
        line = self.lines[self.cursorRow]
        self.lines.insert(self.cursorRow+1, line[self.cursorCol:])
        self.lines[self.cursorRow] = line[:self.cursorCol]
      elif change[0] == 'ld':  # Undo line diff.
        app.log.info('ld')
        lines = []
        index = 0
        for ii in change[1]:
          if type(ii) is type(0):
            for line in self.lines[index:index+ii]:
              lines.append(line)
            index += ii
          elif ii[0] == '+':
            index += 1
          elif ii[0] == '-':
            lines.append(ii[2:])
        self.lines = lines
      elif change[0] == 'm':
        app.log.detail('undo move');
        self.cursorRow -= change[1][0]
        self.cursorCol -= change[1][1]
        self.goalCol -= change[1][2]
        self.scrollRow -= change[1][3]
        self.scrollCol -= change[1][4]
        self.markerRow -= change[1][5]
        self.markerCol -= change[1][6]
        self.markerEndRow -= change[1][7]
        self.markerEndCol -= change[1][8]
        self.selectionMode -= change[1][9]
        assert self.cursorRow >= 0
        assert self.cursorCol >= 0
        assert self.scrollRow >= 0
        assert self.scrollCol >= 0
        return True
      elif change[0] == 'n':
        # Undo split lines.
        self.lines[self.cursorRow] += self.lines[self.cursorRow+change[1][0]]
        for i in range(change[1][0]):
          del self.lines[self.cursorRow+1]
      elif change[0] == 'v':  # undo paste
        clip = change[1]
        row = self.cursorRow
        col = self.cursorCol
        app.log.info('len clip', len(clip))
        if len(clip) == 1:
          self.lines[row] = (
              self.lines[row][:col] +
              self.lines[row][col+len(clip[0]):])
        else:
          self.lines[row] = (self.lines[row][:col]+
              self.lines[row+len(clip)-1][len(clip[-1]):])
          delLineCount = len(clip[1:-1])
          del self.lines[row+1:row+1+delLineCount+1]
      elif change[0] == 'vb':
        row = min(self.markerRow, self.cursorRow)
        endRow = max(self.markerRow, self.cursorRow)
        for i in range(row, endRow+1):
          line = self.lines[self.cursorRow]
          x = self.cursorCol
          self.lines[self.cursorRow] = line[:x] + change[1] + line[x:]
        self.cursorCol += len(change[1])
      elif change[0] == 'vd':
        upperRow = min(self.markerRow, self.cursorRow)
        lowerRow = max(self.markerRow, self.cursorRow)
        x = self.cursorCol
        for i in range(upperRow, lowerRow+1):
          line = self.lines[i]
          self.lines[i] = line[:x] + change[1] + line[x:]
      elif change[0] == 'vi':  # Undo.
        text = change[1]
        col = self.cursorCol
        row = min(self.markerRow, self.cursorRow)
        endRow = max(self.markerRow, self.cursorRow)
        textLen = len(text)
        app.log.info('undo vi', textLen)
        for i in range(row, endRow+1):
          line = self.lines[i]
          self.lines[i] = line[:col] + line[col+textLen:]
      else:
        app.log.info('ERROR: unknown undo.')
    return False


class BackingTextBuffer(Mutator):
  """This base class to TextBuffer handles the text manipulation (without
  handling the drawing/rendering of the text)."""
  def __init__(self):
    Mutator.__init__(self)
    self.view = None
    self.clipList = []

  def setView(self, view):
    self.view = view

  def performDelete(self):
    if self.selectionMode != app.selectable.kSelectionNone:
      text = self.getSelectedText()
      if text:
        if (self.cursorRow > self.markerRow or
            (self.cursorRow == self.markerRow and
            self.cursorCol > self.markerCol)):
          self.swapCursorAndMarker()
        self.redoAddChange(('ds', text))
        self.redo()
      self.selectionNone()

  def performDeleteRange(self, upperRow, upperCol, lowerRow, lowerCol):
    app.log.info(upperRow, upperCol, lowerRow, lowerCol)
    if upperRow == self.cursorRow == lowerRow:
      app.log.info()
      if upperCol < self.cursorCol:
        app.log.info()
        col = upperCol - self.cursorCol
        if lowerCol <= self.cursorCol:
          col = upperCol - lowerCol
        app.log.info(col)
        self.cursorMove(0, col, self.cursorCol+col-self.goalCol)
        self.redo()
    elif upperRow <= self.cursorRow < lowerRow:
      app.log.info()
      self.cursorMove(upperRow-self.cursorRow, upperCol-self.cursorCol,
          upperCol-self.goalCol)
      self.redo()
    elif self.cursorRow == lowerRow:
      app.log.info()
      col = upperCol - lowerCol
      self.cursorMove(upperRow-self.cursorRow, col, col-self.goalCol)
      self.redo()
    if 1:
      self.redoAddChange((
        'dr',
        (upperRow, upperCol, lowerRow, lowerCol),
        self.getText(upperRow, upperCol, lowerRow, lowerCol)))
      self.redo()

  def backspace(self):
    app.log.info('backspace', self.cursorRow > self.markerRow)
    if self.selectionMode != app.selectable.kSelectionNone:
      self.performDelete()
    elif self.cursorCol == 0:
      if self.cursorRow > 0:
        self.cursorLeft()
        self.joinLines()
    else:
      line = self.lines[self.cursorRow]
      change = ('b', line[self.cursorCol-1:self.cursorCol])
      self.redoAddChange(change)
      self.redo()

  def carriageReturn(self):
    self.performDelete()
    self.redoAddChange(('n', (1,)))
    self.redo()
    self.cursorMove(1, -self.cursorCol, -self.goalCol)
    self.redo()
    if 1: # todo: if indent on CR
      line = self.lines[self.cursorRow-1]
      commonIndent = 2
      indent = 0
      while indent < len(line) and line[indent] == ' ':
        indent += 1
      if len(line):
        if line[-1] in [':', '[', '{']:
          indent += commonIndent
        elif line.count('(') > line.count(')'):
          indent += commonIndent * 2
      if indent:
        self.redoAddChange(('i', ' '*indent));
        self.redo()

  def cursorColDelta(self, toRow):
    if toRow >= len(self.lines):
      return
    lineLen = len(self.lines[toRow])
    if self.goalCol <= lineLen:
      return self.goalCol - self.cursorCol
    return lineLen - self.cursorCol

  def cursorDown(self):
    self.selectionNone()
    self.cursorMoveDown()

  def cursorDownScroll(self):
    #todo:
    self.selectionNone()
    self.cursorMoveDown()

  def cursorLeft(self):
    self.selectionNone()
    self.cursorMoveLeft()

  def cursorMove(self, rowDelta, colDelta, goalColDelta):
    self.cursorMoveAndMark(rowDelta, colDelta, goalColDelta, 0, 0, 0)

  def cursorMoveAndMark(self, rowDelta, colDelta, goalColDelta, markRowDelta,
      markColDelta, selectionModeDelta):
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    scrollRows = 0
    if self.scrollRow > self.cursorRow+rowDelta:
      scrollRows = self.cursorRow+rowDelta - self.scrollRow
    elif self.cursorRow+rowDelta >= self.scrollRow+maxy:
      scrollRows = self.cursorRow+rowDelta - (self.scrollRow+maxy-1)
    scrollCols = 0
    if self.scrollCol > self.cursorCol+colDelta:
      scrollCols = self.cursorCol+colDelta - self.scrollCol
    elif self.cursorCol+colDelta >= self.scrollCol+maxx:
      scrollCols = self.cursorCol+colDelta - (self.scrollCol+maxx-1)
    self.redoAddChange(('m', (rowDelta, colDelta, goalColDelta,
        scrollRows, scrollCols,
        markRowDelta, markColDelta, 0, 0, selectionModeDelta)))

  def cursorMoveScroll(self, rowDelta, colDelta, goalColDelta,
      scrollRowDelta, scrollColDelta):
    self.redoAddChange(('m', (rowDelta, colDelta, goalColDelta, scrollRowDelta,
        scrollColDelta,0,0, 0, 0,0)))

  def cursorMoveDown(self):
    if self.cursorRow+1 < len(self.lines):
      self.cursorMove(1, self.cursorColDelta(self.cursorRow+1), 0)
      self.redo()

  def cursorMoveLeft(self):
    if self.cursorCol > 0:
      self.cursorMove(0, -1, self.cursorCol-1 - self.goalCol)
      self.redo()
    elif self.cursorRow > 0:
      self.cursorMove(-1, len(self.lines[self.cursorRow-1]),
          self.cursorCol - self.goalCol)
      self.redo()

  def cursorMoveRight(self):
    if not self.lines:
      return
    if self.cursorCol < len(self.lines[self.cursorRow]):
      self.cursorMove(0, 1, self.cursorCol+1 - self.goalCol)
      self.redo()
    elif self.cursorRow+1 < len(self.lines):
      self.cursorMove(1, -len(self.lines[self.cursorRow]),
          self.cursorCol - self.goalCol)
      self.redo()

  def cursorMoveUp(self):
    if self.cursorRow > 0:
      lineLen = len(self.lines[self.cursorRow-1])
      if self.goalCol <= lineLen:
        self.cursorMove(-1, self.goalCol - self.cursorCol, 0)
        self.redo()
      else:
        self.cursorMove(-1, lineLen - self.cursorCol, 0)
        self.redo()

  def cursorMoveWordLeft(self):
    if self.cursorCol > 0:
      line = self.lines[self.cursorRow]
      pos = self.cursorCol
      for segment in re.finditer(app.selectable.kReWordBoundary, line):
        if segment.start() < pos <= segment.end():
          pos = segment.start()
          break
      self.cursorMove(0, pos-self.cursorCol, pos-self.cursorCol - self.goalCol)
      self.redo()
    elif self.cursorRow > 0:
      self.cursorMove(-1, len(self.lines[self.cursorRow-1]),
          self.cursorCol - self.goalCol)
      self.redo()

  def cursorMoveWordRight(self):
    if not self.lines:
      return
    if self.cursorCol < len(self.lines[self.cursorRow]):
      line = self.lines[self.cursorRow]
      pos = self.cursorCol
      for segment in re.finditer(app.selectable.kReWordBoundary, line):
        if segment.start() <= pos < segment.end():
          pos = segment.end()
          break
      self.cursorMove(0, pos-self.cursorCol, pos-self.cursorCol - self.goalCol)
      self.redo()
    elif self.cursorRow+1 < len(self.lines):
      self.cursorMove(1, -len(self.lines[self.cursorRow]),
          self.cursorCol - self.goalCol)
      self.redo()

  def cursorRight(self):
    self.selectionNone()
    self.cursorMoveRight()

  def cursorSelectDown(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveDown()

  def cursorSelectDownScroll(self):
    #todo:
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveDown()

  def cursorSelectLeft(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveLeft()

  def cursorSelectLineDown(self):
    """Set line selection and extend selection one row down."""
    self.selectionLine()
    if self.lines and self.cursorRow+1 < len(self.lines):
      self.cursorMove(1, -self.cursorCol, -self.goalCol)
      self.redo()
      self.cursorMoveAndMark(*self.extendSelection())
      self.redo()

  def cursorSelectRight(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveRight()

  def cursorSelectWordLeft(self):
    app.log.info('cursorSelectWordLeft')
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    if self.cursorRow == self.markerRow and self.cursorCol == self.markerCol:
      app.log.info('They match')
    self.cursorMoveWordLeft()
    self.cursorMoveAndMark(*self.extendSelection())
    self.redo()

  def cursorSelectWordRight(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveWordRight()
    self.cursorMoveAndMark(*self.extendSelection())
    self.redo()

  def cursorSelectUp(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveUp()

  def cursorSelectUpScroll(self):
    #todo:
    if self.selectionMode == app.selectable.kSelectionNone:
      self.selectionCharacter()
    self.cursorMoveUp()

  def cursorEndOfLine(self):
    lineLen = len(self.lines[self.cursorRow])
    self.cursorMove(0, lineLen-self.cursorCol, lineLen-self.goalCol)
    self.redo()

  def cursorPageDown(self):
    if self.cursorRow == len(self.lines):
      return
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    cursorRowDelta = maxy
    scrollDelta = maxy
    if self.cursorRow + 2*maxy >= len(self.lines):
      cursorRowDelta = len(self.lines)-self.cursorRow-1
      scrollDelta = len(self.lines)-maxy-self.scrollRow
    self.cursorMoveScroll(cursorRowDelta,
        self.cursorColDelta(self.cursorRow+cursorRowDelta), 0, scrollDelta, 0)
    self.redo()

  def cursorPageUp(self):
    if self.cursorRow == 0:
      return
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    cursorRowDelta = -maxy
    scrollDelta = -maxy
    if self.cursorRow < 2*maxy:
      cursorRowDelta = -self.cursorRow
      scrollDelta = -self.scrollRow
    self.cursorMoveScroll(cursorRowDelta,
        self.cursorColDelta(self.cursorRow+cursorRowDelta), 0, scrollDelta, 0)
    self.redo()

  def cursorScrollTo(self, goalRow, window):
    maxy, maxx = window.getmaxyx()
    if len(self.lines) < maxy:
      goalRow = 0
    elif goalRow < 0:
      goalRow = len(self.lines)+goalRow-maxy+1
    #scrollTo = min(min(goalRow, len(self.lines)-1), len(self.lines)-maxy-1)
    # self.cursorMoveScroll(scrollTo-self.cursorRow, -self.cursorCol, 0,
    #     scrollTo-self.scrollRow, -self.scrollCol)
    # self.redo()
    self.cursorRow = self.scrollRow = goalRow #hack

  def cursorScrollToMiddle(self):
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    rowDelta = min(max(0, len(self.lines)-maxy),
                   max(0, self.cursorRow-maxy/2))-self.scrollRow
    self.cursorMoveScroll(0, 0, 0, rowDelta, 0)

  def cursorStartOfLine(self):
    self.cursorMoveScroll(0, -self.cursorCol, -self.goalCol, 0, -self.scrollCol)
    self.redo()

  def cursorUp(self):
    self.selectionNone()
    self.cursorMoveUp()

  def cursorUpScroll(self):
    #todo:
    self.selectionNone()
    self.cursorMoveUp()

  def delCh(self):
    line = self.lines[self.cursorRow]
    change = ('d', line[self.cursorCol:self.cursorCol+1])
    self.redoAddChange(change)
    self.redo()

  def delete(self):
    """Delete character to right of cursor i.e. Del key."""
    if self.selectionMode != app.selectable.kSelectionNone:
      self.performDelete()
    elif self.cursorCol == len(self.lines[self.cursorRow]):
      if self.cursorRow+1 < len(self.lines):
        self.joinLines()
    else:
      self.delCh()

  def deleteToEndOfLine(self):
    line = self.lines[self.cursorRow]
    if self.cursorCol == len(self.lines[self.cursorRow]):
      if self.cursorRow+1 < len(self.lines):
        self.joinLines()
    else:
      change = ('d', line[self.cursorCol:])
      self.redoAddChange(change)
      self.redo()

  def editCopy(self):
    text = self.getSelectedText()
    if len(text):
      self.clipList.append(text)
      if self.selectionMode == app.selectable.kSelectionLine:
        text = text + ('',)
      if clipboard.copy:
        clipboard.copy("\n".join(text))

  def editCut(self):
    self.editCopy()
    self.performDelete()

  def editPaste(self):
    osClip = clipboard.paste and clipboard.paste()
    if len(self.clipList or osClip):
      if self.selectionMode != app.selectable.kSelectionNone:
        self.performDelete()
      if osClip:
        clip = tuple(osClip.split("\n"))
      else:
        clip = self.clipList[-1]
      self.redoAddChange(('v', clip))
      self.redo()
      rowDelta = len(clip)-1
      if rowDelta == 0:
        endCol = self.cursorCol+len(clip[0])
      else:
        endCol = len(clip[-1])
      self.cursorMove(rowDelta, endCol-self.cursorCol,
          endCol-self.goalCol)
      self.redo()
    else:
      app.log.info('clipList empty')

  def doDataToLines(self, data):
    def parse(line):
      return "\xfe%02x"%ord(line.groups()[0])
    lines = data.split('\r\n')
    if len(lines) == 1:
      lines = data.split('\n')
    if len(lines) == 1:
      lines = data.split('\r')
    return [re.sub('([\0-\x1f\x7f-\xff])', parse, i) for i in lines]

  def dataToLines(self):
    self.lines = self.doDataToLines(self.data)

  def fileFilter(self, data):
    self.data = data
    self.dataToLines()
    self.savedAtRedoIndex = self.redoIndex

  def setFilePath(self, path):
    app.buffer_manager.buffers.renameBuffer(self, path)

  def fileLoad(self):
    app.log.info('fileLoad', self.fullPath)
    file = None
    try:
      file = open(self.fullPath, 'r+')
      self.setMessage('Opened existing file')
      self.fileStat = os.stat(self.fullPath)
    except:
      try:
        # Create a new file.
        self.setMessage('Creating new file')
      except:
        app.log.info('error opening file', self.fullPath)
        self.setMessage('error opening file', self.fullPath)
        return
    self.relativePath = os.path.relpath(self.fullPath, os.getcwd())
    app.log.info('fullPath', self.fullPath)
    app.log.info('cwd', os.getcwd())
    app.log.info('relativePath', self.relativePath)
    if file:
      self.fileFilter(file.read())
      file.close()
    else:
      self.data = ""
    self.fileExtension = os.path.splitext(self.fullPath)[1]
    if self.data:
      self.parseGrammars()
      self.dataToLines()
    else:
      self.parser = None

  def linesToData(self):
    def encode(line):
      return chr(int(line.groups()[0], 16))
    #assert re.sub('\xfe([0-9a-fA-F][0-9a-fA-F])', encode, "\xfe00") == "\x00"
    lines = [
      re.sub('\xfe([0-9a-fA-F][0-9a-fA-F])', encode, i) for i in self.lines]
    self.data = '\n'.join(lines)

  def fileWrite(self):
    app.history.set(
        ['files', self.fullPath, 'cursor'], (self.cursorRow, self.cursorCol))
    try:
      try:
        self.stripTrailingWhiteSpace()
        self.linesToData()
        file = open(self.fullPath, 'w+')
        file.seek(0)
        file.truncate()
        file.write(self.data)
        file.close()
        self.fileStat = os.stat(self.fullPath)
        self.setMessage('File saved')
        self.savedAtRedoIndex = self.redoIndex
      except Exception as e:
        type_, value, tb = sys.exc_info()
        self.setMessage(
            'Error writing file. The file did not save properly.',
            color=3)
        app.log.info('error writing file')
        out = traceback.format_exception(type_, value, tb)
        for i in out:
          app.log.info(i)
    except:
      app.log.info('except had exception')

  def selectText(self, lineNumber, start, length, mode):
    scrollRow = self.scrollRow
    scrollCol = self.scrollCol
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    if not (self.scrollRow < lineNumber <= self.scrollRow + maxy):
      scrollRow = max(lineNumber-10, 0)
    if not (self.scrollCol < start <= self.scrollCol + maxx):
      scrollCol = max(start-10, 0)
    self.doSelectionMode(app.selectable.kSelectionNone)
    self.cursorMoveScroll(
        lineNumber-self.cursorRow,
        start+length-self.cursorCol,
        start+length-self.goalCol,
        scrollRow-self.scrollRow,
        scrollCol-self.scrollCol)
    self.redo()
    self.doSelectionMode(mode)
    self.cursorMove(0, -length, -length)
    self.redo()

  def find(self, searchFor, direction=0):
    """direction is -1 for findPrior, 0 for at cursor, 1 for findNext."""
    app.log.info('find', searchFor, direction)
    if not len(searchFor):
      self.findRe = None
      self.doSelectionMode(app.selectable.kSelectionNone)
      return
    # The saved re is also used for highlighting.
    self.findRe = re.compile('()'+searchFor)
    self.findBackRe = re.compile('(.*)'+searchFor)
    self.findCurrentPattern(direction)

  def findReplaceFlags(self, tokens):
    """Map letters in |tokens| to re flags."""
    flags = re.MULTILINE
    if 'i' in tokens:
      flags |= re.IGNORECASE
    if 'l' in tokens:
      # Affects \w, \W, \b, \B.
      flags |= re.LOCALE
    if 'm' in tokens:
      # Affects ^, $.
      flags |= re.MULTILINE
    if 's' in tokens:
      # Affects ..
      flags |= re.DOTALL
    if 'x' in tokens:
      # Affects whitespace and # comments.
      flags |= re.VERBOSE
    if 'u' in tokens:
      # Affects \w, \W, \b, \B.
      flags |= re.UNICODE
    if 0:
      tokens = re.sub('[ilmsxu]', '', tokens)
      if len(tokens):
        self.setMessage('unknown regex flags '+tokens)
    return flags

  def findReplace(self, cmd):
    if not len(cmd):
      return
    separator = cmd[0]
    splitCmd = cmd.split(separator, 3)
    if len(splitCmd) < 4:
      self.setMessage('An exchange needs three '+separator+' separators')
      return
    start, find, replace, end = splitCmd
    flags = self.findReplaceFlags(end)
    oldLines = self.lines
    self.linesToData()
    data = re.sub(find, replace, self.data, flags=flags)
    diff = difflib.ndiff(self.lines, self.doDataToLines(data))
    mdiff = []
    counter = 0
    for i in diff:
      if i[0] != ' ':
        if counter:
          mdiff.append(counter)
          counter = 0
        if i[0] in ['+', '-']:
          mdiff.append(i)
      else:
        counter += 1
    if counter:
      mdiff.append(counter)
    if len(mdiff) == 1 and type(mdiff[0]) is type(0):
      # Nothing was changed. The only entry is a 'skip these lines'
      self.setMessage('No matches found')
      return
    mdiff = tuple(mdiff)
    if 0:
      for i in mdiff:
        app.log.info(i)
    self.redoAddChange(('ld', mdiff))
    self.redo()

  def findCurrentPattern(self, direction):
    localRe = self.findRe
    if direction < 0:
      localRe = self.findBackRe
    if localRe is None:
      app.log.info('localRe is None')
      return
    # Current line.
    text = self.lines[self.cursorRow]
    if direction >= 0:
      text = text[self.cursorCol+direction:]
      offset = self.cursorCol+direction
    else:
      text = text[:self.cursorCol]
      offset = 0
    #app.log.info('find() searching', repr(text))
    found = localRe.search(text)
    if found:
      start = found.regs[1][1]
      end = found.regs[0][1]
      #app.log.info('found on line', self.cursorRow, start)
      self.selectText(self.cursorRow, offset+start, end-start,
          app.selectable.kSelectionCharacter)
      return
    # To end of file.
    if direction >= 0:
      theRange = range(self.cursorRow+1, len(self.lines))
    else:
      theRange = range(self.cursorRow-1, -1, -1)
    for i in theRange:
      found = localRe.search(self.lines[i])
      if found:
        if 0:
          for k in found.regs:
            app.log.info('AAA', k[0], k[1])
          app.log.info('b found on line', i, repr(found))
        start = found.regs[1][1]
        end = found.regs[0][1]
        self.selectText(i, start, end-start, app.selectable.kSelectionCharacter)
        return
    # Warp around to the start of the file.
    self.setMessage('Find wrapped around.')
    if direction >= 0:
      theRange = range(self.cursorRow)
    else:
      theRange = range(len(self.lines)-1, self.cursorRow, -1)
    for i in theRange:
      found = localRe.search(self.lines[i])
      if found:
        #app.log.info('c found on line', i, repr(found))
        start = found.regs[1][1]
        end = found.regs[0][1]
        self.selectText(i, start, end-start, app.selectable.kSelectionCharacter)
        return
    app.log.info('find not found')
    self.doSelectionMode(app.selectable.kSelectionNone)

  def findAgain(self):
    """Find the current pattern, searching down the document."""
    self.findCurrentPattern(1)

  def findBack(self):
    """Find the current pattern, searching up the document."""
    self.findCurrentPattern(-1)

  def findNext(self, searchFor):
    """Find a new pattern, searching down the document."""
    self.find(searchFor, 1)

  def findPrior(self, searchFor):
    """Find a new pattern, searching up the document."""
    self.find(searchFor, -1)

  def indent(self):
    if self.selectionMode == app.selectable.kSelectionNone:
      self.cursorMoveAndMark(0, -self.cursorCol, -self.goalCol,
          self.cursorRow-self.markerRow, self.cursorCol-self.markerCol, 0)
      self.redo()
      self.indentLines()
    elif self.selectionMode == app.selectable.kSelectionAll:
      self.cursorMoveAndMark(len(self.lines)-1-self.cursorRow, -self.cursorCol,
          -self.goalCol, -self.markerRow, -self.markerCol,
          app.selectable.kSelectionLine-self.selectionMode)
      self.redo()
      self.indentLines()
    else:
      self.cursorMoveAndMark(0, -self.cursorCol, -self.goalCol,
          0, -self.markerCol, app.selectable.kSelectionLine-self.selectionMode)
      self.redo()
      self.indentLines()

  def indentLines(self):
    self.redoAddChange(('vi', ('  ')))
    self.redo()

  def verticalInsert(self, row, endRow, col, text):
    self.redoAddChange(('vi', (text)))
    self.redo()

  def insert(self, text):
    self.performDelete()
    self.redoAddChange(('i', text))
    self.redo()
    maxRow, maxCol = self.view.cursorWindow.getmaxyx()
    deltaCol = self.cursorCol - self.scrollCol - maxCol + 1
    if deltaCol > 0:
      self.cursorMoveScroll(0, 0, 0, 0, deltaCol);
      self.redo()

  def insertPrintable(self, ch):
    #app.log.info('insertPrintable')
    if curses.ascii.isprint(ch):
      self.insert(chr(ch))
    # else:
    #   self.insert("\xfe%02x"%(ch,))

  def joinLines(self):
    """join the next line onto the current line."""
    self.redoAddChange(('j',))
    self.redo()

  def markerPlace(self):
    self.redoAddChange(('m', (0, 0, 0, 0, 0, self.cursorRow-self.markerRow,
        self.cursorCol-self.markerCol, 0, 0, 0)))
    self.redo()

  def mouseClick(self, paneRow, paneCol, shift, ctrl, alt):
    if shift:
      app.log.info(' shift click', paneRow, paneCol, shift, ctrl, alt)
      if self.selectionMode == app.selectable.kSelectionNone:
        self.selectionCharacter()
      self.mouseRelease(paneRow, paneCol, shift, ctrl, alt)
    else:
      app.log.info(' click', paneRow, paneCol, shift, ctrl, alt)
      self.selectionNone()
      self.mouseRelease(paneRow, paneCol, shift, ctrl, alt)

  def mouseDoubleClick(self, paneRow, paneCol, shift, ctrl, alt):
    app.log.info('double click', paneRow, paneCol)
    row = self.scrollRow + paneRow
    if row < len(self.lines) and len(self.lines[row]):
      self.selectWordAt(row, self.scrollCol + paneCol)

  def mouseMoved(self, paneRow, paneCol, shift, ctrl, alt):
    app.log.info(' mouseMoved', paneRow, paneCol, shift, ctrl, alt)
    self.mouseClick(paneRow, paneCol, True, ctrl, alt)

  def mouseRelease(self, paneRow, paneCol, shift, ctrl, alt):
    app.log.info(' mouse release', paneRow, paneCol)
    if not self.lines:
      return
    row = max(0, min(self.scrollRow + paneRow, len(self.lines) - 1))
    inLine = paneCol < len(self.lines[row])
    col = max(0, min(self.scrollCol + paneCol, len(self.lines[row])))
    # Adjust the marker column delta when the cursor and marker positions
    # cross over each other.
    markerCol = 0
    if self.selectionMode == app.selectable.kSelectionWord:
      if self.cursorRow == self.markerRow:
        if row == self.cursorRow:
          if self.cursorCol > self.markerCol and col < self.markerCol:
            markerCol = 1
          elif self.cursorCol < self.markerCol and col >= self.markerCol:
            markerCol = -1
        else:
          if (row < self.cursorRow and
              self.cursorCol > self.markerCol):
            markerCol = 1
          elif (row > self.cursorRow and
              self.cursorCol < self.markerCol):
            markerCol = -1
      elif row == self.markerRow:
        if col < self.markerCol and row < self.cursorRow:
          markerCol = 1
        elif col >= self.markerCol and row > self.cursorRow:
          markerCol = -1

    self.cursorMoveAndMark(row - self.cursorRow, col - self.cursorCol,
        col - self.goalCol, 0, markerCol, 0)
    self.redo()
    if self.selectionMode == app.selectable.kSelectionLine:
      self.cursorMoveAndMark(*self.extendSelection())
      self.redo()
    elif self.selectionMode == app.selectable.kSelectionWord:
      if (self.cursorRow < self.markerRow or
         (self.cursorRow == self.markerRow and
          self.cursorCol < self.markerCol)):
        self.cursorSelectWordLeft()
      elif inLine:
        self.cursorSelectWordRight()

  def mouseTripleClick(self, paneRow, paneCol, shift, ctrl, alt):
    app.log.info('triple click', paneRow, paneCol)
    self.mouseRelease(paneRow, paneCol, shift, ctrl, alt)
    self.selectLineAt(self.scrollRow + paneRow)

  def scrollWindow(self, rows, cols):
    self.cursorMoveScroll(rows, self.cursorColDelta(self.cursorRow-rows),
        0, -1, 0)
    self.redo()

  def mouseWheelDown(self, shift, ctrl, alt):
    if not shift:
      self.selectionNone()
    if self.scrollRow == 0:
      return
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    cursorDelta = 0
    if self.cursorRow >= self.scrollRow + maxy - 2:
      cursorDelta = self.scrollRow + maxy - 2 - self.cursorRow
    self.cursorMoveScroll(cursorDelta,
        self.cursorColDelta(self.cursorRow+cursorDelta), 0, -1, 0)
    self.redo()

  def mouseWheelUp(self, shift, ctrl, alt):
    if not shift:
      self.selectionNone()
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    if self.scrollRow+maxy >= len(self.lines):
      return
    cursorDelta = 0
    if self.cursorRow <= self.scrollRow + 1:
      cursorDelta = self.scrollRow-self.cursorRow + 1
    self.cursorMoveScroll(cursorDelta,
        self.cursorColDelta(self.cursorRow+cursorDelta), 0, 1, 0)
    self.redo()

  def nextSelectionMode(self):
    next = self.selectionMode + 1
    next %= app.selectable.kSelectionModeCount
    self.doSelectionMode(next)
    app.log.info('nextSelectionMode', self.selectionMode)

  def noOp(self, ignored):
    pass

  def parseGrammars(self):
    # Reset the self.data to get recent changes in self.lines.
    self.linesToData()
    if not self.parser:
      self.parser = app.parser.Parser()
    self.parser.parse(
        self.data,
        app.prefs.getGrammar(self.fileExtension))

  def doSelectionMode(self, mode):
    if self.selectionMode != mode:
      self.redoAddChange(('m', (0, 0, 0, 0, 0,
          self.cursorRow-self.markerRow,
          self.cursorCol-self.markerCol, 0, 0,
          mode-self.selectionMode)))
      self.redo()

  def selectionAll(self):
    self.doSelectionMode(app.selectable.kSelectionAll)
    self.cursorMoveAndMark(*self.extendSelection())
    self.redo()

  def selectionBlock(self):
    self.doSelectionMode(app.selectable.kSelectionBlock)

  def selectionCharacter(self):
    self.doSelectionMode(app.selectable.kSelectionCharacter)

  def selectionLine(self):
    self.doSelectionMode(app.selectable.kSelectionLine)

  def selectionNone(self):
    self.doSelectionMode(app.selectable.kSelectionNone)

  def selectionWord(self):
    self.doSelectionMode(app.selectable.kSelectionWord)

  def selectLineAt(self, row):
    self.selectionNone()
    self.cursorMove(row-self.cursorRow, 0, 0)
    self.redo()
    self.selectionLine()
    self.cursorMoveAndMark(*self.extendSelection())
    self.redo()

  def selectWordAt(self, row, col):
    row = max(0, min(row, len(self.lines)-1))
    inLine = col < len(self.lines[row])
    col = max(0, min(col, len(self.lines[row])-1))
    self.selectText(row, col, 0, app.selectable.kSelectionWord)
    if inLine:
      self.cursorSelectWordRight()

  def splitLine(self):
    """split the line into two at current column."""
    self.redoAddChange(('n', (1,)))
    self.redo()

  def swapCursorAndMarker(self):
    app.log.info('swapCursorAndMarker')
    self.cursorMoveAndMark(self.markerRow-self.cursorRow,
        self.markerCol-self.cursorCol,
        self.markerCol-self.goalCol,
        self.cursorRow-self.markerRow,
        self.cursorCol-self.markerCol, 0)
    self.redo()

  def test(self):
    app.log.info('test')
    self.insertPrintable(0x00)

  def stripTrailingWhiteSpace(self):
    for i in range(len(self.lines)):
      for found in app.selectable.kReEndSpaces.finditer(self.lines[i]):
        self.performDeleteRange(i, found.regs[0][0], i, found.regs[0][1])

  def unindent(self):
    if self.selectionMode == app.selectable.kSelectionAll:
      self.cursorMoveAndMark(len(self.lines)-1-self.cursorRow, -self.cursorCol,
          -self.goalCol,
          -self.markerRow, -self.markerCol, kSelectionLine-self.selectionMode)
      self.redo()
      self.unindentLines()
    else:
      self.cursorMoveAndMark(0, -self.cursorCol, -self.goalCol,
          0, -self.markerCol, app.selectable.kSelectionLine-self.selectionMode)
      self.redo()
      self.unindentLines()

  def unindentLines(self):
    upperRow = min(self.markerRow, self.cursorRow)
    lowerRow = max(self.markerRow, self.cursorRow)
    app.log.info('unindentLines', upperRow, lowerRow)
    for line in self.lines[upperRow:lowerRow+1]:
      if ((len(line) == 1 and line[:1] != ' ') or
          (len(line) >= 2 and line[:2] != '  ')):
        # Handle multi-delete.
        return
    self.redoAddChange(('vd', ('  ')))
    self.redo()

  def updateScrollPosition(self):
    """Move the selected view rectangle so that the cursor is visible."""
    maxy, maxx = self.view.cursorWindow.getmaxyx()
    rows = 0
    if self.scrollRow > self.cursorRow:
      rows = self.cursorRow - self.scrollRow
    elif self.cursorRow >= self.scrollRow+maxy:
      rows = self.cursorRow - (self.scrollRow+maxy-1)
    cols = 0
    if self.scrollCol > self.cursorCol:
      cols = self.cursorCol - self.scrollCol
    elif self.cursorCol >= self.scrollCol+maxx:
      cols = self.cursorCol - (self.scrollCol+maxx-1)
    self.cursorMoveScroll(0, 0, 0, rows, cols)
    self.redo()


class TextBuffer(BackingTextBuffer):
  """The TextBuffer adds the drawing/rendering to the BackingTextBuffer."""
  def __init__(self):
    BackingTextBuffer.__init__(self)
    self.lineLimitIndicator = sys.maxint
    self.highlightRe = None

  def scrollToCursor(self, window):
    """Move the selected view rectangle so that the cursor is visible."""
    maxy, maxx = window.cursorWindow.getmaxyx()
    #     self.cursorRow >= self.scrollRow+maxy 1 0
    rows = 0
    if self.scrollRow > self.cursorRow:
      rows = self.cursorRow - self.scrollRow
      app.log.error('AAA self.scrollRow > self.cursorRow',
          self.scrollRow, self.cursorRow, self)
    elif self.cursorRow >= self.scrollRow+maxy:
      rows = self.cursorRow - (self.scrollRow+maxy-1)
      app.log.error('BBB self.cursorRow >= self.scrollRow+maxy cRow',
          self.cursorRow, 'sRow', self.scrollRow, 'maxy', maxy, self)
    cols = 0
    if self.scrollCol > self.cursorCol:
      cols = self.cursorCol - self.scrollCol
      app.log.error('CCC self.scrollCol > self.cursorCol',
          self.scrollCol, self.cursorCol, self)
    elif self.cursorCol >= self.scrollCol+maxx:
      cols = self.cursorCol - (self.scrollCol+maxx-1)
      app.log.error('DDD self.cursorCol >= self.scrollCol+maxx',
          self.cursorCol, self.scrollCol, maxx, self)
    assert not rows
    assert not cols
    self.scrollRow += rows
    self.scrollCol += cols

  def draw(self, window):
    if self.shouldReparse:
      self.parseGrammars()
      self.shouldReparse = False
    maxy, maxx = window.cursorWindow.getmaxyx()

    self.scrollToCursor(window)

    startCol = self.scrollCol
    endCol = self.scrollCol+maxx

    if self.parser:
      defaultColor = curses.color_pair(0)
      # Highlight grammar.
      limit = min(max(len(self.lines)-self.scrollRow, 0), maxy)
      for i in range(limit):
        k = startCol
        while k < endCol:
          node, remaining = self.parser.grammarFromOffset(
              self.getCursorOffset(self.scrollRow+i, k))
          lastCol = min(endCol, k+remaining)
          line = self.lines[self.scrollRow+i][k:lastCol]
          length = len(line)
          color = node.grammar.get('color', defaultColor)
          if length:
            col = k-self.scrollCol
            window.addStr(i, col, line, color)
            # Highlight keywords.
            keywordsColor = node.grammar.get('keywordsColor', defaultColor)
            for found in node.grammar['keywordsRe'].finditer(line):
              f = found.regs[0]
              window.addStr(i, col+f[0], line[f[0]:f[1]], keywordsColor)
            # Highlight specials.
            keywordsColor = node.grammar.get('specialsColor', defaultColor)
            for found in node.grammar['specialsRe'].finditer(line):
              f = found.regs[0]
              window.addStr(i, col+f[0], line[f[0]:f[1]], keywordsColor)
            k += length
          else:
            window.addStr(i, k-self.scrollCol+length, ' '*(maxx-k-length),
                color)
            break
    else:
      # Draw to screen.
      limit = min(max(len(self.lines)-self.scrollRow, 0), maxy)
      for i in range(limit):
        line = self.lines[self.scrollRow+i][startCol:endCol]
        window.addStr(i, 0, line + ' '*(maxx-len(line)), window.color)
    self.drawOverlays(window)

  def drawOverlays(self, window):
    if 1:
      maxy, maxx = window.cursorWindow.getmaxyx()
      startRow = self.scrollRow
      startCol = self.scrollCol
      endCol = self.scrollCol+maxx
      limit = min(max(len(self.lines)-startRow, 0), maxy)
      if 1:
        # Highlight brackets.
        for i in range(limit):
          line = self.lines[startRow+i][startCol:endCol]
          for k in re.finditer(app.selectable.kReBrackets, line):
            for f in k.regs:
              window.addStr(i, f[0], line[f[0]:f[1]], curses.color_pair(6))
      if 1:
        # Match brackets.
        if (len(self.lines) > self.cursorRow and
            len(self.lines[self.cursorRow]) > self.cursorCol):
          ch = self.lines[self.cursorRow][self.cursorCol]
          def searchBack(closeCh, openCh):
            count = -1
            for row in range(self.cursorRow, startRow, -1):
              line = self.lines[row]
              if row == self.cursorRow:
                line = line[:self.cursorCol]
              found = [i for i in
                  re.finditer("(\\"+openCh+")|(\\"+closeCh+")", line)]
              for i in reversed(found):
                if i.group() == openCh:
                  count += 1
                else:
                  count -= 1
                if count == 0:
                  if i.start()+self.cursorCol-self.scrollCol < maxx:
                    window.addStr(row-startRow, i.start(), openCh,
                        curses.color_pair(201))
                  return
          def searchForward(openCh, closeCh):
            count = 1
            colOffset = self.cursorCol+1
            for row in range(self.cursorRow, startRow+maxy):
              if row != self.cursorRow:
                colOffset = 0
              line = self.lines[row][colOffset:]
              for i in re.finditer("(\\"+openCh+")|(\\"+closeCh+")", line):
                if i.group() == openCh:
                  count += 1
                else:
                  count -= 1
                if count == 0:
                  if i.start()+self.cursorCol-self.scrollCol < maxx:
                    window.addStr(row-startRow, colOffset+i.start(),
                        closeCh, curses.color_pair(201))
                  return
          matcher = {
            '(': (')', searchForward),
            '[': (']', searchForward),
            '{': ('}', searchForward),
            ')': ('(', searchBack),
            ']': ('[', searchBack),
            '}': ('{', searchBack),
          }
          look = matcher.get(ch)
          if look:
            look[1](ch, look[0])
            window.addStr(self.cursorRow-startRow,
                self.cursorCol-self.scrollCol,
                self.lines[self.cursorRow][self.cursorCol],
                curses.color_pair(201))
      if 1:
        # Highlight numbers.
        for i in range(limit):
          line = self.lines[startRow+i][startCol:endCol]
          for k in re.finditer(app.selectable.kReNumbers, line):
            for f in k.regs:
              window.addStr(i, f[0], line[f[0]:f[1]], curses.color_pair(31))
      if 1:
        # Highlight space ending lines.
        for i in range(limit):
          line = self.lines[startRow+i][startCol:endCol]
          offset = 0
          if startRow + i == self.cursorRow:
            offset = self.cursorCol-startCol
            line = line[offset:]
          for k in app.selectable.kReEndSpaces.finditer(line):
            for f in k.regs:
              window.addStr(i, offset+f[0], line[f[0]:f[1]],
                  curses.color_pair(180))
      lengthLimit = self.lineLimitIndicator
      if endCol >= lengthLimit:
        # Highlight long lines.
        for i in range(limit):
          line = self.lines[startRow+i]
          if len(line) < lengthLimit or startCol > lengthLimit:
            continue
          length = min(endCol, len(line)-lengthLimit)
          window.addStr(i, lengthLimit-startCol, line[lengthLimit:endCol],
              curses.color_pair(96))
      if self.findRe is not None:
        # Highlight find.
        for i in range(limit):
          line = self.lines[startRow+i][startCol:endCol]
          for k in self.findRe.finditer(line):
            f = k.regs[0]
            #for f in k.regs[1:]:
            window.addStr(i, f[0], line[f[0]:f[1]],
                curses.color_pair(app.prefs.foundColorIndex))
      if limit and self.selectionMode != app.selectable.kSelectionNone:
        # Highlight selected text.
        upperRow, upperCol, lowerRow, lowerCol = self.startAndEnd()
        selStartCol = max(upperCol - startCol, 0)
        selEndCol = min(lowerCol - startCol, maxx)
        start = max(0, min(upperRow-startRow, maxy))
        end = max(0, min(lowerRow-startRow, maxy))
        if self.selectionMode == app.selectable.kSelectionBlock:
          for i in range(start, end+1):
            line = self.lines[startRow+i][selStartCol:selEndCol]
            window.addStr(i, selStartCol, line, window.colorSelected)
        elif (self.selectionMode == app.selectable.kSelectionAll or
            self.selectionMode == app.selectable.kSelectionCharacter or
            self.selectionMode == app.selectable.kSelectionWord):
          # Go one row past the selection or to the last line.
          for i in range(start, min(end+1, len(self.lines)-startRow)):
            line = self.lines[startRow+i][startCol:endCol]
            if len(line) == len(self.lines[startRow+i]):
              line += " "  # Maybe do: "\\n".
            if i == end and i == start:
              window.addStr(i, selStartCol,
                  line[selStartCol:selEndCol], window.colorSelected)
            elif i == end:
              window.addStr(i, 0, line[:selEndCol], window.colorSelected)
            elif i == start:
              window.addStr(i, selStartCol, line[selStartCol:],
                  window.colorSelected)
            else:
              window.addStr(i, 0, line, window.colorSelected)
        elif self.selectionMode == app.selectable.kSelectionLine:
          for i in range(start, end+1):
            line = self.lines[startRow+i][selStartCol:maxx]
            window.addStr(i, selStartCol,
                line+' '*(maxx-len(line)), window.colorSelected)
      # Blank screen past the end of the buffer.
      color = curses.color_pair(app.prefs.outsideOfBufferColorIndex)
      for i in range(limit, maxy):
        window.addStr(i, 0, ' '*maxx, color)
