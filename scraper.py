#!/usr/bin/python3

import json
import logging
import math
import re
import requests
import sys

from datetime import datetime

from bs4 import BeautifulSoup

import mysecrets
from constants import states

class Tournament:
	name = None
	date = None
	level = None
	state = None
	position = None
	id = None

def geocode(address):
	logging.info('Google maps query: ' + address)
	baseURL = 'https://maps.googleapis.com/maps/api/geocode/json'
	reqURL = baseURL\
	         + '?address=' + address.replace(' ', '+')\
	         + '&key=' + mysecrets.maps_server_api_key

	# do query and check for errors
	resp = requests.get(reqURL)
	if resp.status_code != 200:
		logging.error('geocoding API returned HTTP status code '\
		              + str(resp.status_code)\
		              + ' (query was ' + reqURL + ')')
		return None

	# make sure geocoding was succesful
	retObj = json.loads(resp.text)
	if retObj['status'] != 'OK':
		logging.warning('geocoding API returned ' + retObj['status']\
		                + ' (query was ' + reqURL + ')')
		return None

	# get coordinates
	location = retObj['results'][0]['geometry']['location']

	# get country and state/province
	addrParts = retObj['results'][0]['address_components'] 
	country = [x for x in addrParts
	           if x['types'][0]=='country'][0]['short_name']

	if country == 'GB':
		# states not necessary for british tournaments
		place = 'UK'
	elif country == 'US' or country == 'CA':
		# get state or province
		for x in addrParts:
			if x['types'][0]=='administrative_area_level_1':
				place = x['short_name']
				break
	else:
		place = 'other'
	
	return [location['lat'], location['lng'], place]

# try to extract state from address
def addr2state(address):
	# iterate backwards though address words, searching for a place
	# we need to start at the end because state abbreivations might
	# appear in place names (statford ON avon)
	asplit = address.lower().split()
	asplit.reverse()
	for word in asplit:
		for state in states:
			if word == state[0].lower() or word == state[1].lower():
				return state[1]

	# nothing found
	return ''

# gets info for a specific tournament in HSQB's database
def getTournament(tid):
	tourney = Tournament()
	tourney.id = tid
	
	resp = requests.get('http://hsquizbowl.org/db/tournaments/' + str(tid))
	if resp.status_code != 200:
		logging.error('could not get tournament ' + str(tid)\
		              + ' from HSQB. HTTP status code '\
		              + str(resp.status_code))
		return None

	soup = BeautifulSoup(resp.text)

	# tournament does not exist
	if soup.select_one('.FBError'):
		logging.info('tournament ' + str(tid) + ' does not exist')
		return None

	# tournament name is in first h2 in heading
	tourney.name = soup.select_one('.MultilineHeading h2').text

	# date is formatted as $LEVEL tournament on $DATE
	ldate = soup.select_one('.MultilineHeading h5').text
	datesplit = ldate.split(' tournament on ')
	if len(datesplit) < 2:
		# not listed, we can't use this
		logging.warn('level or date not listed for tournament '\
		      + str(tid) + '; ignoring')
		return None
	[level, datestr] = datesplit

	tourney.level = level[0]

	# account for multiple days
	datestr = datestr.split(' - ')[0]
	datestr = re.sub(r'-[0-9][0-9]', '', datestr)

	# check if date string was 'Month DD - Month DD YYYY', and append year
	if re.match(r'[A-Z][a-z]* [0-9][0-9]$', datestr):
		datestr += datesplit[1][-6:]

	# get address, if present
	fnames = soup.select('.FieldName')
	addrs = [f.parent for f in fnames if f.text == 'Address:']
	locs = [f.parent for f in fnames if f.text == 'Host location:']

	if locs: hloc = locs[0].text.replace('Host location: ', '')
	else: hloc = ''

	if addrs:
		# has an 'Address' field
		addr = addrs[0].text.replace('Address: ', '')
	elif locs:
		# otherwise, we use the 'Host location' field
		addr = hloc
		
		# ignore tournaments without fixed dates
		if addr.lower() in ['tba', 'to be announced', 'undetermined',
		                    'unknown']:
			logging.warn('the location of tournament ' + str(tid)\
			             + ' is TBA; ignoring')
			return None
		
		# ignore tournaments in multiple locations
		if addr.lower() in ['various', 'multiple']:
			logging.info('tournament ' + str(tid)\
			             + ' is in multiple locations; ignoring')
			return None

		# ignore online tournaments
		if addr.lower() in ['internet', 'the internet', 'online', 'cloud',
		                    'the cloud', 'skype', 'discord']:
			logging.info('tournament ' + str(tid) + ' is online; ignoring')
			return None
	else:
		addr = ''
	
	# check if coordinates are listed
	respGPX = requests.get('http://hsquizbowl.org/db/tournaments/'\
	                       + str(tid) + '/gpx')
	soupGPX = BeautifulSoup(respGPX.text)
	
	wpt = soupGPX.select_one('wpt')

	if wpt:
		# we have coordinates!
		lat = wpt['lat']
		lon = wpt['lon']
		place = addr2state(addr)

		# if no state/province is mentioned in address, see if we can
		# geocode it. we try this last to conserve API queries
		if not place:
			place = geocode(str(lat) + ', ' + str(lon))[2]

	else:
		# no GPX data found, let's geocode it ourselves
		if not addr:
			# no location, this tournament is useless to us
			logging.warn('location not available for tournament '\
			             + str(tid) + '; ignoring')
			return None
		
		# we now have an address string, which we can try to geocode
		location = geocode(addr)
		if not location and hloc and hloc != addr:
			# 'Address' gc failed, try 'Host Location' as a last resort
			location = geocode(hloc)

		if location:
			[lat, lon, place] = location
		else:
			# geocoding failed, we can't find the location
			logging.warn('geocoding failed for tournament '\
			             + str(tid) + '; ignoring')
			return None

	tourney.state = place
	tourney.position = (float(lat), float(lon))

	# get date
	try:
		tourney.date = datetime.strptime(datestr, '%B %d, %Y')
	except ValueError:
		logging.warn('malformed date for tournament ' + str(tid)\
		             + '; ignoring')
		return None
		
	return tourney

def getAllTournaments(start=1, end=1000000000):
	resp = requests.get('http://hsquizbowl.org/db/tournaments/dbstats.php')
	if resp.status_code != 200:
		logging.error('could not get DB stats from HSQB. HTTP status code '\
		              + str(resp.status_code))
		return []

	maxID = int(re.search(r'(?<=max=)[0-9]+', resp.text).group(0))
	
	for tid in range(max(start,1), min(end,maxID) + 1):
		try:
			info = getTournament(tid)
		except KeyboardInterrupt:
			# user pressed ctrl-C, exit immediately
			raise
		except:
			logging.error('parser failed on tournament ' + str(tid))
		else:
			if info:
				logging.info('got tournament ' + str(tid))
				yield info

if __name__ == '__main__':
	for t in getAllTournaments(start=4900, end=4950):
		print(t.level + ': ' + t.name + ' | ' + str(t.date))
		print('   ' + t.state + ' ' + str(t.position))
