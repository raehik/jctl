#!/usr/bin/env python3
#
# Short description of the program/script's operation/function.
#

import sys
import argparse
import os
import re
import subprocess
import time
import shutil
import filecmp

class ArgumentParserUsage(argparse.ArgumentParser):
    """Argparse override to print usage to stderr on argument error."""
    def error(self, message):
        sys.stderr.write("error: %s\n" % message)
        self.print_help(sys.stderr)
        sys.exit(2)

class JournalCtl:
    # static class vars
    READ_ONLY = "r"
    WRITE_ONLY = "w"

    FRONT_MATTER_SEP = "---"
    FRONT_MATTER_VALUE_SEP = ": "
    FRONT_MATTER_END = "\n" + FRONT_MATTER_SEP + "\n"

    TMP_DIR = "/tmp"
    TMP_PREFIX = "jctl"
    TMP_EXT = ".md"

    SUCCESS = 0
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

    def message(self, message):
        """Print a message to stdout, regardless of verbosity."""
        print(message)
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
        elif self.command == "help":
            print("Available commands: search, edit, help")
        else:
            self.error("No such command '{}'".format(self.command))

    def cmd_edit(self, arguments):
        if not arguments:
            self.error("command requires at least 1 argument", 2)
        else:
            matches = self.find_entries(arguments)
            if len(matches) == 0:
                self.message("No entries found for your query.")
                sys.exit(JournalCtl.ERR_NONE_FOUND)
            if len(matches) > 1:
                self.log("many entries found")
                self.message("More than one entry found for your queries.")
                # ask user which one to open
                index = self.interactive_number_chooser(matches)
                if index == -1:
                    # hit Ctrl-C / cancelled it
                    self.message("Selection cancelled, exiting")
                    sys.exit(JournalCtl.ERR_SELECT_CANCEL)
                else:
                    # index is valid
                    e = matches[index]
                    self.edit_entry(e)
            else:
                self.log("one file found")
                self.edit_entry(matches[0])

    def interactive_number_chooser(self, options):
        """
        Show an interactive chooser for a list of options and return the number
        entered.

        For valid input, returns a positive integer for the option's index in
        the list.
        For other input (cancelled, empty line), returns -1.

        """
        ret_bad_input = -1
        indent_spaces = 3
        start_num = 1
        valid_input = False
        print("Please enter the number corresponding to the entry you want to choose:")
        print()

        for i, opt in enumerate(options, start_num):
            print("{0:{1}d}) {2}".format(i, indent_spaces, opt))

        print()

        while not valid_input:
            try:
                ans = input(" > ")
            except KeyboardInterrupt:
                # new line so it looks better
                print()
                return ret_bad_input
            except EOFError:
                print("Ctrl-D pressed, exiting...")
                return ret_bad_input

            # special input values
            if ans == "" or ans == "quit" or ans == "q":
                print("Exiting selection...")
                return ret_bad_input

            try:
                int_ans = int(ans)
            except ValueError:
                print("ERROR: not an integer. Please try again.")
                continue

            index = int_ans - start_num
            if 0 <= index < len(options):
                valid_input = True
            else:
                print("ERROR: entry specified was out of range. Please try again.")

        return index

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
            self.message("No matches found for your query")
            sys.exit(JournalCtl.SUCCESS)
        elif len(matches_all) == 1:
            self.message("1 match found")
        elif len(matches_all) > 1:
            self.message("Many matches found")

        yn = self.__yn_prompt("Open a matched entry?")
        if yn == 0:
            index = self.interactive_number_chooser(matches_all)
            if index == -1:
                self.message("Selection cancelled, exiting")
                sys.exit(JournalCtl.ERR_SELECT_CANCEL)
            else:
                self.edit_entry(matches_all[index])
        elif yn == 1:
            self.message("Matches found in entries:")
            for match in matches_all:
                print(" * {}".format(match))
        else:
            message("ERROR: response wasn't y/n, exiting...")

    def __yn_prompt(self, prompt_msg):
        yn = input(prompt_msg + " (y/n) ").lower()
        if yn == "y" or yn == "yes":
            return 0
        elif yn == "n" or yn == "no":
            return 1
        else:
            return -1


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
        filename = self.get_entry_file(entry)
        return open(filename, JournalCtl.READ_ONLY)

    def edit_entry(self, entry):
        entry_file = self.get_entry_file(entry)

        tmpfile = self.__generate_entry_tmpfile(entry)
        self.log("Opening entry '{}' using '{}'".format(entry, self.editor))
        # use subprocess.call() so it works properly
        #subprocess.call([self.editor, self.get_entry_file(entry)])
        subprocess.call([self.editor, tmpfile])

        # we get here when the file has been closed
        if filecmp.cmp(entry_file, tmpfile):
            # files are identical: no changes were made
            self.message("No changes made")
        else:
            # move tmpfile to original entry
            shutil.move(tmpfile, entry_file)
            self.message("File has been changed")
            yn = self.__yn_prompt("Update timestamp?")
            if yn == 0:
                self.update_time(entry)
            else:
                self.message("Exiting...")


    def __generate_entry_tmpfile(self, entry):
        """
        Generates a temporary file for entry editing, copies the given entry to
        it and returns the filename.

        Requires that JournalCtl.TMP_DIR exists.
        """
        tmp_dir = JournalCtl.TMP_DIR
        tmp_file = JournalCtl.TMP_DIR + "/" \
                + JournalCtl.TMP_PREFIX + "-" \
                + str(int(time.time())) \
                + JournalCtl.TMP_EXT

        shutil.copyfile(self.get_entry_file(entry), tmp_file)

        return tmp_file

    def get_entry_file(self, entry):
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

    def get_front_matter(self, entry):
        with self.open_entry(entry) as f:
            text = f.read()

        # FIXME: not the best way of setting begin index
        begin_index = 4
        end_index = text.find(JournalCtl.FRONT_MATTER_END)
        raw_front_matter = text[begin_index:end_index].strip().split("\n")

        front_matter = []
        for line in raw_front_matter:
            parts = line.split(JournalCtl.FRONT_MATTER_VALUE_SEP, 1)
            if len(parts) > 2:
                self.error("somehow split front matter line into >2 parts")
            elif len(parts) == 1 and parts[0] == "":
                self.log("empty line in front matter")
                parts = None
            front_matter.append(parts)

        return front_matter

    def get_entry_text(self, entry):
        with self.open_entry(entry) as f:
            text = f.read()

        begin_index = text.find(JournalCtl.FRONT_MATTER_END)
        entry_text = text[begin_index+len(JournalCtl.FRONT_MATTER_END):]
        return entry_text

    def update_time(self, entry):
        """
        Update the time in an entry to the time now.

        Awkwardly, I have to rewrite the entire file to do this. Oh well.
        """
        front_matter = self.get_front_matter(entry)
        entry_text = self.get_entry_text(entry)
        new_time = int(time.time())

        entry_file = self.get_entry_file(entry)

        new_text = ""
        new_text += JournalCtl.FRONT_MATTER_SEP + "\n"
        for line in front_matter:
            if line == None:
                # empty line
                new_text += "\n"
                continue

            var = line[0]
            value = line[1]
            if var == "date":
                # found date line: let's update it before adding it
                value = time.strftime("%F %T")
                self.message("Timestamp updated ({} -> {}).".format(line[1], value))
            new_text += "{}: {}\n".format(var, value)
        new_text += JournalCtl.FRONT_MATTER_SEP + "\n"
        new_text += entry_text

        with open(entry_file, JournalCtl.WRITE_ONLY) as f:
            f.write(new_text)

    def update_entry(self, front_matter, entry_text):
        pass

    def get_titles(self):
        """Return a list of the title of each entry."""
        # TODO: test this method
        title_regex = re.compile('^title: "?(.*?)"?$')

        files = [self.get_entry_file(entry) for entry in self.get_entries()]

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
