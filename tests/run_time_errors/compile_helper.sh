#!/bin/sh
# after a compile-time error dcc runs the helper named by DCC_COMPILE_HELPER
# with details of the message in the environment

cat >compile_helper.c <<eof
int main(void) {
    return x;
}
eof

cat >helper.sh <<'eof'
#!/bin/sh
echo "helper: type=$HELPER_TYPE file=$HELPER_FILE line=$HELPER_LINE col=$HELPER_COL label=$HELPER_LABEL" 1>&2
echo "helper: explanation starts: $(echo "$HELPER_EXPLANATION" | sed 1q)" 1>&2
echo "helper: source has $(echo "$HELPER_SOURCE" | wc -l) lines" 1>&2
echo "helper: json has label: $(echo "$HELPER_JSON" | grep -c '"label":"use_of_undeclared_identifier"')" 1>&2
eof
chmod 755 helper.sh

DCC_COMPILE_HELPER="$(pwd)/helper.sh" "$dcc" compile_helper.c
rm -f compile_helper.c helper.sh
