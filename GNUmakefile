SRCS	:= $(sort $(wildcard [0-9][0-9][0-9]-*.*))

dcc: ${SRCS}
	cat $^ > $@
	chmod +x $@ 

tests: dcc
	tests/do_tests.sh
