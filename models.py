from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy with the app
db = SQLAlchemy()

# Define models
class categories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Text)
    title = db.Column(db.Text)
    weight = db.Column(db.Integer)
    parent = db.Column(db.Integer)
    description = db.Column(db.Text)
    path = db.Column(db.Text)
    draft = db.Column(db.Text)
    indexpage = db.Column(db.Text)

class articles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Text)
    title = db.Column(db.Text)
    parent = db.Column(db.Integer)
    description = db.Column(db.Text)
    path = db.Column(db.Text)
    keywords = db.Column(db.Text)
    date = db.Column(db.Text)
    draft = db.Column(db.Text)
    weight = db.Column(db.Integer)
    author = db.Column(db.Text)
    content = db.Column(db.Text)

class Contributors(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    description_short = db.Column(db.Text)
    description_long = db.Column(db.Text)
    skills = db.Column(db.Text)
    linkedin = db.Column(db.Text)
    facebook = db.Column(db.Text)
    twitter = db.Column(db.Text)
    email = db.Column(db.Text)
    image = db.Column(db.Text)
    status = db.Column(db.Text)
    path = db.Column(db.Text)
    content = db.Column(db.Text)
