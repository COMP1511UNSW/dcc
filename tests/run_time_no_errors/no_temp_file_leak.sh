#!/bin/sh
# failed compilations must not leave files in the temporary directory

temp_dir=$(mktemp -d) || exit 1
trap 'rm -fr "$temp_dir"' EXIT
mkdir "$temp_dir/tmp"

cat >"$temp_dir/syntax_error.c" <<eof
int main(void) { int x = 1 return x; }
eof
cat >"$temp_dir/no_main.c" <<eof
int f(void) { return 0; }
eof

for source in syntax_error no_main; do
	for flags in "" -fsanitize=address; do
		# shellcheck disable=SC2086
		TMPDIR="$temp_dir/tmp" "$dcc" $flags "$temp_dir/$source.c" -o "$temp_dir/$source" 2>/dev/null
	done
done
echo "files left in temporary directory: $(ls -A "$temp_dir/tmp" | wc -l)"
