#!/ bin / sh

cat > tmp1.c << eof
#include <stdio.h>
          void
          f(void) {
    fprintf(stderr, "incremental compilation works\n");
}
eof

        cat > tmp2.c << eof extern void f(void);
int main(void) {
    f();
}
eof

        $dcc -
    c tmp1.c $dcc -
    c tmp2.c $dcc tmp1.o tmp2.o./ a.out $dcc tmp1.o tmp2.c./ a.out
