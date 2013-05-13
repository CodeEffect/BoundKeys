# coding=utf-8
import sublime
import sublime_plugin

import fnmatch
import os
import zipfile
import json
import re
import collections


class BoundKeysCommand(sublime_plugin.TextCommand):
    def removeComments(self, text):
        """Thanks to: http://stackoverflow.com/questions/241327/"""
        def replacer(match):
            s = match.group(0)
            if s.startswith('/'):
                return ""
            else:
                return s
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        return re.sub(pattern, replacer, text)

    def jsonify(self, data):
        """Tidy passed string and parse as JSON into a python object"""
        self.lastJsonifyError = ''
        try:
            # Remove any comments from the files as they're not technically
            # valid JSON and the parser falls over on them
            data = self.removeComments(data)

            # Build 3021 & 3033 have trailing commas in the default files
            fixTrailing = re.compile("%s\s+%s" % (
                re.escape("},"),
                re.escape("]")
            ), re.MULTILINE)
            data = re.sub(fixTrailing, "}   ]", data)

            return json.loads(data, strict=False)
        except Exception as e:
            self.lastJsonifyError = "Error parsing JSON: %s" % str(e)
            print(self.lastJsonifyError)
            return False

    def separator(self):
        """Return a string of _'s to use when outputting the results"""
        return " %s\n" % (u"_" * 128)

    def padTo(self, string, padTo):
        """Pad a string to X chars with spaces"""
        if len(string) > padTo:
            return string[0:padTo - 1] + u"…"
        return "%s%s" % (string, " " * (padTo - len(string)))

    def prepKey(self, keyCombo):
        """Take a key combination and order it alphabetically"""
        if type(keyCombo) is list:
            keys = []
            for keyCom in keyCombo:
                keys.append("+".join(sorted(keyCom.lower().split("+"))))
            ret = "__".join(keys)
        else:
            ret = "+".join(sorted(keyCombo.lower().split("+")))
        return ret

    def getOutput(self, fileRepr, last=False):
        """Convert JSON dict representing one file into a results table"""
        text = []
        name = fileRepr["name"]
        path = fileRepr["path"]
        keyFile = fileRepr["object"]
        # First we add the file name and path
        zName = " (%s)" % fileRepr["zipName"] if "zipName" in fileRepr else ""
        length = len(name) + len(zName) + len(path)
        if length > 113:
            loc = u"…%s " % (path[max(1, (length) - 109):] + zName)
        else:
            loc = self.padTo(path + zName, 111 - len(name))
        text.append(u"| %s key bindings - %s|\n" % (
            name,
            loc
        ))
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
                    argVal = str(
                        binding["args"][arg]
                    ).replace("\n", "").replace("\t", "TAB")
                    argsList.append("%s: %s" % (arg.lower(), argVal))
            args = self.padTo(", ".join(argsList), 25)
            # Now add the list of clashes indicating with *'s if the file
            # overrides our current one
            if len(self.bindings[self.prepKey(binding["keys"][0])]) > 1:
                dupedIn = []
                for dupe in self.bindings[self.prepKey(binding["keys"])]:
                    if dupe != name:
                        if name == "Default" or dupe == "User" or (
                            name < dupe and dupe != "Default"
                        ):
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

Search through all installed .sublime-keymap files and indicate any clashes
and overrides.

"""
        # Set up some vars for use later
        view = self.view
        errorLoading = []
        text = ""
        self.bindings = collections.defaultdict(list)
        # Store sublime file details here (User and Default)
        subKeys = {}
        # Store our other package details here
        userKeys = {}
        # Get the self.platform we're running on and convert it to the correct
        # case to represent a filename
        platforms = {"windows": "Windows", "osx": "OSX", "linux": "Linux"}
        try:
            p = sublime.platform()
            self.platform = platforms[p]
        except:
            return view.status_message("Unknown platform \"%s\"." % p)

        validNames = [
            "Default.sublime-keymap",
            "Default (%s).sublime-keymap" % self.platform
        ]
        # If we're at least version 3 then we have 3 package dir's.
        if int(str(sublime.version())[0]) >= 3:
            exePath = sublime.executable_path()
            exePP = "%s%sPackages" % (
                exePath[0:exePath.rfind(os.sep)],
                os.sep
            )
            pP = sublime.packages_path()
            insPP = sublime.installed_packages_path()
            self.pPaths = {
                "packages": {"path": pP, "isZip": False},
                "installed_packages": {"path": insPP, "isZip": True},
                "executable_packages": {"path": exePP, "isZip": True}
            }
        else:
            self.pPaths = {
                "packages": {"path": sublime.packages_path(), "isZip": False}
            }

        # We will use the following format for holding and processing file
        # paths, contents, details etc. Note that the first key below is a path
        # relative to the package folder so that we only load the highest
        # priority file.
        #
        # Note: The order of precedence from most important to least is User
        # file, plugin files (alphabetical: z highest, a lowest) finally
        # default file. The order based on location is the packages folder,
        # installed packages folder then executable folder:
        #
        # subKeys[lastPath][name]    = Short name e.g. User, PluginName etc
        #                  [loc_key] = Key of above self.pPaths dictionary
        #                  [obj]     = Python object repr of JSON
        #                  [path]    = Full path to the file
        #
        # Due to the updated sublime-3 way of using zip files as packages it's
        # likely that we'd be best to get all details at once as we have to
        # open the zip to get the file path anyway.

        # First we'll get our default and user files as these are important +
        # we know their file name if not the exact location.
        subKeys = {
            "%s%sDefault (%s).sublime-keymap" % (
                "Default",
                os.sep,
                self.platform
            ): {"name": "Default"},
            "%s%sDefault (%s).sublime-keymap" % (
                "User",
                os.sep,
                self.platform
            ): {"name": "User"}
        }

        for lastPath in subKeys:
            for pathName in self.pPaths:
                jsonObj = None
                if self.pPaths[pathName]["isZip"]:
                    fullPath = "%s%s%s.sublime-package" % (
                        self.pPaths[pathName]["path"],
                        os.sep,
                        subKeys[lastPath]["name"]
                    )
                    fileZipPath = "%s (%s).sublime-keymap" % (
                        subKeys[lastPath]["name"],
                        self.platform
                    )
                    try:
                        if not zipfile.is_zipfile(fullPath):
                            continue
                        zip = zipfile.ZipFile(fullPath, "r")
                        jsonObj = self.jsonify(
                            str(zip.open(fileZipPath, "r").read(), "utf-8")
                        )
                        zip.close()
                    except IOError:
                        print("File not found: %s" % fullPath)
                    except zipfile.BadZipfile:
                        print("Bad zip file: %s" % fullPath)
                    # TODO: Other exceptions???
                else:
                    fileZipPath = None
                    # Else file is just text
                    fullPath = "%s%s%s" % (
                        self.pPaths[pathName]["path"],
                        os.sep,
                        lastPath
                    )
                    try:
                        jsonObj = self.jsonify(open(fullPath, "r").read())
                    except IOError:
                        pass

                if jsonObj:
                    subKeys[lastPath]["loc_key"] = pathName
                    subKeys[lastPath]["object"] = jsonObj
                    subKeys[lastPath]["path"] = fullPath
                    if fileZipPath:
                        subKeys[lastPath]["zipName"] = fileZipPath
                    break

        # Load the ignored packages list
        settings = sublime.load_settings("Preferences.sublime-settings")
        ignored = settings.get("ignored_packages", None)

        # Recursively walk the package directories and pull all info on any
        # used plugin keymap files (including those inside .sublime-package zip
        # files)
        for pathName in self.pPaths:
            for root, dirs, files in os.walk(self.pPaths[pathName]["path"]):
                if self.pPaths[pathName]["isZip"]:
                    # Look for zipped sublime-package files
                    for filename in fnmatch.filter(files, "*.sublime-package"):
                        fullPath = os.path.join(root, filename)
                        # Check it's a zip
                        if not zipfile.is_zipfile(fullPath):
                            continue
                        try:
                            zip = zipfile.ZipFile(fullPath, "r")
                            for zipName in zip.namelist():
                                # We only need default and default (platform)
                                # files
                                if zipName not in validNames:
                                    continue
                                # Work out our short name (that we key our
                                # dicts on) to see if we've loaded a higher
                                # pref version of this file
                                name = filename[0:filename.find(".")]
                                if name in ignored:
                                    continue
                                lastPath = "%s%s%s" % (name, os.sep, zipName)
                                if lastPath in subKeys or lastPath in userKeys:
                                    continue
                                # Nothing loaded so far and the file looks to
                                # be required
                                jsonObj = self.jsonify(
                                    str(zip.open(zipName, "r").read(), "utf-8")
                                )
                                fileZipPath = None
                                zip.close()
                                userKeys[lastPath] = {}
                                userKeys[lastPath]["name"] = name
                                userKeys[lastPath]["loc_key"] = pathName
                                userKeys[lastPath]["object"] = jsonObj
                                userKeys[lastPath]["path"] = fullPath
                                userKeys[lastPath]["zipName"] = zipName
                        except IOError:
                            print("File not found: %s" % fullPath)
                        except zipfile.BadZipfile:
                            print("Bad zip file: %s" % fullPath)
                else:
                    # Handle the loose packages folder on ST3 or ST2's only
                    # packages location
                    fileZipPath = None
                    for filename in fnmatch.filter(files, "*.sublime-keymap"):
                        # We only need default and default (platform) files
                        if filename not in validNames:
                            continue
                        filePath = os.path.join(root, filename)
                        # Work out the plugin name for checking against the
                        # ignored packages list
                        end = filePath.rfind(os.sep)
                        start = filePath.rfind(os.sep, 0, end) + 1
                        name = filePath[start:end]
                        if name in ignored:
                            continue
                        # Lastly we drop the user and default files as we deal
                        # with these separately
                        lastPath = "%s%s%s" % (name, os.sep, filename)
                        if lastPath in subKeys or lastPath in userKeys:
                            continue
                        try:
                            jsonObj = self.jsonify(open(filePath, "r").read())
                        except IOError:
                            errorLoading.append(filePath)
                        if jsonObj:
                            userKeys[lastPath] = {}
                            userKeys[lastPath]["name"] = name
                            userKeys[lastPath]["loc_key"] = pathName
                            userKeys[lastPath]["object"] = jsonObj
                            userKeys[lastPath]["path"] = filePath

        # Loop our loaded files and build a dictionary of files each
        # combination is present in keyed on the actual key combination
        for lastPath in subKeys:
            for binding in subKeys[lastPath]["object"]:
                self.bindings["__".join(
                    self.prepKey(binding["keys"])
                )].append(subKeys[lastPath]["name"])
        for lastPath in userKeys:
            for binding in userKeys[lastPath]["object"]:
                self.bindings["__".join(
                    self.prepKey(binding["keys"])
                )].append(userKeys[lastPath]["name"])

        # Build our output. User first, then plugins, finally default
        if errorLoading:
            text += "Error loading the following files: %s\n\n" % (
                ", ".join(errorLoading)
            )
        text += self.separator()
        lastPath = "%s%sDefault (%s).sublime-keymap" % (
            "User",
            os.sep,
            self.platform
        )
        text += self.getOutput(subKeys[lastPath])
        for lastPath in sorted(userKeys):
            text += self.getOutput(userKeys[lastPath])
        lastPath = "%s%sDefault (%s).sublime-keymap" % (
            "Default",
            os.sep,
            self.platform
        )
        text += self.getOutput(subKeys[lastPath], True)

        # Open a new tab and populate it with the text generated above
        results = view.window().new_file()
        results.set_scratch(True)
        results.set_name("Bound Keys")
        newRegion = sublime.Region(1, 0)
        results.replace(edit, newRegion, text)
