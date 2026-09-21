#!/bin/sh
# a source file which is not valid UTF-8 (e.g. a Latin-1 comment)
# must not stop the runtime helper being run with the source

printf '// caf\351 - a Latin-1 comment\nint main(void) {\n    int a[10] = {0};\n    int i = 10;\n    return a[i];\n}\n' >latin1.c

cat >helper.sh <<'eof2'
#!/bin/sh
echo "helper: file=$HELPER_FILE line=$HELPER_LINE"
echo "helper: source lines: $(printf '%s\n' "$HELPER_SOURCE" | wc -l)"
echo "helper: json parses: $(printf '%s' "$HELPER_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["line"], len(d["source"].splitlines()))')"
eof2
chmod 755 helper.sh

"$dcc" latin1.c -o latin1 || exit 1
DCC_RUNTIME_HELPER="$(pwd)/helper.sh" ./latin1
rm -f latin1.c latin1 helper.sh
