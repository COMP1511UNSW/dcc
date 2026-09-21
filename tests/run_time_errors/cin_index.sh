#!/bin/sh
# C++ programs read stdin through cin, which dcc redirects to its stdin stream
# so the dual sanitizers stay synchronized, and the error is still explained

cat >cin_index.cpp <<eof2
#include <iostream>
int main() {
    int n;
    int a[4] = {0};
    std::cin >> n;
    std::cout << "you entered " << n << "\n";
    std::cout << a[n] << "\n";
    return 0;
}
eof2

"$dcc" cin_index.cpp -o cin_index || exit 1
echo 7 | ./cin_index
rm -f cin_index.cpp cin_index
