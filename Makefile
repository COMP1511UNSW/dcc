SOURCE = __main__.py compile.py explain_compiler_output.py help_cs50.py start_gdb.py drive_gdb.py watch_valgrind.py
EMBEDDED_SOURCE = start_gdb.py drive_gdb.py watch_valgrind.py main_wrapper.c
	
dcc: $(SOURCE) embedded_source.py Makefile
	echo 'VERSION = "'`git describe --tags --long`'"' >version.py
	zip $@.zip -9 -r $(SOURCE) embedded_source.py
	echo '#!/usr/bin/env python3' >$@
	cat $@.zip >>$@
	rm $@.zip
	chmod 755 $@ 

embedded_source.py: $(EMBEDDED_SOURCE)
	./build_embedded_source.py $(EMBEDDED_SOURCE) > $@

test: dcc
	tests/do_tests.sh
	
