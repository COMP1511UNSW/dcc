#include <iostream>
#include <stdio.h>

#define STDIOBUF_BUFFER_SIZE 8192
#define STDIOBUF_PUSHBACK_MAX 4

// redirect cin, cout, cerr to stdin, stdout, stderr
// to allow dcc to synchronize across 

// similar code at http://ilab.usc.edu/rjpeters/groovx/stdiobuf_8cc-source.html
// documentation at https://cplusplus.com/reference/streambuf/streambuf/

class stdiobuf: public std::streambuf {
	FILE *stdio_stream;
    char buffer[STDIOBUF_PUSHBACK_MAX + STDIOBUF_BUFFER_SIZE] = {0};
public:
    stdiobuf(FILE *f) {
    	stdio_stream = f;
    	char *b = buffer + STDIOBUF_PUSHBACK_MAX;
        setp(b, b);
        setg(buffer, b, b);
    }


	// input methods
    int underflow() {
        if (gptr() == egptr()) {
	    	char *b = buffer + STDIOBUF_PUSHBACK_MAX;
	    	// just get one character to avoid introducing inappropriate buffering
	    	// bufferring will still be happening in stdio
           	int c = fgetc(stdio_stream);
            if (c != EOF) {
             	b[0] = c;
            }
            setg(buffer, b, b + 1);
        }
        return gptr() == egptr() ? traits_type::eof() : traits_type::to_int_type(*gptr());
    }
    
    // do we need to implement pbackfail?
		

	// output methods
	int overflow(int c) {
		if (c != EOF) {
			*pptr() = c;
			pbump(1);
		}
		return flush_buffer() == EOF ? EOF : traits_type::to_int_type(c);
	}

	int sync() {
		return flush_buffer() == EOF ? -1 : 0;
	}

	// helper function
    int flush_buffer() {
		const size_t num = pptr() - pbase();
		if (fwrite(pbase(), 1, num, stdio_stream) != num) {
			return EOF;
		}
		pbump(-num);
		return num;
    }
};


static std::streambuf *original_cin_streambuf;

extern "C" void __dcc_replace_cin(FILE *stream) {
    original_cin_streambuf = std::cin.rdbuf(new stdiobuf(stream));
}

extern "C" void __dcc_restore_cin(void) {
	if (original_cin_streambuf) {
		delete std::cin.rdbuf(original_cin_streambuf);
	} 
}


static std::streambuf *original_cout_streambuf;

extern "C" void __dcc_replace_cout(FILE *stream) {
 	original_cout_streambuf = std::cout.rdbuf(new stdiobuf(stream));
}

extern "C" void __dcc_restore_cout() {
	if (original_cout_streambuf) {
		std::cout << std::flush;
		delete std::cout.rdbuf(original_cout_streambuf); 
	} 
}


static std::streambuf *original_cerr_streambuf;

extern "C" void __dcc_replace_cerr(FILE *stream) {
    original_cerr_streambuf = std::cerr.rdbuf(new stdiobuf(stream));
}

extern "C" void __dcc_restore_cerr() {
	if (original_cerr_streambuf) {
		std::cerr << std::flush;
		delete std::cerr.rdbuf(original_cerr_streambuf); 
	} 
}
