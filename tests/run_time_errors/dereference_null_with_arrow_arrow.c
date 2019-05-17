#include <stdio.h>
struct list_node {
    struct list_node *next;
    int data;
};
int main(void) { 
    struct list_node s = {0};
    struct list_node *a = &s;
    a->next->next->data = 42;
}
