#!/usr/bin/python3

from flask import Flask
from flask import render_template
from flask import request

from flask_sqlalchemy import SQLAlchemy

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required

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

# Define models
roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

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

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

# Create a user to test with
@app.before_first_request
def create_user():
    db.create_all()
    user_datastore.create_user(email='matt@coloradoqb.org', password='password')
    db.session.commit()

# Views
@app.route('/', methods=["GET", "POST"])
@login_required
def home():
    if request.form:
        print(request.form['email'])
        print(request.form['password'])
    return render_template("home.html")

if __name__ == '__main__':
    app.run()
