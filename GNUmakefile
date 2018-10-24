SRCS	:= $(sort $(wildcard [0-9][0-9][0-9]-*.py))

dcc: ${SRCS}
	cat $^ > $@
	chmod +x $@ 
