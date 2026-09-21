struct stack;

int top(struct stack *s) {
    return s->top;
}

int main(void) {
    return top(0);
}
