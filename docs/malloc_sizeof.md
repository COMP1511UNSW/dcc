You must be careful when using malloc to allocate the correct number of bytes.

For example, this program contains a common error.

The programmer would like malloc to allocate enough bytes
to hold a struct node.


But instead they ask malloc for enough bytes to hold a **pointer** to a **struct node**.

```c
struct node {
    struct node *next;
    int         data;
};

int main(void) {

    struct node *n;

    n = malloc(sizeof (struct node *));
    n->data = NULL;

}
```

This program asks malloc for enough bytes to hold a **struct node**.

```c
struct node {
    struct node *next;
    int         data;
};

int main(void) {

    struct node *n;

    n = malloc(sizeof (struct node));
    n->data = NULL;

}
```
