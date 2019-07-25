Accidentally printing a zero byte is easy to do in a C program but hard to debug.

For example, this program accidentally prints a zero byte when it prints `string[3]`:

```c
#include <stdio.h>

int main(void) {
    char *string = "dog";
    
    for (int i = 0; i < 4; i++) {
        putchar(string[i]);
    }
    
    putchar('\n');
    
    return 0;
}
```

And because printing of a  zero byte is invisible, the program  looks like it works:

```console
$ dcc dog.c
$ ./a.out
dog
$
```



This is an equivalent program:

```c
#include <stdio.h>

int main(void) {

    putchar('d');
    putchar('o');
    putchar('g');
    putchar('\0');  // or putchar(0);  
    putchar('\n');
    
    return 0;
}
```

This is a program which doesn't print the zero byte:

```c
#include <stdio.h>

int main(void) {
    char *string = "dog";
    
    for (int i = 0; string[i] != '\0'; i++) {
        putchar(string[i]);
    }
    
    putchar('\n');
    
    return 0;
}
```

It is  equivalent to this program:

```c
#include <stdio.h>

int main(void) {

    putchar('d');
    putchar('o');
    putchar('g');
    putchar('\n');
    
    return 0;
}
```
