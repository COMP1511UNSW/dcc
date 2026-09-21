#!/bin/sh
# clog and the wide streams must be redirected like cout and cerr are
# they used to keep the stdout and stderr the C++ streams were constructed
# with, before dcc replaced them, so both sanitizer processes wrote them and
# their output appeared twice and out of order with cout

cat >clog_and_wide_streams.cpp <<eof2
#include <iostream>
int main() {
    std::cout << "1 cout\n";
    std::clog << "2 clog\n";
    std::cerr << "3 cerr\n";
    std::wcout << L"4 wcout\n";
    std::wclog << L"5 wclog\n";
    std::wcerr << L"6 wcerr\n";
    std::cout << "7 cout\n";

    return 0;
}
eof2

"$dcc" clog_and_wide_streams.cpp -o clog_and_wide_streams || exit 1

# stderr is merged into stdout so the order of the writes is visible
./clog_and_wide_streams 2>&1

cat >wcin.cpp <<eof2
#include <iostream>
#include <string>
int main() {
    int value;
    std::wstring word;
    std::wcin >> value >> word;
    std::wcout << L"read " << value << L" " << word << L"\n";

    return 0;
}
eof2

"$dcc" wcin.cpp -o wcin || exit 1

printf '42 apples\n' | ./wcin

rm -f clog_and_wide_streams.cpp clog_and_wide_streams wcin.cpp wcin
