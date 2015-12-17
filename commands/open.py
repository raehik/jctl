#!/usr/bin/env python3
#
# Short description of the program/script's operation/function.
#

import sys
from command import Command

class CmdOpen(Command):
    def __init__(self):
        Command.__init__(self, "open",
                short_alias="o",
                min_args=1)

    def print_help(self):
        print("I'M MR MEESEEKS LOOK AT MEEEE")

    def exec_main(self, arguments):
        print("(opening '{}')".format(arguments[0]))

if __name__ == "__main__":
    cmd = CmdOpen()
    cmd.exec(["waow"])
    cmd.print_help()
