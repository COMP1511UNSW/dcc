int main(int argc, char *argv[]) {
	int s;
	if (argc > 3)
		s = 1;
  	else if (argc < 2)
    	s = 2;
  
	return s;
}