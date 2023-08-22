#include <stdio.h>

enum space_type {
    NORMAL,
    PREMIUM,
};

struct car_space {
	enum space_type type;
    int parking_rate;
    int licence_plate;
    int occupied_since;
};

void print_car_space(struct car_space car_space) {
    if (car_space.parking_rate == NORMAL) {
        printf("N");
    }
}

int main(void) {
    struct car_space carpark[2][2];
    carpark[1][1].type = PREMIUM;
    print_car_space(carpark[0][0]);
}
