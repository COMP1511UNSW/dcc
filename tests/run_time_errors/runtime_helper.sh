#!/bin/sh
# after a runtime error the program runs the helper named by DCC_RUNTIME_HELPER
# with details of the error in the environment

cat >runtime_helper.c <<eof
int main(void) {
    int a[10] = {0};
    int i = 10;
    return a[i];
}
eof

cat >helper.sh <<'eof'
#!/bin/sh
echo "helper: file=$HELPER_FILE line=$HELPER_LINE col=$HELPER_COL"
echo "helper: explanation starts: $(echo "$HELPER_EXPLANATION" | sed 1q)"
echo "helper: variables: $(echo "$HELPER_VARIABLES" | tr '\n' ' ')"
echo "helper: json has file: $(echo "$HELPER_JSON" | grep -c '"file":"runtime_helper.c"')"
echo "helper: working directory is not DCC_PWD: $(test "$(pwd)" != "$DCC_PWD" && echo yes)"
eof
chmod 755 helper.sh

"$dcc" runtime_helper.c -o runtime_helper || exit 1
DCC_RUNTIME_HELPER="$(pwd)/helper.sh" ./runtime_helper
rm -f runtime_helper.c runtime_helper helper.sh
