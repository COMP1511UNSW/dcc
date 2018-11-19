#!/usr/bin/env python3

import sys

def embed(file):
	variable_name = 'embedded_source_' + file.replace('.', '_')
	print(variable_name, '=', "r'''")
	with open(file) as f:
		print(f.read(), end='')
	print("'''")

if __name__ == '__main__':
	for file in sys.argv[1:]:
		embed(file)
