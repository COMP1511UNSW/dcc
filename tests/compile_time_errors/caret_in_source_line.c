// the compiler echoes this line under its message, and it contains a ^, so it
// looked like the line the compiler draws to point at a word - which vetoed
// the message, losing the explanation and leaking the compiler's own summary
int main(void) {
    int y = 4;
    1 ^
    y;
    return 0;
}
