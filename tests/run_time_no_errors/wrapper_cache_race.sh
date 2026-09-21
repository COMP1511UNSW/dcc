#!/bin/sh
# dcc keeps the object it compiles from its own wrapper code in a cache shared
# by every dcc the user runs.  Touching an entry to record its use, and linking
# it from the cache, were both done outside the guard against it disappearing,
# so a concurrent dcc removing a least recently used entry killed this one with
# a Python traceback.

cat >wrapper_cache_race.py <<'eof'
# stands in for a concurrent dcc removing the least recently used cached
# object: waits for the cache entry to be opened, then unlinks it
import ctypes, ctypes.util, os, struct, sys

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
fd = libc.inotify_init()
directory = sys.argv[1]
libc.inotify_add_watch(fd, directory.encode(), 0x20)  # IN_OPEN
buffer = b""
while True:
    buffer += os.read(fd, 4096)
    while len(buffer) >= 16:
        _, _, _, name_length = struct.unpack("iIII", buffer[:16])
        if len(buffer) < 16 + name_length:
            break
        name = buffer[16 : 16 + name_length].rstrip(b"\0").decode()
        buffer = buffer[16 + name_length :]
        if name.endswith(".o"):
            try:
                os.unlink(os.path.join(directory, name))
            except OSError:
                pass
eof

cat >wrapper_cache_race.c <<'eof'
#include <stdio.h>

int main(void) {
	printf("hello\n");
	return 0;
}
eof

XDG_CACHE_HOME="$PWD/cache"
export XDG_CACHE_HOME

# the first compilation puts the wrapper object in the cache
"$dcc" wrapper_cache_race.c -o wrapper_cache_race || exit 1

timeout 60 python3 wrapper_cache_race.py "$XDG_CACHE_HOME/dcc" &
racer=$!
sleep 1

for attempt in 1 2 3
do
	"$dcc" wrapper_cache_race.c -o wrapper_cache_race 2>error_output || {
		echo "compilation $attempt failed while the cache was being emptied"
		sed 's/^/dcc said: /' error_output
		break
	}
	./wrapper_cache_race
done

kill $racer 2>/dev/null
wait $racer 2>/dev/null
rm -fr wrapper_cache_race.py wrapper_cache_race.c wrapper_cache_race error_output cache
