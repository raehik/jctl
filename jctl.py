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

FILENAME = os.path.basename(sys.argv[0])

class ArgumentParserUsage(argparse.ArgumentParser):
    """Argparse override to print usage to stderr on argument error."""
    def error(self, message):
        sys.stderr.write("error: %s\n" % message)
        self.print_help(sys.stderr)
        sys.exit(2)

class JournalCtl:
    SUCCESS = 0
    ERR_NONE_FOUND = 1
    ERR_TEMPLATE_FAIL = 2
    ERR_SELECT_CANCEL = 3
    ERR_FILE_EXISTS = 4
    ERR_NO_SUCH_CMD = 5
    ERR_WRONG_ARGS = 6

    READ_ONLY = "r"
    WRITE_ONLY = "w"
    TMP_DIR = "/tmp"
    TMP_PREFIX = "jctl"

    TEMPLATER_CMD = "pyplater.py"
    TEMPLATE_PREFIX = "jctl-"
    SLUG_CMD = "ezstring"
    ENTRY_EXT = ".md" # if this has >1 full stop then you gotta fix get_entries()

    FRONT_MATTER_SEP = "---"
    FRONT_MATTER_VALUE_SEP = ": "
    FRONT_MATTER_END = "\n" + FRONT_MATTER_SEP + "\n"

    def __init__(self):
        # set variables
        self.journal_dir = os.environ["HOME"] + "/journal"
        self.editor = os.environ["EDITOR"]

        self.new_aliases = ["new", "n"]
        self.edit_aliases = ["edit", "e"]
        self.search_aliases = ["search", "s"]

        self.__parse_args()

    def exit(self, exit_code=0):
        """Deinitialise and exit."""
        sys.exit(exit_code)

    # Logging {{{
    def __log_message(self, message, pipe=sys.stdout):
        """Log a message to a specific pipe (defaulting to stdout)."""
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
        self.parser.add_argument("command", help="command to run")
        self.parser.add_argument("arguments", nargs="*", help="argument(s) for command")

        # parse & grab arguments
        self.args = self.parser.parse_args()
        self.arguments = self.args.arguments
        self.command = self.args.command

    def get_shell(self, args):
        """Run a shell command, returning the output."""
        # we run without a shell (default) so we don't need to shell escape
        # strange titles e.g. ones with punctuation in
        was_successful = False
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        out, err = proc.communicate()

        if proc.returncode == 0:
            was_successful = True

        return out.decode("utf-8").strip(), was_successful

    def run_interactive(self, args):
        """Run an interactive shell command and return the return code."""
        return subprocess.call(args)

    def execute_cmd(self):
        """Try to run something based on the command given."""
        if self.command in self.new_aliases:
            self.cmd_new(self.arguments)
        elif self.command in self.edit_aliases:
            self.cmd_edit(self.arguments)
        elif self.command in self.search_aliases:
            self.cmd_search(self.arguments)
        elif self.command == "help":
            print("Available commands: new, search, edit, help")
        else:
            self.error(
                    "No such command '{}'".format(self.command),
                    JournalCtl.ERR_NO_SUCH_CMD)

    def cmd_new(self, arguments):
        """
        Create a new entry using a file templater (by default, my Pyplater).

        Note that unlike my previous 'journal' template, the 'jctl-*' templates
        require that jctl provides the *full* filename. That way the templater
        doesn't get involved with journal placement.
        """
        # we need at least the template name (entry, exam, meal) & title
        if len(arguments) < 2:
            self.error("expected at least 2 arguments (got {})".format(
                len(arguments)), JournalCtl.ERR_WRONG_ARGS)

        # get title & name of new entry
        entry_title = " ".join(arguments[1:])
        slug, ret = self.get_shell([JournalCtl.SLUG_CMD, entry_title])
        entry_name = "{}-{}".format(time.strftime("%F"), slug)
        entry_file = self.get_entry_file(entry_name)

        # check that exact file does not exist already
        if os.path.isfile(entry_file):
            self.error("entry '{}' already exists".format(entry_name),
                    JournalCtl.ERR_FILE_EXISTS)

        # templater command
        template = JournalCtl.TEMPLATE_PREFIX + arguments[0]
        template_cmd = [
                JournalCtl.TEMPLATER_CMD,
                template,
                entry_file,
                entry_title,
                ]
        ret = self.run_interactive(template_cmd)

        if ret == 0:
            self.log("templating succeeded")
        else:
            self.error("templating failed (error code {})".format(ret),
                    JournalCtl.ERR_TEMPLATE_FAIL)

        # I use date field as 'last edited' field, so update again when finished
        # (my Pyplater already fills it in, but only at the start)
        self.update_time(entry_name)

    def cmd_edit(self, arguments):
        if not arguments:
            self.error("command requires at least 1 argument",
                    JournalCtl.ERR_WRONG_ARGS)
        else:
            matches = self.find_entries(arguments)
            if len(matches) == 0:
                self.message("No entries found for your query.")
                sys.exit(JournalCtl.ERR_NONE_FOUND)
            if len(matches) > 1:
                self.message("More than one entry found for your query.")
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

        if len(options) == 1:
            # there is one option. return its index :)
            return 0

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

        # get matches for *all* keywords
        matches_all = self.search_entries(arguments)

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
            self.message("ERROR: response wasn't y/n, exiting...")

    def __yn_prompt(self, prompt_msg):
        """
        Prompt the user with a yes/no question.

        Returns 0 for 'yes'.
        Returns 1 for 'no'.
        Returns -1 for invalid input.
        """
        ret_y = 0
        ret_n = 1
        ret_invalid = -1

        try:
            yn = input(prompt_msg + " (y/n) ").lower()
        except KeyboardInterrupt:
            # new line so it looks better
            print()
            return ret_invalid
        except EOFError:
            return ret_invalid
        if yn == "y" or yn == "yes":
            return ret_y
        elif yn == "n" or yn == "no":
            return ret_n
        else:
            return -1

    def search_entries(self, keywords):
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
            # remember to check everything in lowercase
            if all(word.lower() in text.lower() for word in keywords):
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
        self.run_interactive([self.editor, tmpfile])

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
        Copies the given entry to a temporary file for entry editing and returns
        the temporary file's name.

        Requires that JournalCtl.TMP_DIR exists.
        """
        tmp_dir = JournalCtl.TMP_DIR
        tmp_file = JournalCtl.TMP_DIR + "/" \
                + JournalCtl.TMP_PREFIX + "-" \
                + str(int(time.time())) \
                + JournalCtl.ENTRY_EXT

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
        return self.journal_dir + "/" + entry + JournalCtl.ENTRY_EXT

    def get_entries(self):
        """
        Return a list of all entry names.

        In jctl, most functions only deal with the 'slug' as an entry name (i.e.
        'YYYY-MM-DD-title-slug'). This function returns the 'basename' of each
        entry, without full path *or the extension*.
        """
        return [ os.path.splitext(entry)[0] for entry in os.listdir(self.journal_dir) ]

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
            if len(parts) == 2:
                # correct
                pass
            elif len(parts) > 2:
                self.error("somehow split front matter line into >2 parts",
                        JournalCtl.ERR_BAD_FRONT_MATTER)
            elif len(parts) == 1 and parts[0] == "":
                self.log("empty line in front matter")
                parts = None
            elif len(parts) == 1 and parts[0] != "":
                self.log("front matter variable '{}' has no value".format(
                    parts[0]))
                parts.append(None)
            else:
                self.error("unknown error in front matter",
                        JournalCtl.ERR_BAD_FRONT_MATTER)
            front_matter.append(parts)

        return front_matter

    def get_entry_text(self, entry):
        with self.open_entry(entry) as f:
            text = f.read()

        begin_index = text.find(JournalCtl.FRONT_MATTER_END)
        entry_text = text[begin_index+len(JournalCtl.FRONT_MATTER_END):]
        return entry_text

    def update_time(self, entry):
        """Update the time in an entry to the time now."""
        self.fix_entry(entry, date=time.strftime("%F %T"))

    def fix_entry(self, entry, date=None):
        """
        Check that an entry is named correctly (considering its metadata
        in-file to be accurate) and fix the filename if required.

        If a date is provided, replace the file's 'date' field with it.
        """
        front_matter = self.get_front_matter(entry)
        entry_text = self.get_entry_text(entry)

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
                # get old date (used to check filename consistency)
                old_date = value
                if date != None:
                    # we were given a date to update to, so do it
                    value = date
                    self.message("Timestamp updated ({} -> {}).".format(
                        line[1], value))
            if var == "title":
                # grab the title to check consistency with later
                entry_title = value
            new_text += "{}: {}\n".format(var, value)
        new_text += JournalCtl.FRONT_MATTER_SEP + "\n"
        new_text += entry_text

        with open(entry_file, JournalCtl.WRITE_ONLY) as f:
            f.write(new_text)

        check_entry = date.split(" ")[0] + "-" \
                + self.get_shell([JournalCtl.SLUG_CMD, entry_title])[0]
        if entry != check_entry:
            self.message("Filename is inconsistent with date/title, fixing using metadata")
            new_file = self.get_entry_file(check_entry)
            shutil.move(entry_file, new_file)
            self.log("moved entry ({} -> {})".format(entry, check_entry))



if __name__ == "__main__":
    jctl = JournalCtl()
    jctl.execute_cmd()
