#!/usr/bin/env python3

# https://stackoverflow.com/questions/38153418/can-someone-give-a-python-requests-example-of-uploading-a-release-asset-in-githu/52354681#52354681

import json, os, subprocess, sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = 'COMP1511UNSW/dcc'
URL_TEMPLATE = 'https://{}.github.com/repos/' + REPO + '/releases'

def make_release(token, tag):
	_json = json.loads(urlopen(Request(
		URL_TEMPLATE.format('api'),
		json.dumps({
			'tag_name': tag,
			'name': tag,
			'prerelease': False,
		}).encode(),
		headers={
			'Accept': 'application/vnd.github.v3+json',
			'Authorization': 'token ' + token,
		},
	)).read().decode())
	return _json['id']

def upload_file(token, pathname, release_id):
	with open(pathname, 'br') as myfile:
		content = myfile.read()
	json.loads(urlopen(Request(
		URL_TEMPLATE.format('uploads') + '/' + str(release_id) + '/assets?' \
		  + urlencode({'name': os.path.split(pathname)[1]}),
		content,
		headers={
			'Accept': 'application/vnd.github.v3+json',
			'Authorization': 'token ' + token,
			'Content-Type': 'application/zip',
		},
	)).read().decode())
	
def run(command):
	print(' '.join(command))
	subprocess.check_call(command)
	
def main():
	if len(sys.argv) != 3:
		print("Usage:", sys.argv[0], '<release-tag> <release-description>', file=sys.stderr)
		sys.exit(1)
	tag = sys.argv[1]            # e.g 1.0'
	description = sys.argv[2]    # description
	token = os.environ.get('GITHUB_TOKEN', '')
	with open(os.path.join(os.environ.get('HOME', ''), '.github_token')) as f:
		token = f.read().strip()
	run(['git', 'tag', '-a', tag, '-m', description])
	run(['git', 'push'])
	run(['git', 'push', 'origin', tag])
	run(['rm', '-f', 'dcc'])
	run(['make', 'dcc', 'dcc.1'])
	run(['packaging/debian/build.sh'])
	release_id = make_release(token, tag)
	for pathname in ['dcc', f'packaging/debian/dcc_{tag}_all.deb']:
		upload_file(token, pathname, release_id)
		
if __name__ == '__main__':
	main()