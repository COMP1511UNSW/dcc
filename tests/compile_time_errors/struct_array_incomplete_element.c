// an array of an incomplete struct is not a missing array bound
struct student;

struct student cohort[10];

int main(void) {
    return 0;
}
