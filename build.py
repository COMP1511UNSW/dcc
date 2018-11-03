#!/usr/bin/python3

source_files = """
	header.py
	compile.py
	explain_compile_time_error.py
	help50.py
	start_gdb.py
	drive_gdb.py
	main.py
""".split()

embedded_files = """
	start_gdb.py
	drive_gdb.py
	main_wrapper.c
""".split()


def main():
	for file in source_files:
		cat(file)
	for file in embedded_files:
		embed(file)
	print("if __name__ == '__main__':\n    main()")

def cat(file):
	with open(file) as f:
		for line in f:
			if line.startswith("if __name__"):
				break
			print(line, end='')

def embed(file):
	variable_name = 'embedded_source_' + file.replace('.', '_')
	print(variable_name, '=', "r'''")
	with open(file) as f:
		print(f.read(),end='')
	print("'''")

if __name__ == '__main__':
	main()
