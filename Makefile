PACKAGED_SOURCE = start_gdb.py drive_gdb.py watch_valgrind.py colors.py main_wrapper.c
SOURCE = __main__.py compile.py explain_compiler_output.py compiler_explanations.py help_cs50.py $(PACKAGED_SOURCE)
PACKAGE_NAME=src

dcc: $(SOURCE) Makefile
	echo 'VERSION = "'`git describe --tags`'"' >version.py
	rm -rf $(PACKAGE_NAME)
	mkdir -p $(PACKAGE_NAME)
	touch $(PACKAGE_NAME)/__init__.py
	for f in $(PACKAGED_SOURCE); do ln -sf ../$$f $(PACKAGE_NAME); done
	# --symlinks here breaks pkgutil.read_data in compile.py
	zip $@.zip -9 -r $(SOURCE) version.py $(PACKAGE_NAME)
	echo '#!/usr/bin/env python3' >$@
	cat $@.zip >>$@
	rm $@.zip
	chmod 755 $@ 
	rm -rf $(PACKAGE_NAME)

dcc.1: dcc help2man_include.txt
	help2man --include=help2man_include.txt ./dcc >dcc.1
	
tests: dcc
	tests/do_tests.sh ./dcc
	
tests_all_clang_versions: dcc
	set -x ; for compiler in /usr/bin/clang-[1-24-9]* ; do tests/do_tests.sh ./dcc $$compiler; done
	
debian: dcc
	rm -rf debian
	mkdir -p debian/DEBIAN/usr/local/bin/
	cp -p dcc debian/DEBIAN/usr/local/bin/
	echo Package: dcc >debian/DEBIAN/control
	echo Architecture: all >>debian/DEBIAN/control
	echo Description:  a C compiler which explain errors to novice programmers >>debian/DEBIAN/control