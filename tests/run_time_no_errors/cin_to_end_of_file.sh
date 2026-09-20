#!/bin/sh
# a C++ program which reads until end of file must stop there
# dcc redirects cin through its own streambuf, which used to return the last
# character read over and over instead of reporting end of file, so a loop
# reading to the end of the input never finished

cat >cin_to_end_of_file.cpp <<eof2
#include <iostream>
#include <string>
int main() {
    int n = 0;
    int value;
    while (std::cin >> value) {
        n++;
        if (n > 100) {
            std::cout << "read did not stop at end of file\n";
            return 1;
        }
    }
    std::cout << n << " integers\n";

    return 0;
}
eof2

"$dcc" cin_to_end_of_file.cpp -o cin_to_end_of_file || exit 1

printf '1 2 3\n' | ./cin_to_end_of_file
# the last line having no newline must also end the input
printf '1 2 3' | ./cin_to_end_of_file
printf '' | ./cin_to_end_of_file

cat >getline_to_end_of_file.cpp <<eof2
#include <iostream>
#include <string>
int main() {
    int n = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        n++;
        if (n > 100) {
            std::cout << "getline did not stop at end of file\n";
            return 1;
        }
    }
    std::cout << n << " lines\n";

    return 0;
}
eof2

"$dcc" getline_to_end_of_file.cpp -o getline_to_end_of_file || exit 1
printf 'a\nb\nc\n' | ./getline_to_end_of_file

rm -f cin_to_end_of_file.cpp cin_to_end_of_file
rm -f getline_to_end_of_file.cpp getline_to_end_of_file
