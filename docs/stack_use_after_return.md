You are not permitted to assign arrays in C.

You can NOT do this:

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

You can instead use a loop to copy each array element individually.

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
