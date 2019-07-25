Forgetting to print a newline is a common mistake.

For example, this program doesn't print a newline.

```c
int main(void) {
    int answer = 7 * 6;
    printf("%d", answer);
}

```

So when its compiled and run you'll see something like this:

```console
$ dcc answer.c
$ ./a.out
42$
```

If you add a **\n** to the _printf_ like this:

```c
int main(void) {
    int answer = 7 * 6;
    printf("%d\n", answer);
}
```

It will fix the problem:


```console
$ dcc answer.c
$ ./a.out
42
$
```

