#!/bin/sh
# a wide character with no representation in the locale must not fail the
# stream - it used to, and everything the program printed afterwards was
# silently discarded
# std::wcin.putback() of a character that was not just read must work too

cat >wide_stream_conversion.cpp <<eof2
#include <iostream>
#include <locale>
#include <string>
int main() {
    std::wcout << L"1 café\n";
    std::wcout << L"2 still printing\n";

    // imbuing a locale without setlocale() is the usual recipe and must not
    // lose output either
    try {
        std::wcout.imbue(std::locale("C.UTF-8"));
    } catch (...) {
    }
    std::wcout << L"3 café\n";
    std::wcout << L"4 still printing\n";

    std::wstring word;
    std::wcin >> word;
    std::wcin.putback(L'X');
    std::wstring rest;
    std::getline(std::wcin, rest);
    std::wcout << L"5 [" << word << L"] [" << rest << L"]\n";

    return 0;
}
eof2

"$dcc" wide_stream_conversion.cpp -o wide_stream_conversion || exit 1

printf 'hello there\n' | ./wide_stream_conversion

rm -f wide_stream_conversion.cpp wide_stream_conversion
