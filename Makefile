SOURCE = __main__.py compile.py explain_compiler_output.py help_cs50.py start_gdb.py drive_gdb.py
EMBEDDED_SOURCE = start_gdb.py drive_gdb.py main_wrapper.c
	
dcc: $(SOURCE) embedded_source.py Makefile
	zip $@.zip -9 -r $(SOURCE) embedded_source.py
	echo '#!/usr/bin/env python3' >$@
	cat $@.zip >>$@
	rm $@.zip
	chmod 755 $@ 

embedded_source.py: $(EMBEDDED_SOURCE)
	./build_embedded_source.py $(EMBEDDED_SOURCE) > $@

test: dcc
	tests/do_tests.sh
	