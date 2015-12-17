#!/usr/bin/env python3
#
# Short description of the program/script's operation/function.
#

import sys

class Command:
    def __init__(self, cmd_name, short_alias=None, min_args=0, verbose=False):
        self.cmd_name = cmd_name
        self.short_alias = short_alias
        self.verbose = verbose

        if isinstance(min_args, int):
            self.min_args = min_args
        else:
            self.error("min_args is not an integer", 20)

    # Logging {{{
    def __log_message(self, message, pipe=sys.stdout):
        """Log a message to a specific pipe (defaulting to stdout)."""
        FILENAME = sys.argv[0]
        print("COMMAND {}: {}".format(self.cmd_name, message), file=pipe)

    def log(self, message):
        """If verbose, log an event."""
        if not self.verbose:
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
    # Logging }}}

    def exec(self, arguments):
        no_of_args = len(arguments)
        if no_of_args < self.min_args:
            self.error("expected {} arguments (got {})".format(self.min_args, no_of_args))

        # checks were successful, execute command
        self.exec_main(arguments)

    def print_help(self):
        print("No help for command '{}'".format(self.cmd_name))

if __name__ == "__main__":
    print("NOTE: this module is *not* meant to be run (it's a base class for jctl commands)")
    sys.exit(1)
