# Bound Keys #

A plugin for both Sublime Text 2 and 3 that lists the contents of active keymap
files and indicate any clashes / overrides.

## Details ##

The plugin lists the contents of all installed .sublime-keymap files from active
plugins along with the pre-installed User and Default files. The last column
of the data table lists clashes of key combinations whilst he presence of
*asterisks* indicate that the combination is overridden by the other file.

The plugin respects the override order of the various ST3 package installation
folders and only lists keys from the file that takes precedence.

The presented columns of data are: Key combination, command called, arguments to
command and clashes.

![BoundKeys Screenshot](https://github.com/CodeEffect/BoundKeys/raw/master/BoundKeys.png)

## Manual installation ##

At present the plugin is not in package control so you will need to install manually.

### Using GIT (recommended): ###
Go to the Packages directory (`Preferences` / `Browse Packages…`). Then clone this
repository:

    git clone git://github.com/CodeEffect/BoundKeys

### Manually: ###
Downoad a zip of the project (click on the zip icon further up the page) and extract
it into your packages directory (`Preferences` / `Browse Packages…`).
Go to the "Packages" directory (`Preferences` / `Browse Packages…`). Then clone this
repository:

## Default key bindings ##

`shift+f10` - `bound_keys` - Open a new tab and list details of all bound keys indicating
where clashes occur

## License ##

Bound Keys is licensed under the MIT license.

  Copyright (c) 2013 Steven Perfect <steve@codeeffect.co.uk>

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
