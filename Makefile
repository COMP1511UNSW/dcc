PACKAGED_SOURCE = start_gdb.py drive_gdb.py watch_valgrind.py colors.py main_wrapper.c
SOURCE = __main__.py compile.py explain_compiler_output.py compiler_explanations.py help_cs50.py $(PACKAGED_SOURCE)
PACKAGE_NAME=src

dcc: $(SOURCE) Makefile
	echo 'VERSION = "'`git describe --tags --long`'"' >version.py
	mkdir -p $(PACKAGE_NAME)
	rm -rf $(PACKAGE_NAME)/*
	touch $(PACKAGE_NAME)/__init__.py
	for f in $(PACKAGED_SOURCE); do ln -sf ../$$f $(PACKAGE_NAME); done
	# --symlinks here breaks pkgutil.read_data in compile.py
	zip $@.zip -9 -r $(SOURCE) version.py $(PACKAGE_NAME)
	echo '#!/usr/bin/env python3' >$@
	cat $@.zip >>$@
	rm $@.zip
	chmod 755 $@ 

test: dcc
	tests/do_tests.sh
	
