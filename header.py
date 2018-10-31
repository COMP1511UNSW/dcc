#!/usr/bin/env python3
# andrewt@unsw.edu.au May 2013-2017
# compile a C program with runtime checking enabled
# run-time errors are intercepted and an explanation
# printed in a form comprehensible to beginner programmers
# using	 information obtained from	gdb
# clang errors are explained using matcher from https://github.com/cs50/help50

from __future__ import print_function

# This program can be executed in 4 ways
#
# 1) Invoked by the user from the command line to do the compilation
#	 the binary produced has code added which intercepts runtime errors and runs this program
#
# 2) invoked from the C binary when a runtime error occurs - it then runs gdb (--no_embed_source only)
#
# 3) invoked via gdb to print details of the program state when the runtime error occurred (--no_embed_source only)
#
# 4) invoked from the C binary to watch for valgrind errors on stdin when using valgrind

# The above 4 execution modes have been bundled into one file to simplify installation 


# Unless the --no_embed_source option is specified, a tar file is embedded in the binary
# containing the C source files for the user's program plus the files start_gdb.py and drive_gdb.py
#
# If a runtime error occurs the tar file is extracted into a temporary directory
# and start_gdb.py starts gdb controlled by drive_gdb.py to print details of the program state

# --valgrind currently implies --no_embed_source option
