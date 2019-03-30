//dcc_flags=--valgrind
//dcc_flags=--memory

int main(int argc, char **argv) { 
	int i, a[1000], sum = 0;
  	a[42] = 42;
  	for (i = 0; i < 1000; i++)
  		sum += a[i];
  	if (sum < 1000) {
  		return sum;
  	}
}
