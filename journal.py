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
    def __init__(self):
        # set some variables
        self.journal_dir = os.environ["HOME"] + "/journal"
        self.editor = os.environ["EDITOR"]

        self.__parse_args()

    def exit(self, exit_code=0):
        """Deinitialise and exit."""
        sys.exit(exit_code)

    def __log_message(self, message, pipe=sys.stdout):
        """Log a message to a specific pipe (defaulting to stdout)."""
        FILENAME = sys.argv[0]
        print(FILENAME + ": " + message, file=pipe)

    def log(self, message):
        """If verbose, log an event."""
        if not self.args.verbose:
            return
        self.__log_message(message)

    def error(self, message, exit_code=None):
        """Log an error. If given a 2nd argument, exit using that error code."""
        self.__log_message("error: " + message, sys.stderr)
        if exit_code:
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

    def __parse_args(self):
        self.parser = ArgumentParserUsage(description="Control program for a journal kept in Jekyll.")

        commands = ["new", "open", "commit", "n", "o", "c"]

        # add arguments
        self.parser.add_argument("-v", "--verbose", help="be verbose",
                            action="store_true")
        self.parser.add_argument("-l", "--layout", help="layout to use")
        self.parser.add_argument("command", choices=commands, help="command to run")
        self.parser.add_argument("argument", nargs="?", help="argument for command")

        # parse & grab arguments
        self.args = self.parser.parse_args()
        self.argument = self.args.argument
        self.command = self.args.command

    def run_command(self, args):
        """Run a command, returning the output."""
        # run without a shell so we don't need to escape strange titles
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        out, err = proc.communicate()

        if proc.returncode != 0:
            was_successful = False

        return out.decode("utf-8").strip()

    def execute_args(self):
        if self.command == "open" or self.command == "o":
            if self.argument == None:
                self.error("command requires an argument")
            else:
                matches = self.find_entries(self.argument)
                print(matches)

    def find_entries(self, title):
        files = self.get_entries()
        filename_part = self.run_command(["ezstring", title])

        # look at that list comprehension. goddamn, it's beautiful
        matches = [f for f in files if filename_part in f]

        if len(matches) > 1:
            self.log("more than 1 match found for title '" + title + "'")
            self.exit()

        return matches

    def open_entry(self, entry):
        self.log("Opening entry '" + entry + "' in editor '" + self.editor + "'")
        subprocess.call([self.editor, self.journal_dir + "/" + entry])

    def get_entries(self):
        """Return a list of the relative filename of all journal entries."""
        return os.listdir(self.journal_dir)

    def get_titles(self):
        """Return a list of the title of each entry."""
        MATCH_GROUP_1 = 1
        title_regex = re.compile('^title: "?(.*?)"?$')

        files = [self.journal_dir + "/" + entry for entry in self.get_entries()]

        titles = []
        for f in files:
            with open(f) as current_file:
                for line in current_file:
                    result = TITLE.match(line)
                    if result is not None:
                        titles.append(result.group(MATCH_GROUP_1))
                        break
                # TODO: no title found
                #titles.append("ayy lmao")


        #combined = []
        #for title in titles:
        #    combined.append([title, run_command(["ezstring", title])])

        #print(combined)


if __name__ == "__main__":
    jctl = JournalCtl()
    jctl.execute_args()
