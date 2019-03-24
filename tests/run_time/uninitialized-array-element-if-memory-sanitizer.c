//dcc_flags="--memory"

int main(int argc, char **argv) { 
	int a[1000];
  	a[42] = 42;
  	if (a[argc]) {
  		a[43] = 43;
  	}
}
