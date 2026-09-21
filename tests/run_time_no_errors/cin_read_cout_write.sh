#!/bin/sh
# dcc renames unistd.h functions with -D so a program's own read or write can
# not displace the one its wrapper calls.  Those macros rewrote the
# declarations in <istream> and <ostream> as well, so std::cin.read and
# std::cout.write were left undefined at link time.

cat >cin_read_cout_write.cpp <<'eof'
#include <iostream>

// a C++ function of the same name is mangled, so it can not displace the
// unistd.h function dcc's wrapper calls
int read(int n) {
    return n + 1;
}

int main(void) {
    char buffer[4] = {0};
    std::cin.read(buffer, 3);
    std::cout.write(buffer, std::cin.gcount());
    std::cout << " " << read(41) << "\n";
    return 0;
}
eof

"$dcc" cin_read_cout_write.cpp -o cin_read_cout_write || exit 1
printf 'abc' | ./cin_read_cout_write

# but an extern "C" function of the same name is not mangled and would displace
# the one the wrapper calls, so C++ source still needs the renames
cat >cpp_extern_c_read.cpp <<'eof'
#include <iostream>

extern "C" long read(int fd, void *buffer, unsigned long n) {
    (void)fd;
    (void)buffer;
    (void)n;
    return 0;
}

int main(void) {
    int x = 0;
    std::cin >> x;
    std::cout << "x=" << x << "\n";
    return 0;
}
eof

"$dcc" cpp_extern_c_read.cpp -o cpp_extern_c_read || exit 1
echo 42 | ./cpp_extern_c_read

rm -f cin_read_cout_write.cpp cin_read_cout_write
rm -f cpp_extern_c_read.cpp cpp_extern_c_read
