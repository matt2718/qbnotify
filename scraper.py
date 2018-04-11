#!/usr/bin/python3

import json
import math
import re
import requests
import sys

from bs4 import BeautifulSoup

import mysecrets

def geocode(address):
	baseURL = 'https://maps.googleapis.com/maps/api/geocode/json'
	reqURL = baseURL\
	         + '?address=' + address.replace(' ', '+')\
	         + '&key=' + mysecrets.maps_api_key

	# do query and check for errors
	resp = requests.get(reqURL)
	if resp.status_code != 200:
		print('GEOCODING ERROR: HTTP status code ' + str(resp.status_code))
		print('(Query was ' + reqURL + ')')
		return None

	# make sure geocoding was succesful
	retObj = json.loads(resp.text)
	if retObj['status'] != 'OK':
		print('GEOCODING ERROR: API returned ' + retObj['status'])
		print('(Query was ' + reqURL + ')')
		return None

	location = retObj['results'][0]['geometry']['location']
	return (location['lat'], location['lng'])

def getTournament(tid):
	resp = requests.get('http://hsquizbowl.org/db/tournaments/' + str(tid))
	if resp.status_code != 200:
		print('ERROR: could not get tournament ' + str(tid)\
		      + ' from HSQB. HTTP status code '\
		      + str(resp.status_code))
		return None

	soup = BeautifulSoup(resp.text)

	# tournament does not exist
	if soup.select_one('.FBError'):
		return None

	# tournament name is in first h2 in heading
	tname = soup.select_one('.MultilineHeading h2').text

	# $LEVEL tournament on $DATE
	ldate = soup.select_one('.MultilineHeading h5').text
	[level, datestr] = ldate.split(' tournament on ')

	# get location
	respGPX = requests.get('http://hsquizbowl.org/db/tournaments/'\
	                       + str(tid) + '/gpx')
	soupGPX = BeautifulSoup(respGPX.text)
	
	wpt = soupGPX.select_one('wpt')
	if wpt:
		lat = wpt['lat']
		lon = wpt['lon']
	else:
		# no GPX data found, let's geocode it ourselves
		fnames = soup.select('.FieldName')
		addrs = [f.parent for f in fnames if f.text == 'Address:']
		locs = [f.parent for f in fnames if f.text == 'Host location:']
		if addrs:
			# has an 'Address' field
			addr = addrs[0].text.lstrip('Address: ')
		elif locs:
			# otherwise, we use the 'Host location' field
			addr = locs[0].text.lstrip('Address: ')
		else:
			# no location, this tournament is useless to us
			return None
		
		# we now have an address string, which we can try to geocode
		coords = geocode(addr)
		if coords:
			[lat, lon] = coords
		else:
			# geocoding failed, we can't find the location
			return None

	return [tname, datestr, level, lat, lon]

def getAllTournaments(last=0):
	resp = requests.get('http://hsquizbowl.org/db/tournaments/dbstats.php')
	if resp.status_code != 200:
		print('ERROR: could not get DB stats from HSQB. HTTP status code '\
		      + str(resp.status_code))
		return []
	
	maxID = int(re.search(r'(?<=max=)[0-9]+', resp.text)[0])
	allInfo = []
	
	for x in range(last+1, maxID+1):
		info = getTournament(x)
		if info: allInfo.append(info)

	return allInfo

print(getAllTournaments(5050))
