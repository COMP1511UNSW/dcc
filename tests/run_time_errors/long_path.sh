#!/bin/sh
# a runtime error in a source file with a long absolute path
# must still show the source and variables

temp_dir=$(mktemp -d) || exit 1
trap 'rm -fr "$temp_dir"' EXIT
long_dir="$temp_dir/$(head -c 200 /dev/zero | tr '\0' x)"
mkdir -p "$long_dir"

cat >"$long_dir/index.c" <<eof
int main(void) {
    int a[10] = {0};
    int i = 10;
    return a[i];
}
eof

"$dcc" "$long_dir/index.c" -o "$long_dir/index" || exit 1
"$long_dir/index"
