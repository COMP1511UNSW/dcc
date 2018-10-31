SRCS	:= $(sort $(wildcard *.*))

dcc: ${SRCS}
	./build.py > $@
	chmod +x $@ 

test: dcc
	tests/do_tests.sh
