#!/usr/bin/python3

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect

from flask_sqlalchemy import SQLAlchemy

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required

from flask_login import current_user

states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA",
          "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
          "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
          "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
          "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]


# Create app
app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qbnotify.db'

# this shouldn't be tracked by git
# just put secret_key = '<SOME RANDOM BYTES>' in the file mysecrets.py
import mysecrets
app.config['SECRET_KEY'] = mysecrets.secret_key

# not actually a cryptographic salt, so it doesn't matter if it's constant
# this is because flask-security uses stupid naming
app.config['SECURITY_PASSWORD_SALT'] = '00000'

# Create database connection object
db = SQLAlchemy(app)

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

class Notification(db.Model):
	email = db.Column(db.String(255), primary_key=True)
	id = db.Column(db.Integer(), primary_key=True)
	type = db.Column(db.String(1))

	lat = db.Column(db.Float(), nullable=True)
	lon = db.Column(db.Float(), nullable=True)
	radius = db.Column(db.Float(), nullable=True)

	state = db.Column(db.String(16), nullable=True)
	
tmpnotes = [];

@app.before_first_request
def create_user():
	db.create_all()
	user_datastore.create_user(email='matt@coloradoqb.org', password='password')
	db.session.add(Notification(email='matt@coloradoqb.org',
	                            id=0,
	                            type='S',
	                            state='ID'))
	db.session.add(Notification(email='matt@coloradoqb.org',
	                            id=1,
	                            type='C',
	                            lat=40.008019,
	                            lon=-105.267860,
	                            radius=1000))
	db.session.commit()
			
# Views
@app.route('/', methods=["GET", "POST"])
@login_required
def home():
	noteList = Notification.query.filter_by(email='matt@coloradoqb.org')\
	                             .order_by(Notification.id).all()
	return render_template("home.html", states=states, curNotes=noteList)

# new coordinate notification added
@app.route('/addCoord', methods=["POST"])
@login_required
def addCoord():
	if request.form:
		# validate input
		try:
			lat = float(request.form['lat'])
			lon = float(request.form['lon'])
			radius = float(request.form['r'])

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

		db.session.add(Notification(email=current_user.email, id=maxID + 1,
		                            type='C', lat=lat, lon=lon, radius=radius))
		db.session.commit()
		
	return redirect('/')

# new state notification added
@app.route('/addState', methods=["POST"])
@login_required
def addState():
	if request.form:
		# get highest ID that user has
		curNotes = Notification.query.filter_by(email=current_user.email)\
		                             .order_by(Notification.id).all()
		if curNotes: maxID = curNotes[-1].id
		else: maxID = -1

		db.session.add(Notification(email=current_user.email, id=maxID + 1,
		                            type='S', state=request.form['state']))
		db.session.commit()

	return redirect('/')

# notification deleted
@app.route('/delNote', methods=["POST"])
@login_required
def delNote():
	if request.form:
		Notification.query.filter_by(email=current_user.email)\
		                  .filter_by(id=request.form['id']).delete()
		db.session.commit()
		print("Deleting: " + request.form['id'])
		
	return redirect('/')

if __name__ == '__main__':
	# this is only for debugging, not deployment
	app.run()
