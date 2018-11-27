// Copyright 2018 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use std::io::Write;

extern crate ncurses;

const KEY_CTRL_Q: i32 = 17;

pub fn enable_bracketed_paste() {
    // Enable Bracketed Paste Mode.
    let stdout = std::io::stdout();
    let mut stdout_handle = stdout.lock();
    stdout_handle.write(b"\033[?2004;h").expect(
        "enable_bracketed_paste failed");
    // Push the escape codes out to the terminal. (Whether this is needed seems
    // to vary by platform).
    stdout_handle.flush().expect("enable_bracketed_paste flush failed");
}

pub fn run() {
    // Maybe set to "en_US.UTF-8"?
    ncurses::setlocale(ncurses::LcCategory::all, "");

    ncurses::initscr();
    ncurses::raw();
    ncurses::mousemask(ncurses::ALL_MOUSE_EVENTS as ncurses::mmask_t, None);
    ncurses::keypad(ncurses::stdscr(), true);
    ncurses::meta(ncurses::stdscr(), true);
    ncurses::noecho();
    enable_bracketed_paste();

    ncurses::clear();
    ncurses::mv(0, 0);
    ncurses::printw("This is a work in progress\n");
    ncurses::printw("Press ctrl+q to exit.\n");
    loop {
        let c = ncurses::getch();
        if c == KEY_CTRL_Q {
            break;
        }
        ncurses::printw(&format!("pressed {}\n", c));
    }
    ncurses::endwin();
}
