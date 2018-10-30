#!/usr/bin/env python3

# andrewt@unsw.edu.au May 2013-2017
# compile a C program with runtime checking enabled
# run-time errors are intercepted and an explanation
# printed in a form comprehensible to beginner programmers
# using	 information obtained from	gdb
# clang errors are explained using matcher from https://github.com/cs50/help50
# This program is executed in 4 ways
#
# 1) Invoked by the user from the command line to do the compilation
#	 the binary produced has code added which intercepts runtime errors and runs this program
#
# 2) invoked from the C binary when a runtime error occurs - it then runs gdb
#
# 3) invoked via gdb to print details of the program state when the runtime error occurred
#
# 4) invoked from the C binary to watch for valgrind errors on stdin when using valgrind

# The above 4 execution modes have been bundled into one file to simplify installation 

from __future__ import print_function

import collections, os, platform, re, signal, subprocess, sys, traceback


dcc_path = os.path.realpath(sys.argv[0])
# replace CSE mount path with /home - otherwise breaks sometimes with ssh jobs
dcc_path = re.sub(r'/tmp_amd/\w+/\w+ort/\w+/\d+/', '/home/', dcc_path)
dcc_path = re.sub(r'^/tmp_amd/\w+/\w+ort/\d+/', '/home/', dcc_path)	
dcc_path = re.sub(r'^/(import|export)/\w+/\d+/', '/home/', dcc_path)	


