#!/bin/sh
# ios::sync_with_stdio(false), which students copy from tutorials to make cin
# faster, used to leave libstdc++'s own streambufs in cin, cout and cerr
# dcc's teardown then deleted one of those static buffers, reporting a bad
# free, and everything the program printed was lost

cat >sync_with_stdio.cpp <<eof2
#include <iostream>
int main() {
    std::ios::sync_with_stdio(false);

    int value;
    std::cout << "enter a number: ";
    std::cin >> value;
    std::cout << "you entered " << value << "\n";
    std::cerr << "finished\n";

    return 0;
}
eof2

"$dcc" sync_with_stdio.cpp -o sync_with_stdio || exit 1

printf '42\n' | ./sync_with_stdio 2>&1

rm -f sync_with_stdio.cpp sync_with_stdio
