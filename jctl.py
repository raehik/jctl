#!/usr/bin/env python3
#
# Short description of the program/script's operation/function.
#

import sys
import argparse
import os
import re
import subprocess

class ArgumentParserUsage(argparse.ArgumentParser):
    """Argparse override to print usage to stderr on argument error."""
    def error(self, message):
        sys.stderr.write("error: %s\n" % message)
        self.print_help(sys.stderr)
        sys.exit(2)

class JournalCtl:
    # static class vars
    READ_ONLY = "r"
    READ_WRITE = "rw"

    ERR_NONE_FOUND = 2
    ERR_SELECT_CANCEL = 3

    def __init__(self):
        # set variables
        self.journal_dir = os.environ["HOME"] + "/journal"
        self.editor = os.environ["EDITOR"]
        self.command_dir = "commands"
        self.commands_to_import = ["open"]

        self.edit_aliases = ["edit", "e"]
        self.search_aliases = ["search", "s"]

        self.__parse_args()

    def exit(self, exit_code=0):
        """Deinitialise and exit."""
        sys.exit(exit_code)

    # Logging {{{
    def __log_message(self, message, pipe=sys.stdout):
        """Log a message to a specific pipe (defaulting to stdout)."""
        FILENAME = sys.argv[0]
        print(FILENAME + ": " + message, file=pipe)

    def log(self, message):
        """If verbose, log an event."""
        if not self.args.verbose:
            return
        self.__log_message(message)

    def error(self, message, exit_code=1):
        """Log an error and exit."""
        self.__log_message("error: " + message, sys.stderr)
        sys.exit(exit_code)

    def usage(self, exit_code):
        """Print usage and exit depending on given exit code."""
        if exit_code == 0:
            pipe = sys.stdout
        else:
            # if argument was non-zero, print to STDERR instead
            pipe = sys.stderr

        self.parser.print_help(pipe)
        sys.exit(exit_code)
    # Logging }}}

    def __parse_args(self):
        self.parser = ArgumentParserUsage(
                description="Control program for a journal kept in Jekyll.")

        # add arguments
        self.parser.add_argument("-v", "--verbose", help="be verbose",
                            action="store_true")
        self.parser.add_argument("-l", "--layout", help="layout to use")
        self.parser.add_argument("command", help="command to run")
        self.parser.add_argument("arguments", nargs="*", help="argument(s) for command")

        # parse & grab arguments
        self.args = self.parser.parse_args()
        self.arguments = self.args.arguments
        self.command = self.args.command

    def run_shell(self, args):
        """Run a shell command, returning the output."""
        # we run without a shell (default) so we don't need to shell escape
        # strange titles e.g. ones with punctuation in
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        out, err = proc.communicate()

        if proc.returncode != 0:
            was_successful = False

        return out.decode("utf-8").strip()

    def execute_cmd(self):
        """Try to run something based on the command given."""
        if self.command in self.edit_aliases:
            self.cmd_edit(self.arguments)
        elif self.command in self.search_aliases:
            self.cmd_search(self.arguments)

    def cmd_edit(self, arguments):
        if not arguments:
            self.error("command requires at least 1 argument", 2)
        else:
            matches = self.find_entries(arguments)
            if len(matches) == 0:
                print("No entries found for your query.")
                sys.exit(JournalCtl.ERR_NONE_FOUND)
            if len(matches) > 1:
                self.log("many entries found")
                print("More than one entry found for your queries.")
                # ask user which one to open
                index = self.interactive_number_chooser(matches)
                if index == -1:
                    # hit Ctrl-C / cancelled it
                    print("Selection cancelled, exiting")
                    sys.exit(21)
                else:
                    # index is valid
                    e = matches[index]
                    self.log("opening entry: {}".format(e))
                    self.edit_entry(e)
            else:
                self.log("one file found")
                self.edit_entry(matches[0])

    def edit_entry(self, filename):
        # use subprocess.call() so it works properly
        subprocess.call([self.editor, self.journal_dir + "/" + filename])

    def interactive_number_chooser(self, options):
        """Show an interactive chooser and return the number entered."""
        indent_spaces = 3
        valid_input = False
        print("Please enter the number corresponding to the entry you want to choose:")
        print()

        num_of_options = len(options)
        for i in range(num_of_options):
            print("{0:{1}d}) {2}".format(i, indent_spaces, options[i]))

        print()

        while not valid_input:
            try:
                ans = input(" > ")
            except KeyboardInterrupt:
                # new line so it looks better
                print()
                return -1
            except EOFError:
                print("Ctrl-D pressed, exiting...")
                return -1

            # special input values
            if ans == "" or ans == "quit" or ans == "q":
                print("Exiting selection...")
                return -1

            try:
                int_ans = int(ans)
            except ValueError:
                print("ERROR: not an integer. Please try again.")
                continue

            if 0 <= int_ans < num_of_options:
                valid_input = True
            else:
                print("ERROR: entry specified was out of range. Please try again.")

        return int_ans

    def find_entries(self, keywords):
        """Try to find entries matching *all* given keyword(s) in the filename
        *and* sort them most recent first."""
        entries = self.get_entries()

        # for every entry:
        #     if all keywords separately found in entry, entry is a match
        matches = []
        for entry in entries:
            if all(word in entry for word in keywords):
                matches.append(entry)

        if len(matches) == 0:
            self.log("no matches found for keywords")
            return []

        if len(matches) > 1:
            self.log("more than 1 match found for keywords")

        return sorted(matches, reverse=True)

    def cmd_search(self, arguments):
        """Search for keywords in full journal text."""

        """
        # get matches matching any of keywords
        matches_any = self.search_entries_any(arguments)

        # pretty-print 'any' matches
        for match in matches_any:
            print("{}: '{}' @ L.{}".format(
                match["entry_name"],
                match["keyword_match"],
                match["line_no"]
            ))
        """

        # OR get matches for *all* keywords
        matches_all = self.search_entries_all(arguments)

        # pretty-print 'all' matches
        if len(matches_all) == 0:
            print("No matches found for your query")
            sys.exit(0)
        elif len(matches_all) == 1:
            print("1 match found")
        elif len(matches_all) > 1:
            print("Many matches found")

        # TODO: make a y/n prompt function
        yn = input("Open a matched entry? (y/n) ")
        if yn.lower() == "y":
            index = self.interactive_number_chooser(matches_all)
            if index == -1:
                print("Selection cancelled, exiting")
                sys.exit(JournalCtl.ERR_SELECT_CANCEL)
            else:
                self.edit_entry(matches_all[index])
        elif yn.lower() == "n":
            print("Matches found in entries:")
            for match in matches_all:
                print(" * {}".format(match))
        else:
            print("error: response wasn't y/n, exiting...")

    def search_entries_any(self, keywords):
        """Try to find entries matching given keywords in the text, where a
        valid match is *any one* of the keywords.

        Returns a list of matches in the following format:

            [
                [
                entry_name: entry
                keyword_match: keywords[i]
                line_no: 123
                line_text: "... keywords[i] ..."
                ]
            ]
        """

        # TODO: 3 `for` loops deep? maybe not the best

        FIRST_LINE_INDEX = 1

        # sort & reverse for niceness (can't do at the end without manual
        # sorting methods)
        entries = sorted(self.get_entries(), reverse=True)

        matches = []

        # check entry text
        for entry in entries:
            text = self.get_text_of(entry)
            lines = text.split("\n")
            for w in keywords:
                for i, line in enumerate(lines, FIRST_LINE_INDEX):
                    # we check lower case, but we don't make the actual
                    # variables lower, so that we can show the original keyword
                    # matches & line text
                    if w.lower() in line.lower():
                        matches.append({
                            "entry_name": entry,
                            "keyword_match": w,
                            "line_no": i,
                            "line_text": line,
                        })

        # TODO: check entry titles/filenames (both?) too

        return matches

    def search_entries_all(self, keywords):
        """
        Try to find entries matching given keywords in the text, where a
        valid match is *each of* of the keywords found in text.

        Returns a list of matches.
        """

        entries = self.get_entries()

        # for every entry:
        #     if all keywords separately found in entry text, entry is a match
        matches = []
        for entry in entries:
            text = self.get_text_of(entry)
            if all(word in text for word in keywords):
                matches.append(entry)

        if len(matches) == 0:
            self.log("no matches found for keywords")
            return []

        if len(matches) > 1:
            self.log("more than 1 match found for keywords")

        return sorted(matches, reverse=True)

    def get_text_of(self, entry):
        """Returns the contents of the specified entry."""
        return self.open_entry(entry).read()

    def open_entry(self, entry):
        """Returns a read-only file handle to the specified entry."""
        filename = self.get_filename_of_entry(entry)
        return open(filename, JournalCtl.READ_ONLY)

    def edit_entry(self, entry):
        self.log("Opening entry '" + entry + "' in editor '" + self.editor + "'")
        subprocess.call([self.editor, self.get_filename_of_entry(entry)])

    def get_filename_of_entry(self, entry):
        """
        Returns a constructed full path for a given 'basename' file name (the
        entry).

        Note that this constructed file does *not* need to exist, since we might
        be opening a new file -- thus other functions must do that checking
        where required.
        """
        return self.journal_dir + "/" + entry

    def get_entries(self):
        """Return a list of all journal entry filenames (basenames)."""
        return os.listdir(self.journal_dir)

    def get_titles(self):
        """Return a list of the title of each entry."""
        title_regex = re.compile('^title: "?(.*?)"?$')

        files = [self.get_filename_of_entry(entry) for entry in self.get_entries()]

        titles = []
        for f in files:
            with self.open_entry(f) as current_file:
                for line in current_file:
                    result = TITLE.match(line)
                    if result is not None:
                        titles.append(result.group(1))
                        break
                # TODO: no title found
                #titles.append("ayy lmao")


        #combined = []
        #for title in titles:
        #    combined.append([title, run_shell(["ezstring", title])])

        #print(combined)

if __name__ == "__main__":
    jctl = JournalCtl()
    jctl.execute_cmd()
