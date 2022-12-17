import os
import requests
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
app = Flask('BooksRiver')
app.secret_key = os.environ['SECRET_KEY']
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///info.db"
db.init_app(app)


class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String)


class Post(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String)
	title = db.Column(db.String)
	subject = db.Column(db.String)
	grade = db.Column(db.Integer)
	status = db.Column(db.Integer)


with app.app_context():
	db.create_all()

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

client_secrets_file = "client_secret.json"
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']

flow = Flow.from_client_secrets_file(
 client_secrets_file=client_secrets_file,
 scopes=[
  "https://www.googleapis.com/auth/userinfo.profile",
  "https://www.googleapis.com/auth/userinfo.email", "openid"
 ],
 redirect_uri="https://BooksRiver.q23rf.repl.co/callback")


def login_is_required(function):

	def wrapper(*args, **kwargs):
		if "google_id" not in session:
			return abort(401)  # Authorization required
		else:
			return function()

	#wrapper.__name__ = func.__name__
	return wrapper


@app.route("/login")
def login():
	authorization_url, state = flow.authorization_url()
	session["state"] = state
	return redirect(authorization_url)


@app.route("/callback")
def callback():
	flow.fetch_token(authorization_response=request.url)

	if not session["state"] == request.args["state"]:
		abort(500)  # State does not match!

	credentials = flow.credentials
	request_session = requests.session()
	cached_session = cachecontrol.CacheControl(request_session)
	token_request = google.auth.transport.requests.Request(session=cached_session)

	id_info = id_token.verify_oauth2_token(id_token=credentials._id_token,
	                                       request=token_request,
	                                       audience=GOOGLE_CLIENT_ID)

	session["google_id"] = id_info.get("sub")
	session["name"] = id_info.get("name")
	return redirect("/protected")


@app.route("/logout")
def logout():
	session.clear()
	return redirect("/")


@app.route("/")
def index():
	return render_template("index.html")


@app.route("/protected", endpoint='protected')
@login_is_required
def protected():
	return render_template("protected.html", username=session['name'])


@app.route("/post", endpoint='post')
@login_is_required
def post():
	return render_template("post.html")

@app.route("/browse", endpoint='browse', methods=["GET", "POST"])
@login_is_required
def browse():
	if request.method == "POST":
		post = Post(username=session['name'],
		            title=request.form["title"],
		            subject=request.form["subject"],
		            grade=request.form["grade"],
		            status=0)
		db.session.add(post)
		db.session.commit()
	posts = db.session.execute(db.select(Post).order_by(Post.id)).scalars()
	return render_template("browse.html", posts=posts)


if __name__ == '__main__':
	app.run(port=8040, host='0.0.0.0', debug=False)
