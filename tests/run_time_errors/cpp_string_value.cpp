//dcc_flags=-fsanitize=address
// clang's default limited debug info leaves out std::string's members, and
// gdb's pretty-printer then fails where the string's value should be
#include <string>

int main(int argc, char *argv[]) {
    std::string s = "hi";
    int a[1] = {0};
    return a[argc + 2];
}
