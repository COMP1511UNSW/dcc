// the note clang prints here echoes the line below, whose comment names a
// header - which is not the compiler suggesting it, so the student must get
// the advice for a function it does not recognise, not for a missing #include
void myfunc2(void); // remember to include <stdio.h> first

int main(void) {
    myfunc();
    return 0;
}
