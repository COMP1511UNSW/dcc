EMBEDDED_SOURCE = $(wildcard run_time_python/*.py wrapper_c/*.c wrapper_c/*.cpp)
SOURCE = $(wildcard compile_time_python/*.py)
BUILD_DIR=_build

# EMBEDDED_PACKAGE_NAME used by pkgutil.get_data in compile_time_python/compile.py
EMBEDDED_PACKAGE_NAME=embedded_src
PACKAGE_DIR=$(BUILD_DIR)/$(EMBEDDED_PACKAGE_NAME)

dcc: $(SOURCE) $(EMBEDDED_SOURCE) Makefile
	rm -rf $(BUILD_DIR)
	mkdir -p $(PACKAGE_DIR)
	touch $(PACKAGE_DIR)/__init__.py
	echo 'VERSION = "'`git describe --tags`'"' >$(BUILD_DIR)/version.py
	for f in $(EMBEDDED_SOURCE); do ln -sf ../../$$f $(PACKAGE_DIR); done
	for f in $(SOURCE); do ln -sf ../$$f $(BUILD_DIR); done
	# --symlinks here breaks pkgutil.read_data in compile.py
	cd $(BUILD_DIR); zip $@.zip -9 -r *.py $(EMBEDDED_PACKAGE_NAME)
	echo '#!/usr/bin/env python3' >$@
	cat $(BUILD_DIR)/$@.zip >>$@
	chmod 755 $@ 
	rm -rf $(BUILD_DIR)

dcc.1: dcc lib/help2man_include.txt
	help2man --include=lib/help2man_include.txt ./dcc >dcc.1
	
tests: dcc
	tests/do_tests.sh ./dcc

# static checks of the Python, shell and embedded C code, and the Python unit tests
PYTHON_SOURCE = $(wildcard compile_time_python/*.py run_time_python/*.py lib/*.py tests/*.py)
SHELL_SOURCE = $(wildcard tests/*.sh tests/*/*.sh) packaging/debian/build.sh install_scripts/macos_install.sh

CHECK_DIR=_build_check

check:
	$(MAKE) dcc
	rm -rf $(CHECK_DIR)
	mkdir -p $(CHECK_DIR)
	echo 'VERSION = "check"' >$(CHECK_DIR)/version.py
	python3 -W error -m py_compile $(PYTHON_SOURCE)
	PYTHONPATH=$(CHECK_DIR):compile_time_python:run_time_python pylint --rcfile=.pylintrc $(PYTHON_SOURCE)
	# run_time_python/util.py and colors.py are symlinks, which mypy sees as duplicate modules
	MYPYPATH=$(CHECK_DIR):compile_time_python python3 -m mypy --ignore-missing-imports $(filter-out run_time_python/util.py run_time_python/colors.py,$(PYTHON_SOURCE))
	rm -rf $(CHECK_DIR)
	shellcheck --severity=warning --exclude=SC2154 $(SHELL_SOURCE)
	tests/check_wrapper_warnings.sh ./dcc
	python3 tests/python_unit_tests.py

tests_all_clang_versions: dcc
	for compiler in /usr/bin/clang-[1-24-9]* ; do echo $$compiler;tests/do_tests.sh ./dcc $$compiler; echo; done


VERSION=$(shell git describe --tags|sed 's/-/./;s/-.*//')

deb: packaging/debian/dcc_${VERSION}_all.deb

packaging/debian/dcc_${VERSION}_all.deb: dcc dcc.1 
	rm -rf debian
	mkdir -p debian/DEBIAN/usr/local/bin/
	cp -p dcc debian/DEBIAN/usr/local/bin/
	ln -sf dcc debian/DEBIAN/usr/local/bin/dcc++
	echo Package: dcc >debian/DEBIAN/control
	echo Architecture: all >>debian/DEBIAN/control
	echo Description:  a C compiler which explain errors to novice programmers >>debian/DEBIAN/control
	packaging/debian/build.sh

.PHONY: deb tests tests_all_clang_versions check
