# coding=utf-8
import sublime
import sublime_plugin

import fnmatch
import os
import json
import re
import collections


class BoundKeysCommand(sublime_plugin.TextCommand):
    def loadAndJsonify(self, fileName):
        """Open the supplied file name and return parsed JSON"""
        try:
            f = open(fileName, "r")
            data = f.read()
            f.close()
            # Remove any comments from the files as they're not technically valid
            # JSON and the parser falls over on them
            stripComments = re.compile("^\s*//.*$", re.MULTILINE)
            return json.loads(re.sub(stripComments, "", data))
        except:
            return False

    def separator(self):
        """Return a string of _'s to use when outputting the results"""
        return " %s\n" % (u"_" * 128)

    def padTo(self, string, padTo):
        """Pad a string to X chars with spaces"""
        if len(string) > padTo:
            return string[0:padTo - 1] + u"…"
        return "%s%s" % (string, " " * (padTo - len(string)))

    def orderKeyCombo(self, keyCombo):
        """Take a key combination and order it alphabetically"""
        if type(keyCombo) is list:
            ret = []
            for keyCom in keyCombo:
                ret.append("+".join(sorted(keyCom.split("+"))))
        else:
            ret = "+".join(sorted(keyCombo.split("+")))
        return ret

    def getOutput(self, name, keyFile, bindings, last=False):
        """Convert JSON dict representing one file into a results table"""
        text = []
        # First we add the file name
        text.append(u"|    %s key bindings%s|\n" % (name, " " * (111 - len(name))))
        text.append(self.separator())
        # Loop the key bindings 1 at a time
        for binding in keyFile:
            # Firstly the key sequence
            keys = self.padTo(", ".join(binding["keys"]), 25)
            # Next the command that gets called
            command = self.padTo(binding["command"].lower(), 25)
            # Then any arguments passed to the command
            argsList = []
            if "args" in binding:
                for arg in binding["args"]:
                    argVal = str(binding["args"][arg]).replace("\n", "").replace("\t", "TAB")
                    argsList.append("%s: %s" % (arg.lower(), argVal))
            args = self.padTo(", ".join(argsList), 25)
            # Now add the list of clashes indicating with *'s if the file overrides
            # our current one
            if len(bindings[self.orderKeyCombo(binding["keys"][0].lower())]) > 1:
                dupedIn = []
                for dupe in bindings["__".join(self.orderKeyCombo(binding["keys"])).lower()]:
                    if dupe != name:
                        if name == "Default" or dupe == "User" or (name < dupe and dupe != "Default"):
                            dupedIn.append("*" + dupe + "*")
                        else:
                            dupedIn.append(dupe)
                clashes = self.padTo(", ".join(self.listUnique(dupedIn)), 50)
            else:
                clashes = self.padTo("", 50)
            # Now piece them all together
            text.append(u"|%s|%s|%s|%s|\n" % (keys, command, args, clashes))
        if not last:
            text.append("\n%s" % self.separator())
        return "".join(text)

    def listUnique(self, seq):
        """De-dupe the passed list"""
        seen = {}
        result = []
        for item in seq:
            marker = item
            if marker in seen:
                continue
            seen[marker] = 1
            result.append(item)
        return result

    def run(self, edit):
        """List all key bindings and indicate clashes and overrides.

Search through all installed .sublime-keymap files and indicate any clashes and overrides.

"""
        # Set up some vars for use later
        view = self.view
        pluginFiles = []
        errorLoading = []
        pluginKeyFiles = {}
        text = ""
        bindings = collections.defaultdict(list)
        # Get the platform we're running on and convert it to the correct case to
        # represent a filename
        platform = sublime.platform()
        if platform == "windows":
            platform = "Windows"
        elif platform == "osx":
            platform = "OSX"
        elif platform == "linux":
            platform = "Linux"

        # Store the default and user keymap file paths
        defaultKeyBindings = "%s%s%s%sDefault (%s).sublime-keymap" % (sublime.packages_path(), os.sep, "Default", os.sep, platform)
        userKeyBindings = "%s%s%s%sDefault (%s).sublime-keymap" % (sublime.packages_path(), os.sep, "User", os.sep, platform)
        keyFiles = {"User": userKeyBindings, "Default": defaultKeyBindings}

        # Load the ignored packages list
        settings = sublime.load_settings("Preferences.sublime-settings")
        ignored = settings.get("ignored_packages", None)

        # Recursively walk the package directory and pull out the file path of
        # any used plugin keymap files
        for root, dirnames, filenames in os.walk(sublime.packages_path()):
            for filename in fnmatch.filter(filenames, "*.sublime-keymap"):
                # We only need default and default (PLATFORM) files
                if "Default.sublime-keymap" in filename or "(%s)" % platform in filename:
                    filepath = os.path.join(root, filename)
                    # Work out the plugin name for checking against the ignored packages list
                    end = filepath.rfind(os.sep)
                    start = filepath.rfind(os.sep, 0, end) + 1
                    pluginName = filepath[start:end]
                    # Lastly we drop the user and default files as we deal with these separately
                    if pluginName not in ignored and pluginName != "User" and pluginName != "Default":
                        pluginFiles.append(pluginName + os.sep + filename)

        # Load all files and parse the JSON contents
        for keyFile in keyFiles:
            fileResult = self.loadAndJsonify(keyFiles[keyFile])
            if not fileResult:
                return sublime.error_message("Error loading %s file. This may be due to the file being inaccessible or because the JSON is invalid." % keyFile)
            else:
                keyFiles[keyFile] = fileResult
        for pluginFile in pluginFiles:
            fileResult = self.loadAndJsonify(sublime.packages_path() + os.sep + pluginFile)
            if not fileResult:
                errorLoading.append(pluginFile)
            else:
                pluginKeyFiles[pluginFile] = fileResult

        # Loop our loaded files and build a dictionary of files each combination
        # is present in keyed on the actual key combination
        for keyFile in keyFiles:
            for binding in keyFiles[keyFile]:
                bindings["__".join(self.orderKeyCombo(binding["keys"]))].append(keyFile)
        for keyFile in pluginKeyFiles:
            for binding in pluginKeyFiles[keyFile]:
                shortName = keyFile[0:keyFile.find(os.sep)]
                bindings["__".join(self.orderKeyCombo(binding["keys"]))].append(shortName)

        # Build our output. User first, then plugins, finally default
        if errorLoading:
            text += "Error loading the following files: %s\n\n" % ", ".join(errorLoading)
        text += self.separator()
        text += self.getOutput("User", keyFiles["User"], bindings)
        for name in sorted(pluginKeyFiles):
            shortName = name[0:name.find(os.sep)]
            text += self.getOutput(shortName, pluginKeyFiles[name], bindings)
        text += self.getOutput("Default", keyFiles["Default"], bindings, True)

        # Open a new tab and populate it with the text generated above
        results = view.window().new_file()
        results.set_scratch(True)
        results.set_name("Bound Keys")
        newRegion = sublime.Region(1, 0)
        results.replace(edit, newRegion, text)
