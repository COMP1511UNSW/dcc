#include <iostream>

void twod(int b[5][4]) {
    std::cout << b[5][2] << "\n";
}

int main(int argc, char **argv) {
    int a[5][4] = { { 0 } };
    twod(a);
    return 0;
}
