# Copyright 2016 The ci_edit Authors. All rights reserved.
# Use of this source code is governed by an Apache-style license that can be
# found in the LICENSE file.

"""Key bindings for the cua-like editor."""

from app.curses_util import *
import app.controller
import app.editor
import curses
import curses.ascii
import text_buffer


def initCommandSet(editText, textBuffer):
  """The basic command set includes line editing controls."""
  return {
    #curses.KEY_F10: editText.prg.debugWindowOrder,
    CTRL_A: textBuffer.selectionAll,

    CTRL_C: textBuffer.editCopy,

    CTRL_H: textBuffer.backspace,

    CTRL_Q: editText.maybeChangeToQuit,
    CTRL_S: textBuffer.fileWrite,
    CTRL_V: textBuffer.editPaste,
    CTRL_X: textBuffer.editCut,
    CTRL_Y: textBuffer.redo,
    CTRL_Z: textBuffer.undo,

    127: textBuffer.backspace,
    curses.ascii.DEL: textBuffer.backspace,

    curses.KEY_BACKSPACE: textBuffer.backspace,
    curses.KEY_DC: textBuffer.delete,
    curses.KEY_HOME: textBuffer.cursorStartOfLine,
    curses.KEY_END: textBuffer.cursorEndOfLine,

    # curses.KEY_DOWN: textBuffer.cursorDown,
    curses.KEY_LEFT: textBuffer.cursorLeft,
    curses.KEY_RIGHT: textBuffer.cursorRight,
    # curses.KEY_UP: textBuffer.cursorUp,

    KEY_CTRL_LEFT: textBuffer.cursorMoveWordLeft,
    KEY_CTRL_SHIFT_LEFT: textBuffer.cursorSelectWordLeft,
    KEY_CTRL_RIGHT: textBuffer.cursorMoveWordRight,
    KEY_CTRL_SHIFT_RIGHT: textBuffer.cursorSelectWordRight,
  }


class InteractiveFind(app.editor.InteractiveFind):
  """Find text within the current document."""
  def __init__(self, host, textBuffer):
    app.editor.InteractiveFind.__init__(self, host, textBuffer)
    self.document = host
    commandSet = initCommandSet(self, textBuffer)
    commandSet.update({
      curses.ascii.ESC: self.changeToHostWindow,
      curses.KEY_F1: self.info,
      curses.KEY_F3: self.saveEventChangeToHostWindow,
      KEY_SHIFT_F3: self.saveEventChangeToHostWindow,
      CTRL_E: self.findReplaceChangeToHostWindow,
      CTRL_F: self.findNext,
      CTRL_G: self.findNext,
      CTRL_J: self.changeToHostWindow,
      CTRL_R: self.findPrior,
      CTRL_S: self.saveDocument,
      curses.KEY_DOWN: self.findNext,
      curses.KEY_UP: self.findPrior,
    })
    self.commandSet = commandSet
    self.commandDefault = self.textBuffer.insertPrintable

  def findReplaceChangeToHostWindow(self):
    self.findReplace()
    self.changeToHostWindow()


class InteractiveGoto(app.editor.InteractiveGoto):
  """Jump to a particular line number."""
  def __init__(self, host, textBuffer):
    app.editor.InteractiveGoto.__init__(self, host, textBuffer)
    self.document = host
    commandSet = initCommandSet(self, textBuffer)
    commandSet.update({
      curses.ascii.ESC: self.changeToHostWindow,
      curses.KEY_F1: self.info,
      CTRL_J: self.changeToHostWindow,
      CTRL_S: self.saveDocument,
      ord('b'): self.gotoBottom,
      ord('h'): self.gotoHalfway,
      ord('t'): self.gotoTop,
    })
    self.commandSet = commandSet
    self.commandDefault = self.textBuffer.insertPrintable


class InteractiveOpener(app.editor.InteractiveOpener):
  """Open a file to edit."""
  def __init__(self, prg, host, textBuffer):
    app.editor.InteractiveOpener.__init__(self, prg, host, textBuffer)
    self.document = host
    commandSet = initCommandSet(self, textBuffer)
    commandSet.update({
      curses.ascii.ESC: self.changeToHostWindow,
      curses.KEY_F1: self.info,
      CTRL_I: self.tabCompleteExtend,
      CTRL_J: self.createOrOpen,
      CTRL_N: self.createOrOpen,
      CTRL_O: self.createOrOpen,
    })
    self.commandSet = commandSet
    self.commandDefault = self.textBuffer.insertPrintable


class InteractiveQuit(app.editor.InteractiveQuit):
  """Ask about unsaved changes."""
  def __init__(self, host, textBuffer):
    app.editor.InteractiveQuit.__init__(self, host, textBuffer)
    self.document = host
    commandSet = initCommandSet(self, textBuffer)
    commandSet.update({
      curses.KEY_F1: self.info,
      ord('n'): host.quitNow,
      ord('y'): self.saveAndQuit,
    })
    self.commandSet = commandSet
    self.commandDefault = self.changeToHostWindow

  def saveAndQuit(self):
    app.log.info('saveAndQuit')
    # Preload the message with an error that should be overwritten.
    self.document.textBuffer.setMessage('Error saving file')
    self.document.textBuffer.fileWrite()
    # check for write error.
    if self.document.textBuffer.message[0] != 'File saved':
      return
    self.host.quitNow()


class CuaEdit(app.controller.Controller):
  """Keyboard mappings for CUA. CUA is the Cut/Copy/Paste paradigm."""
  def __init__(self, prg, host):
    app.controller.Controller.__init__(self, host, 'CuaEdit')
    self.prg = prg
    self.host = host
    app.log.info('CuaEdit.__init__')

  def setTextBuffer(self, textBuffer):
    self.textBuffer = textBuffer
    commandSet = initCommandSet(self, textBuffer)
    commandSet.update({
      curses.ascii.ESC: textBuffer.selectionNone,
      curses.KEY_RESIZE: self.prg.handleScreenResize,

      curses.KEY_F1: self.info,

      curses.KEY_BTAB: textBuffer.unindent,
      curses.KEY_PPAGE: textBuffer.cursorPageUp,
      curses.KEY_NPAGE: textBuffer.cursorPageDown,

      CTRL_F: self.changeToFind,
      CTRL_G: self.changeToGoto,

      CTRL_I: textBuffer.indent,
      CTRL_J: textBuffer.carriageReturn,

      CTRL_O: self.changeToFileOpen,
      CTRL_R: self.changeToFindPrior,

      curses.KEY_DOWN: textBuffer.cursorDown,
      curses.KEY_SLEFT: textBuffer.cursorSelectLeft,
      curses.KEY_SRIGHT: textBuffer.cursorSelectRight,
      curses.KEY_UP: textBuffer.cursorUp,

      KEY_SHIFT_DOWN: textBuffer.cursorSelectDown,
      KEY_SHIFT_UP: textBuffer.cursorSelectUp,

      KEY_CTRL_DOWN: textBuffer.cursorDownScroll,
      KEY_CTRL_SHIFT_DOWN: textBuffer.cursorSelectDownScroll,
      KEY_CTRL_UP: textBuffer.cursorUpScroll,
      KEY_CTRL_SHIFT_UP: textBuffer.cursorSelectUpScroll,
    })
    self.commandSet = commandSet
    self.commandDefault = self.textBuffer.insertPrintable

  def info(self):
    app.log.info('CuaEdit Command set main')
    app.log.info(repr(self))

  def onChange(self):
    pass


class CuaPlusEdit(CuaEdit):
  """Keyboard mappings for CUA, plus some extra."""
  def __init__(self, prg, host):
    CuaEdit.__init__(self, prg, host)
    app.log.info('CuaPlusEdit.__init__')

  def info(self):
    app.log.info('CuaPlusEdit Command set main')
    app.log.info(repr(self))

  def setTextBuffer(self, textBuffer):
    app.log.info('CuaPlusEdit.__init__')
    CuaEdit.setTextBuffer(self, textBuffer)
    commandSet = self.commandSet.copy()
    commandSet.update({
      CTRL_E: textBuffer.nextSelectionMode,

      curses.KEY_F3: textBuffer.findAgain,
      curses.KEY_F4: self.prg.paletteWindow.focus,
      curses.KEY_F6: self.prg.shiftPalette,
      KEY_SHIFT_F3: textBuffer.findBack,
    })
    self.commandSet = commandSet


class PaletteDialogController(app.controller.Controller):
  """."""
  def __init__(self, prg, view):
    app.controller.Controller.__init__(self, prg, 'Palette')
    self.prg = prg
    self.view = view
    app.log.info('PaletteDialogController.__init__')
    def noOp(c):
      app.log.info('noOp in PaletteDialogController')
    self.commandDefault = noOp
    self.commandSet = {
      CTRL_J: self.changeToHostWindow,
      curses.ascii.ESC: self.changeToHostWindow,
      curses.KEY_F3: self.prg.shiftPalette,
      curses.KEY_F5: self.changeToHostWindow,
    }

  def changeToHostWindow(self):
    self.view.hide()
    app.controller.Controller.changeToHostWindow(self)

  def info(self):
    app.log.info('PaletteDialogController command set')
    app.log.info(repr(self))

  def setTextBuffer(self, textBuffer):
    pass