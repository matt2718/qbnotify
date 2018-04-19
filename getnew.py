#!/usr/bin/python3

import requests
import mysecrets

# get ID of last tournament parsed
try:
	f = open('lastID', 'r')
	last = int(f.read().strip())
	f.close()
except FileNotFoundError:
	print('ERROR: could not find file lastID')
	quit(1)
except ValueError:
	print('ERROR: first line of lastID does not contain an integer')
	quit(1)

# tell server to parse tournaments and notify people
qstring  = '?key=' + mysecrets.admin_key
qstring += '&start=' + str(last + 1)
resp = requests.get('https://qbnotify.msmitchell.org/sn' + qstring)

# validate response
if resp.status_code != 200:
	print('ERROR: server returned status code ' + str(resp.status_code))
	quit(1)

try:
	int(resp.text)
except ValueError:
	print('ERROR: server did not return an integer value')
	quit(1)

# record last tournament parsed
f = open('lastID', 'w')
f.write(resp.text + '\n')
f.close()
