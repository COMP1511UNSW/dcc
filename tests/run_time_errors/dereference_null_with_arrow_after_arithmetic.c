#include <stdio.h>
struct node {
    int data;
};
int main(void) {
    struct node *a = NULL;
    return (a + 1)->data;
}
