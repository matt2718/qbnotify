#!/usr/bin/python3

import html
import json
import logging
import math
import os
import sys

from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, Response, \
	send_from_directory

from flask_sqlalchemy import SQLAlchemy

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required

from flask_login import current_user

from flask_mail import Mail, Message

import scraper
import mysecrets
from constants import states

# set up logging
if '-dbg' in sys.argv[1:]:
	logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
	                    level=logging.DEBUG)
else:
	logging.basicConfig(filename='logs/qbnotify.log',
	                    format='%(asctime)s - %(levelname)s - %(message)s',
	                    level=logging.INFO)

# Create app
app = Flask(__name__)
app.config['DEBUG'] = ('-dbg' in sys.argv[1:])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qbnotify.db'

# this shouldn't be tracked by git
# just put secret_key = '<SOME RANDOM BYTES>' in the file mysecrets.py
app.config['SECRET_KEY'] = mysecrets.secret_key

# not actually a cryptographic salt, so it doesn't matter if it's constant
# this is because flask-security uses stupid naming
app.config['SECURITY_PASSWORD_SALT'] = '00000'

logging.debug('created flask app')

# Create database connection object
db = SQLAlchemy(app)

logging.debug('initialized DB connection')

# allow users to create accounts
app.config['SECURITY_REGISTERABLE'] = True
app.config['SECURITY_REGISTER_URL'] = '/create_account'

# password reset
app.config['SECURITY_RECOVERABLE'] = True

# email setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True

# also from mysecrets.py
# (username and sender will probably be the same unless we're forwarding)
app.config['MAIL_USERNAME'] = mysecrets.mail_username
app.config['MAIL_PASSWORD'] = mysecrets.mail_password
app.config['MAIL_DEFAULT_SENDER'] = mysecrets.mail_sender
app.config['SECURITY_EMAIL_SENDER'] = mysecrets.mail_sender
mail = Mail(app)

logging.debug('configured mail')

############################################################
# COPIED FROM FLASK-SECURITY QUICKSTART GUIDE

# define models
col_user_id = db.Column('user_id', db.Integer(), db.ForeignKey('user.id'))
col_role_id = db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
roles_users = db.Table('roles_users', col_user_id, col_role_id)

class Role(db.Model, RoleMixin):
	id = db.Column(db.Integer(), primary_key=True)
	name = db.Column(db.String(80), unique=True)
	description = db.Column(db.String(255))

class User(db.Model, UserMixin):
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(255), unique=True)
	password = db.Column(db.String(255))
	active = db.Column(db.Boolean())
	confirmed_at = db.Column(db.DateTime())
	roles = db.relationship('Role', secondary=roles_users,
	                        backref=db.backref('users', lazy='dynamic'))

# set up Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

############################################################

logging.debug('initialized security model')

# represents a single alert setting for the user
class Notification(db.Model):
	email = db.Column(db.String(255), primary_key=True)
	id = db.Column(db.Integer(), primary_key=True)
	type = db.Column(db.String(1))
	diff_ms = db.Column(db.Boolean())
	diff_hs = db.Column(db.Boolean())
	diff_college = db.Column(db.Boolean())
	diff_open = db.Column(db.Boolean())
	diff_trash = db.Column(db.Boolean())
	
	lat = db.Column(db.Float(), nullable=True)
	lon = db.Column(db.Float(), nullable=True)
	radius = db.Column(db.Float(), nullable=True)
	unit = db.Column(db.String(8), nullable=True)

	state = db.Column(db.String(16), nullable=True)

	dispname = db.Column(db.String(255), nullable=True)
	
	def __str__(self):
		# get tournament levels
		diffs = []
		if self.diff_ms:      diffs.append('MS')
		if self.diff_hs:      diffs.append('HS')
		if self.diff_college: diffs.append('College')
		if self.diff_open:    diffs.append('Open')
		if self.diff_trash:   diffs.append('Trash')

		# multiple elements require an 'and'
		if len(diffs) > 1: diffs[-1] = 'and ' + diffs[-1]
		
		# commas for more than 2
		if len(diffs) > 2: diffstr = ', '.join(diffs)
		else: diffstr = ' '.join(diffs)

		if self.type == 'S':
			return diffstr + ' tournaments in ' + self.state
		elif self.type == 'C':
			if self.dispname:
				disp = self.dispname +\
					' (' + str(self.lat) + ', ' + str(self.lon) + ')'
			else:
				disp = '(' + str(self.lat) + ', ' + str(self.lon) + ')'
				
			return diffstr + ' tournaments within '\
				+ str(self.radius) + ' ' + str(self.unit) + ' of '\
				+ disp
		
		return ''

# DB listing for tournaments (SQL wrapper for Tournament class in scraper.py)
class DBTournament(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	name = db.Column(db.String(256))
	date = db.Column(db.DateTime())
	level = db.Column(db.String(8))
	state = db.Column(db.String(16))
	lat = db.Column(db.Float())
	lon = db.Column(db.Float())

	def __init__(self, tourney):
		self.id = tourney.id
		self.name = tourney.name
		self.date = tourney.date
		self.level = tourney.level
		self.state = tourney.state
		self.lat = tourney.position[0]
		self.lon = tourney.position[1]

	def dictify(self):
		return {
			'id': self.id,
			'name': self.name,
			'date': self.date.strftime('%Y-%m-%d'),
			'level': self.level,
			'state': self.state,
			'lat': self.lat,
			'lon': self.lon
		}
	
logging.info('started QBNotify')

@app.before_first_request
def create_user():
	db.create_all()
	db.session.commit()


# make necessary parameters available for login page
@security.context_processor
def security_context_processor():
	return dict(clientkey=mysecrets.maps_client_api_key)
	
# Views
@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
	noteList = Notification.query.filter_by(email=current_user.email)\
	                             .order_by(Notification.id).all()
	
	return render_template('home.html',
	                       states=states,
	                       curNotes=noteList,
	                       email=current_user.email,
	                       clientkey=mysecrets.maps_client_api_key)

# new coordinate notification added
@app.route('/addCoord', methods=['POST'])
@login_required
def addCoord():
	if request.form:
		# get coordinates (need to handle addresses seperately)
		if request.form['addrbut']:
			if not request.form['addr']:
				return redirect('/')
			place = scraper.geocode(request.form['addr'])
			if not place:
				return redirect('/')
			latstr, lonstr, tmp = place
		elif request.form['coordbut']:
			latstr = float(request.form['lat'])
			lonstr = float(request.form['lon'])
		else:
			return redirect('/')

		# validate input
		try:
			lat = float(latstr)
			lon = float(lonstr)
			radius = float(request.form['r'])
			unit = request.form['unit']

		except ValueError:
			return redirect('/')

		# make sure the range is correct
		if (lat < -90 or 90 < lat) or (lon < -180 or 180 < lon):
			return redirect('/')

		# get highest ID that user has
		curNotes = Notification.query.filter_by(email=current_user.email)\
		                             .order_by(Notification.id).all()
		if curNotes: maxID = curNotes[-1].id
		else: maxID = -1

		newNote = Notification(email=current_user.email, id=maxID + 1,
		                       type='C',
		                       lat=lat, lon=lon, radius=radius, unit=unit)

		if request.form['addrbut']:
			newNote.dispname = request.form['addr']
		
		# check which difficulties the person has chosen
		levels = request.form.getlist('level')
		if not levels: return redirect('/')

		newNote.diff_ms      = ('ms' in levels)
		newNote.diff_hs      = ('hs' in levels)
		newNote.diff_college = ('college' in levels)
		newNote.diff_open    = ('open' in levels)
		newNote.diff_trash   = ('trash' in levels)

		db.session.add(newNote)
		db.session.commit()
		
	return redirect('/')

# new state notification added
@app.route('/addState', methods=['POST'])
@login_required
def addState():
	if request.form:
		# get highest ID that user has
		curNotes = Notification.query.filter_by(email=current_user.email)\
		                             .order_by(Notification.id).all()
		if curNotes: maxID = curNotes[-1].id
		else: maxID = -1

		newNote = Notification(email=current_user.email, id=maxID + 1,
		                       type='S', state=request.form['state'])
		
		# check which difficulties the person has chosen
		levels = request.form.getlist('level')
		if not levels: return redirect('/')

		newNote.diff_ms      = ('ms' in levels)
		newNote.diff_hs      = ('hs' in levels)
		newNote.diff_college = ('college' in levels)
		newNote.diff_open    = ('open' in levels)
		newNote.diff_trash   = ('trash' in levels)

		db.session.add(newNote)
		db.session.commit()

	return redirect('/')

# notification deleted
@app.route('/delNote', methods=['POST'])
@login_required
def delNote():
	if request.form:
		Notification.query.filter_by(email=current_user.email)\
		                  .filter_by(id=request.form['id']).delete()
		db.session.commit()
		
	return redirect('/')

# checks if the notification applies to difficulty of tournament
def checkDifficulty(tournament, notification):
	return (tournament.level == 'M' and notification.diff_ms) \
		or (tournament.level == 'H' and notification.diff_hs) \
		or (tournament.level == 'C' and notification.diff_college) \
		or (tournament.level == 'O' and notification.diff_open) \
		or (tournament.level == 'T' and notification.diff_trash)

# get new tournaments and notify people
# this will be called by snFrontend because it's a generator
def scrapeAndNotify(start, end):
	# get tournaments and setup email list
	tournaments = []
	today = datetime.today()
	for tourney in scraper.getAllTournaments(start=start, end=end):
		tournaments.append(tourney)
		if tourney.date > today:
			db.session.merge(DBTournament(tourney))
		# client gets a list of tournament IDs
		# we stream to prevent gunicorn from timing out
		yield str(tourney.id) + '\n'
	db.session.commit()

	# update upcoming tournaments file
	tmp = DBTournament.query.filter(DBTournament.date >= today).all()
	with open('static/upcoming.json', 'w') as outfile:
		json.dump([t.dictify() for t in tmp], outfile)

	toSend = {}

	# if no new tournaments are present, return start-1
	if not tournaments:
		yield str(start-1)
		return
	
	# get area notifications
	circNotes = Notification.query.filter_by(type='C').all()
	
	# The area checking has bad complexity, but it's a cheap operation done
	# relatively few times and I'm not going to implement a complicated
	# spatial partitioning scheme to save time in the unlikely case that
	# thousands of tournaments are announced in a day. If that happens, the
	# state of quizbowl will be so amazing that I won't mind rewriting it.
	
	for tourney in tournaments:
		# handle state notification first
		stateNotes = Notification.query.filter_by(state=tourney.state).all()
		for note in stateNotes:
			if checkDifficulty(tourney, note) and tourney.date > today:
				# correct difficulty and in the future; add tournament
				if note.email not in toSend: toSend[note.email] = set()
				toSend[note.email].add(tourney)

		# handle area notifications
		for note in circNotes:
			coord1 = (note.lat, note.lon)
			coord2 = tourney.position

			# must use meters for radius
			if note.unit == 'mi': radius_m = note.radius * 1609.3
			elif note.unit == 'ft': radius_m = note.radius * 0.3048
			elif note.unit == 'km': radius_m = note.radius * 1000.0
			else: radius_m = note.radius

			if checkDifficulty(tourney, note) and tourney.date > today \
			   and surfDist(6371008.8, coord1, coord2) < radius_m:
				# correct difficlty, in the future, and within range
				if note.email not in toSend: toSend[note.email] = set()
				toSend[note.email].add(tourney)

	# time to actually send the emails
	subj = 'You have new quizbowl tournament notifications'
	baseURL = 'http://hsquizbowl.org/db/tournaments/'
	# optimize for batch sending
	with app.app_context(), mail.connect() as conn:
		for email in toSend:
			content = 'The following tournaments have recently been '\
			          'posted to the hsquizbowl.org database:<br />'

			for tourney in toSend[email]:
				content += '<br />'
				content += '<a href="' + baseURL + str(tourney.id) + '">'
				content += html.escape(tourney.name)
				content += '</a> on '
				content += tourney.date.isoformat().split('T')[0]

			content += '<br /><br />'
			content += 'You can edit your notification settings '
			content += 'or view a map of all upcoming tournaments at '
			content += '<a href="https://qbnotify.msmitchell.org">'
			content += 'qbnotify.msmitchell.org'
			content += '</a>.'
			
			msg = Message(recipients=[email],
			              html=content,
			              subject=subj)
			conn.send(msg)
			logging.info('notified user ' + email)

# authenticate and call scrapeAndNotify
@app.route('/sn/', methods=['GET'])
def snFrontend():
	# validate query string
	if 'key' not in request.args:
		return Response('ERROR: no key', mimetype='text/plain'), 400
	
	if 'start' not in request.args:
		return Response('ERROR: no start index', mimetype='text/plain'), 400
	
	if request.args['key'] != mysecrets.admin_key:
		return Response('ERROR: bad key', mimetype='text/plain'), 401

	try:
		start = int(request.args['start'])
	except ValueError:
		return Response('ERROR: start must be an integer',
		                mimetype='text/plain'), 403

	# have we provided an ending point?
	if 'end' in request.args:
		try:
			end = int(request.args['end'])
		except ValueError:
			return Response('ERROR: end must be an integer',
		                mimetype='text/plain'), 403
	else:
		end = 1000000000

	return Response(scrapeAndNotify(start, end), mimetype='text/plain')

# certain static files
@app.route('/robots.txt')
def robotstxt():
	return send_from_directory(
		os.path.join(app.root_path, 'static'),
		'robots.txt',
		mimetype='text/plain')	

# some browsers expect favicons to be at the site root
@app.route('/favicon.ico')
def favicon():
	return send_from_directory(
		os.path.join(app.root_path, 'static'),
		'favicon.ico',
		mimetype='image/vnd.microsoft.icon')

@app.route('/browserconfig.xml')
def browserconfig():
	return send_from_directory(
		os.path.join(app.root_path, 'static'),
		'browserconfig.xml',
		mimetype='application/xml')

# finds great-circle distance between 2 points on a sphere
# (Yes, I know the earth is an oblate spheroid, but I'm not going to implement
#  the full Vincenty formula to give you <0.5% more accurate geodesics. It was
#  hard enough making sure this was numerically well-conditioned. Just make your
#  notifcation circle slightly larger if it matters to you.)
def surfDist(r, latlon1, latlon2):
	# convert to radians
	lat1 = latlon1[0] * math.pi / 180
	lon1 = latlon1[1] * math.pi / 180
	lat2 = latlon2[0] * math.pi / 180
	lon2 = latlon2[1] * math.pi / 180

	# haversine formula
	# (possibly not super well-conditioned for antipodes, but if you want to
	#  notified exclusively about non-antipodal tournaments, you have bigger
	#  problems)
	tmp = math.sin((lat1 - lat2) / 2)**2 \
	      + math.cos(lat1) * math.cos(lat2) * math.sin((lon1 - lon2) / 2)**2

	return 2 * r * math.asin(math.sqrt(tmp))

if __name__ == '__main__':
	# this is only for debugging, not deployment
	app.run()
