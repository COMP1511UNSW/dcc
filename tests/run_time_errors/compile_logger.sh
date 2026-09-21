#!/bin/sh
# after every compilation dcc runs the logger named by DCC_COMPILE_LOGGER
# with the compiler's exit status, first line of output and explanation labels

cat >compile_logger.c <<eof
#include <stdio.h>
int main(void) {
    int i = 0;
    scanf("%d", i);
    return 0;
}
eof

cat >logger.sh <<'eof'
#!/bin/sh
echo "logger: exit=$DCC_LOGGER_EXIT labels=$DCC_LOGGER_LABELS argv=$DCC_LOGGER_ARGV" 1>&2
echo "logger: first line: $DCC_LOGGER_FIRST_LINE" 1>&2
echo "logger: json has source: $(echo "$DCC_LOGGER_JSON" | grep -c '"source":"#include')" 1>&2
eof
chmod 755 logger.sh

DCC_COMPILE_LOGGER="$(pwd)/logger.sh" "$dcc" compile_logger.c
echo "logger for a clean compile:" 1>&2
printf 'int main(void) {\n    return 0;\n}\n' >clean.c
DCC_COMPILE_LOGGER="$(pwd)/logger.sh" "$dcc" clean.c
rm -f compile_logger.c clean.c logger.sh a.out
