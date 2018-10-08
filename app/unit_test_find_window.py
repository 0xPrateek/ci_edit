# -*- coding: latin-1 -*-

# Copyright 2018 Google Inc.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import curses
import sys

from app.curses_util import *
import app.fake_curses_testing


class FindWindowTestCases(app.fake_curses_testing.FakeCursesTestCase):
  def setUp(self):
    self.longMessage = True
    if True:
      # The buffer manager will retain the test file in RAM. Reset it.
      try:
        del sys.modules['app.buffer_manager']
        import app.buffer_manager
      except KeyError:
        pass
    app.fake_curses_testing.FakeCursesTestCase.setUp(self)

  def test_find(self):
    self.runWithFakeInputs([
        self.displayCheck(-1, 0, [u"      "]),
        CTRL_F, self.displayCheck(-3, 0, [u"Find: "]), CTRL_J,
        self.displayCheck(-1, 0, [u"      "]),
        CTRL_F, self.displayCheck(-3, 0, [u"Find: "]),
        CTRL_I, self.displayCheck(-3, 0, [u"Find: ", u"Replace: ", u"["]),
        #KEY_BTAB, KEY_BTAB, self.displayCheck(-1, 0, [u"Find: "]),
        CTRL_Q])

  def test_find_replace_groups(self):
    #self.setMovieMode(True)
    self.runWithFakeInputs([
        self.writeText(u'aDog\n'),
        self.displayCheck(2, 7, [u"aDog  "]),
        CTRL_F, self.writeText(u'a(.*)'),
        self.displayCheck(-3, 0, [u"Find: a(.*)  "]),
        CTRL_I, self.writeText(u'x\\1\\1'),
        self.displayCheck(-2, 0, [u"Replace: x\\1\\1  "]),
        CTRL_G,
        self.displayCheck(2, 7, [u"xDogDog  "]),
        CTRL_Q, u"n"])

  def test_find_esc_from_find(self):
    self.runWithFakeInputs([
        # Check initial state.
        self.displayCheck(-1, 0, [u"      "]),
        self.displayCheckStyle(-2, 0, 1, 10, app.prefs.color['status_line']),

        # Basic open and close.
        CTRL_F, self.displayCheck(-3, 0, [u"Find: "]),
        KEY_ESCAPE, curses.ERR,
        self.displayCheck(-3, 0, [u"   ", u"   ", u"   "]),
        self.displayCheckStyle(-2, 0, 1, 10, app.prefs.color['status_line']),

        # Open, expand, and close.
        CTRL_F, self.displayCheck(-3, 0, [u"Find: "]),
        CTRL_I, self.displayCheck(-3, 0, [u"Find: ", u"Replace: ", u"["]),
        KEY_ESCAPE, curses.ERR,
        self.displayCheck(-3, 0, [u"   ", u"   ", u"   "]),
        self.displayCheckStyle(-2, 0, 1, 10, app.prefs.color['status_line']),

        # Regression test one for https://github.com/google/ci_edit/issues/170.
        CTRL_F, self.displayCheck(-3, 0, [u"Find: ", u"Replace: ", u"["]),
        CTRL_I, CTRL_I,
        self.displayCheck(-3, 0, [u"Find: ", u"Replace: ", u"["]),
        KEY_ESCAPE, curses.ERR,
        self.displayCheck(-3, 0, [u"   ", u"   ", u"   "]),
        self.displayCheckStyle(-2, 0, 1, 10, app.prefs.color['status_line']),

        # Regression test two for https://github.com/google/ci_edit/issues/170.
        CTRL_F, self.displayCheck(-3, 0, [u"Find: ", u"Replace: ", u"["]),
        self.addMouseInfo(0, 2, 10, curses.BUTTON1_PRESSED),
        curses.KEY_MOUSE,
        #self.displayCheck(-3, 0, ["   ", "   ", "   "]),
        self.displayCheckStyle(-2, 0, 1, 10, app.prefs.color[u'status_line']),
        CTRL_Q])

  def test_replace_style_parse(self):
    self.runWithFakeInputs([
        #self.displayCheck(2, 7, [u"      "]),
        #self.displayCheckStyle(2, 7, 1, 10, app.prefs.color[u'text']),
        self.writeText(u'focusedWindow\n'),
        CTRL_F,
        #self.displayCheck(-1, 0, [u"Find:         "]),
        self.writeText(u'focused'),
        CTRL_I,
        #self.displayCheck(-3, 0, [u"Find: focused", "Replace:          ", u"["]),
        self.writeText(u'  focused'),
        #self.displayCheck(-3, 0, [u"Find: focused", "Replace:   focused", u"["]),
        CTRL_G,
        # Regression, replace causes 'Windo' to show as a misspelling.
        self.displayCheckStyle(2, 17, 1, 10, app.prefs.color[u'text']),
        CTRL_Q, ord('n')])
