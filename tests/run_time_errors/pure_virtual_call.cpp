// the C++ library calls terminate here with no exception thrown,
// so it must not be explained as an uncaught exception
struct Shape {
    Shape() { setup(); }
    void setup();
    virtual void draw() = 0;
    virtual ~Shape() {}
};

void Shape::setup() { draw(); }

struct Square : Shape {
    void draw() override {}
};

int main(void) {
    Square s;
    return 0;
}
