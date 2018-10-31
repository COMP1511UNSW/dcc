def main():
	signal.signal(signal.SIGINT, handler)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if debug: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_PID="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')))
	if not sys.argv[1:] and 'DCC_RUN_INSIDE_GDB' in os.environ:
		drive_gdb()
	elif not sys.argv[1:] and 'DCC_PID' in os.environ:
		# we are invoked by the binary because an error has occurred
		start_gdb()
	elif sys.argv[1:] == ['--watch-stdin-for-valgrind-errors']:
		# valgrind is being used - we have been invoked via the binary to watch for valgrind errors
		# which have been directed to our stdin
		while True:
			line = sys.stdin.readline()
			if not line:
				break
			if debug: print('valgrind: ', line, file=sys.stderr)
			if 'vgdb me' in line:
				if colorize_output:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: \033[31muninitialized variable accessed.\033[0m'
				else:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: uninitialized variable accessed.'
				print('\n'+os.environ['DCC_VALGRIND_ERROR'], file=sys.stderr)
				sys.stderr.flush()
				start_gdb()
				sys.exit(0)
			elif 'loss record' in line:
				line = sys.stdin.readline()
				if 'malloc' in line:
					line = sys.stdin.readline()
					m = re.search(r'(\S+)\s*\((.+):(\d+)', line)
					if m:
						print('Error: free not called for memory allocated with malloc in function {} in {} at line {}.'.format(m.group(1),m.group(2),m.group(3)), file=sys.stderr)
					else:
						print('Error: free not called for memory allocated with malloc.', file=sys.stderr)
				else:
					print('Error: memory allocated not de-allocated.', file=sys.stderr)
				sys.exit(0)
	else:
		compile()

if __name__ == '__main__':
	main()
