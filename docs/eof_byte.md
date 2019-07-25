Accidentally printing the special **EOF** value returned by the functions _getchar_, _getc_ and _fgetc_.

For example, this program prints  the **EOF** value before the loop exits:

```c
#include <stdio.h>

int main(void) {
    int c = 0;
    while (c != EOF) {
        int c = getchar();
        putchar(c);
    }
    return 0;
}
```

The special **EOF** value typically is defined to be `-1` (in `<stdio.h>`)
and when printed is invisible. So the program appears to work.

```console
$ dcc cat.c
$ echo cat | ./a.out
cat
$
```

But the program will fail automated testing because it is printing an extra byte.

This is a program that output the same bytes as the above example.

```c
#include <stdio.h>

int main(void) {

    putchar('c');
    putchar('a');
    putchar('t');
    putchar('\n');
    putchar(EOF);
    
    return 0;
}
```

This is a program which doesn't print the EOF value:

```c
#include <stdio.h>

int main(void) {
    int c = getchar();
    while (c != EOF) {
        putchar(c);
        c = getchar();
    }
    return 0;
}
```
