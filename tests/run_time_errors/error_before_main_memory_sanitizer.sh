#!/bin/sh
# MemorySanitizer has nothing recorded to say what a run-time error before
# main was, and dcc calls anything it can not name an uninitialized variable,
# so it must leave the sanitizer's own report to speak for itself

cat >memory_sanitizer_before_main.c <<eof
__attribute__((constructor)) static void initialize(void) {
    int *p = 0;
    *p = 1;
}

int main(void) {
    return 0;
}
eof

"$dcc" -fsanitize=memory memory_sanitizer_before_main.c -o memory_sanitizer_before_main || exit 1
./memory_sanitizer_before_main 2>memory_sanitizer_before_main.out
{
	echo "sanitizer reported the write: $(grep -c 'MemorySanitizer: SEGV' memory_sanitizer_before_main.out)"
	echo "dcc called it uninitialized: $(grep -c 'uninitialized variable' memory_sanitizer_before_main.out)"
} >&2
rm -f memory_sanitizer_before_main.c memory_sanitizer_before_main memory_sanitizer_before_main.out
