#!/bin/sh

export EMAIL="andrewt@unsw.edu.au"
export DEBFULLNAME="Andrew Taylor"

base_directory=$(dirname $(readlink -f "$0"))
source_directory=$base_directory/../..
version=`git describe --tags|sed 's/-/./;s/-.*//'`
package_name=dcc

dir=$base_directory/dcc-$version

rm -rf $dir
mkdir -p $dir/debian/
cp -p $source_directory/dcc $dir
cp -p $source_directory/dcc.1 $dir
rsync -a $base_directory/debian/ $dir/debian/
git tag -l -n9 --sort=-version:refname --format 'dcc (%(refname:lstrip=-1)) unstable; urgency=medium

  * %(contents)
 -- %(*authorname) %(*authoremail) %(*authordate)'|
 sed 's?> \(.*\) \(.*\) \(.*\) \([0-9][0-9]:[0-9][0-9]:[0-9][0-9]\) \(.*\) \(.*\)?>  \1, \3 \2 \5 \4 \6?'   >$dir/debian/changelog

cd $dir
dpkg-buildpackage -b 
cd $base_directory
lintian dcc_${version}_all.deb
exit 0

