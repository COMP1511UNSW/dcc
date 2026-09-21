#!/bin/sh
# the runtime helper is given the input the program read from stdin
# (HELPER_STDIN and friends are filled from the buffer kept by dcc_save_stdin.c)

cat >runtime_helper_stdin.c <<eof2
#include <stdio.h>
int main(void) {
    int n;
    int a[4] = {0};
    if (scanf("%d", &n) != 1) {
        return 1;
    }
    return a[n];
}
eof2

cat >helper.sh <<'eof2'
#!/bin/sh
printf 'helper: stdin=[%s] truncated=%s valid_utf8=%s\n' "$HELPER_STDIN" "$HELPER_STDIN_TRUNCATED" "$HELPER_STDIN_VALID_UTF8"
printf 'helper: json has stdin: %s\n' "$(printf '%s' "$HELPER_JSON" | grep -c '"stdin":"7\\n"')"
eof2
chmod 755 helper.sh

"$dcc" runtime_helper_stdin.c -o runtime_helper_stdin || exit 1
echo 7 | DCC_RUNTIME_HELPER="$(pwd)/helper.sh" ./runtime_helper_stdin
rm -f runtime_helper_stdin.c runtime_helper_stdin helper.sh
