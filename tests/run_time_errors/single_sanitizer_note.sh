#!/bin/sh
# dropping to AddressSanitizer alone costs uninitialized variable detection,
# so dcc must say so, for C and for C++ alike

cat >single_sanitizer_note.c <<eof
#include <unistd.h>
int main(void) { return 0; }
eof

cat >single_sanitizer_note.cpp <<eof
#include <vector>
int main(void) { return 0; }
eof

for source in single_sanitizer_note.c single_sanitizer_note.cpp; do
	echo "*** $source" 1>&2
	"$dcc" "$source" -o single_sanitizer_note 2>&1 >/dev/null |
		grep 'uninitialized variables will not be detected' 1>&2
done

# the downgrade for -pthread and for spawn.h is asserted here because
# pthread_flag.c and posix_spawn.c now name their sanitizer explicitly
cat >single_sanitizer_note_threads.c <<eof
int main(void) { return 0; }
eof

cat >single_sanitizer_note_spawn.c <<eof
#include <spawn.h>
int main(void) { return 0; }
eof

echo "*** -pthread" 1>&2
"$dcc" -pthread single_sanitizer_note_threads.c -o single_sanitizer_note 2>&1 >/dev/null |
	grep 'uninitialized variables will not be detected' 1>&2

echo "*** spawn.h" 1>&2
"$dcc" single_sanitizer_note_spawn.c -o single_sanitizer_note 2>&1 >/dev/null |
	grep 'uninitialized variables will not be detected' 1>&2

# the header named must be the same on every run: the set it comes from
# has no fixed iteration order
cat >single_sanitizer_note_many.c <<eof
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
int main(void) { return 0; }
eof

echo "*** distinct notes over 8 runs with several unsafe headers" 1>&2
for _ in 1 2 3 4 5 6 7 8; do
	"$dcc" single_sanitizer_note_many.c -o single_sanitizer_note 2>&1 >/dev/null |
		grep 'uninitialized variables will not be detected'
done | sort -u | wc -l 1>&2

# naming a single sanitizer is the user's choice, not a downgrade
echo "*** -fsanitize=address" 1>&2
"$dcc" -fsanitize=address single_sanitizer_note.c -o single_sanitizer_note 2>&1 >/dev/null |
	grep -c 'uninitialized variables will not be detected' 1>&2

# -fsyntax-only never produces a program, so the note has nothing to warn about
echo "*** -fsyntax-only" 1>&2
"$dcc" -fsyntax-only single_sanitizer_note.c 2>&1 >/dev/null |
	grep -c 'uninitialized variables will not be detected' 1>&2

rm -f single_sanitizer_note.c single_sanitizer_note.cpp \
	single_sanitizer_note_threads.c single_sanitizer_note_spawn.c \
	single_sanitizer_note_many.c single_sanitizer_note
