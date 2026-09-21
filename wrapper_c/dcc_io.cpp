#include <iostream>
#include <climits>
#include <cwchar>
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
            if (c == EOF) {
            	// leave the get area empty, otherwise the character read
            	// before this one is returned again, and again, and the
            	// stream never reports end of file
            	setg(buffer, b, b);
            } else {
             	b[0] = c;
            	setg(buffer, b, b + 1);
            }
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


// the wide streams (wcin, wcout, wcerr, wclog) keep the streambuf they were
// constructed with, which holds the stdio stream from before dcc replaced it,
// so their bytes bypass the synchronization and both sanitizers write them
// wide characters are converted here and passed to stdio as bytes, so the
// wide streams stay in order with the ordinary streams sharing the FILE

class wstdiobuf: public std::wstreambuf {
	FILE *stdio_stream;
	mbstate_t read_state = {};
	mbstate_t write_state = {};
	// buffer[0] is a slot for a character the program puts back
	wchar_t buffer[2] = {0};
public:
	wstdiobuf(FILE *f) {
		stdio_stream = f;
		setp(NULL, NULL);
		setg(buffer, buffer + 2, buffer + 2);
	}

	int_type underflow() {
		if (gptr() == egptr()) {
			// read a byte at a time so no input is consumed beyond the
			// character asked for
			for (;;) {
				int c = fgetc(stdio_stream);
				if (c == EOF) {
					return traits_type::eof();
				}
				char b = (char)c;
				size_t n = mbrtowc(buffer + 1, &b, 1, &read_state);
				if (n == (size_t)-1) {
					return traits_type::eof();
				}
				if (n != (size_t)-2) {
					break;
				}
			}
			setg(buffer, buffer + 1, buffer + 2);
		}
		return traits_type::to_int_type(*gptr());
	}

	// std::wcin.putback(c) for a c the program did not just read always
	// reaches pbackfail - without this the stream fails and the rest of the
	// input is never read
	int_type pbackfail(int_type c) {
		if (gptr() == eback()) {
			return traits_type::eof();
		}
		gbump(-1);
		if (!traits_type::eq_int_type(c, traits_type::eof())) {
			*gptr() = traits_type::to_char_type(c);
		}
		return traits_type::not_eof(c);
	}

	int_type overflow(int_type c) {
		if (traits_type::eq_int_type(c, traits_type::eof())) {
			return traits_type::not_eof(c);
		}
		char b[MB_LEN_MAX];
		size_t n = wcrtomb(b, traits_type::to_char_type(c), &write_state);
		if (n == (size_t)-1) {
			// the character has no representation in this locale - stdio
			// substitutes a question mark here, and failing instead would
			// latch badbit and silently discard everything printed after it
			write_state = {};
			b[0] = '?';
			n = 1;
		}
		if (fwrite(b, 1, n, stdio_stream) != n) {
			return traits_type::eof();
		}
		return c;
	}
};


// a program can install a streambuf of its own in a standard stream and not
// put it back - take back only a stream dcc still owns, and only ever delete
// the streambuf dcc allocated, never whatever the program left there, which
// may not even exist any more
template <typename C>
static void restore_streambuf(std::basic_ios<C> &stream, std::basic_streambuf<C> *dcc_streambuf, std::basic_streambuf<C> *original_streambuf) {
	if (stream.rdbuf() == dcc_streambuf) {
		dcc_streambuf->pubsync();
		stream.rdbuf(original_streambuf);
	}
}


static std::streambuf *original_cin_streambuf;
static std::wstreambuf *original_wcin_streambuf;
static stdiobuf *dcc_cin_streambuf;
static wstdiobuf *dcc_wcin_streambuf;

extern "C" void __dcc_replace_cin(FILE *stream) {
	dcc_cin_streambuf = new stdiobuf(stream);
    original_cin_streambuf = std::cin.rdbuf(dcc_cin_streambuf);
	dcc_wcin_streambuf = new wstdiobuf(stream);
	original_wcin_streambuf = std::wcin.rdbuf(dcc_wcin_streambuf);
}

extern "C" void __dcc_restore_cin(void) {
	if (dcc_cin_streambuf) {
		restore_streambuf(std::cin, dcc_cin_streambuf, original_cin_streambuf);
		delete dcc_cin_streambuf;
		dcc_cin_streambuf = NULL;
		original_cin_streambuf = NULL;
	}
	if (dcc_wcin_streambuf) {
		restore_streambuf(std::wcin, dcc_wcin_streambuf, original_wcin_streambuf);
		delete dcc_wcin_streambuf;
		dcc_wcin_streambuf = NULL;
		original_wcin_streambuf = NULL;
	}
}


static std::streambuf *original_cout_streambuf;
static std::wstreambuf *original_wcout_streambuf;
static stdiobuf *dcc_cout_streambuf;
static wstdiobuf *dcc_wcout_streambuf;

extern "C" void __dcc_replace_cout(FILE *stream) {
	dcc_cout_streambuf = new stdiobuf(stream);
	original_cout_streambuf = std::cout.rdbuf(dcc_cout_streambuf);
	dcc_wcout_streambuf = new wstdiobuf(stream);
	original_wcout_streambuf = std::wcout.rdbuf(dcc_wcout_streambuf);
}

extern "C" void __dcc_restore_cout() {
	if (dcc_cout_streambuf) {
		restore_streambuf(std::cout, dcc_cout_streambuf, original_cout_streambuf);
		delete dcc_cout_streambuf;
		dcc_cout_streambuf = NULL;
		original_cout_streambuf = NULL;
	}
	if (dcc_wcout_streambuf) {
		restore_streambuf(std::wcout, dcc_wcout_streambuf, original_wcout_streambuf);
		delete dcc_wcout_streambuf;
		dcc_wcout_streambuf = NULL;
		original_wcout_streambuf = NULL;
	}
}


static std::streambuf *original_cerr_streambuf;
static std::streambuf *original_clog_streambuf;
static std::wstreambuf *original_wcerr_streambuf;
static std::wstreambuf *original_wclog_streambuf;
static stdiobuf *dcc_cerr_streambuf;
static wstdiobuf *dcc_wcerr_streambuf;

extern "C" void __dcc_replace_cerr(FILE *stream) {
	dcc_cerr_streambuf = new stdiobuf(stream);
    original_cerr_streambuf = std::cerr.rdbuf(dcc_cerr_streambuf);
	// clog shares cerr's streambuf, and is left writing to the unsynchronized
	// stderr the streams were constructed with if it is not replaced too
	original_clog_streambuf = std::clog.rdbuf(dcc_cerr_streambuf);
	dcc_wcerr_streambuf = new wstdiobuf(stream);
	original_wcerr_streambuf = std::wcerr.rdbuf(dcc_wcerr_streambuf);
	original_wclog_streambuf = std::wclog.rdbuf(dcc_wcerr_streambuf);
}

extern "C" void __dcc_restore_cerr() {
	if (dcc_cerr_streambuf) {
		restore_streambuf(std::cerr, dcc_cerr_streambuf, original_cerr_streambuf);
		restore_streambuf(std::clog, dcc_cerr_streambuf, original_clog_streambuf);
		delete dcc_cerr_streambuf;
		dcc_cerr_streambuf = NULL;
		original_cerr_streambuf = NULL;
		original_clog_streambuf = NULL;
	}
	if (dcc_wcerr_streambuf) {
		restore_streambuf(std::wcerr, dcc_wcerr_streambuf, original_wcerr_streambuf);
		restore_streambuf(std::wclog, dcc_wcerr_streambuf, original_wclog_streambuf);
		delete dcc_wcerr_streambuf;
		dcc_wcerr_streambuf = NULL;
		original_wcerr_streambuf = NULL;
		original_wclog_streambuf = NULL;
	}
}


// dcc synchronizes its sanitizer processes at the stdio layer, so the C++
// streams have to keep writing through stdio
// sync_with_stdio(false), which students copy from tutorials to speed up cin,
// would instead give cin, cout and cerr streambufs of libstdc++'s own, which
// use the file descriptor libstdc++ gets from the FILE with the real fileno,
// not dcc's wrapper - there is no descriptor for the streams dcc substitutes,
// so everything the program prints is silently discarded
// leaving the streams synchronized makes the program slower than it asked to
// be, which is a better outcome than losing its output
// weak so that a statically linked libstdc++, whose definition is strong,
// wins instead of the link failing with a duplicate symbol
namespace std {
	__attribute__((weak)) bool ios_base::sync_with_stdio(bool) {
		return true;
	}
}
