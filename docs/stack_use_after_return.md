A C function can not return a pointer to a local variable.

A local variable variable does not exist after the function returns.

For example, you can NOT do this:

```c
struct node {
    struct node *next;
    int         data;
};

struct node *create_node(int i) {
    struct node n;

    n.data = i;
    n.next = NULL;

    return &n;
}
```

A function can return a pointer provided by malloc:

For example, you can do this:


```c
struct node {
    struct node *next;
    int         data;
};

struct node *create_node(int i) {
    struct node *p;

    p = malloc(sizeof (struct node));
    p->data = i;
    p->next = NULL;

    return p;
}
```
