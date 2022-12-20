import os
import requests
import time
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

app = Flask('BooksRiver')
app.secret_key = os.environ['SECRET_KEY']

import sqlite3
con = sqlite3.connect("instance/info.db", check_same_thread=False)
cur = con.cursor()
res = cur.execute("SELECT name FROM sqlite_master")
print(res.fetchall())
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
			return redirect("https://BooksRiver.q23rf.repl.co")  # Authorization required
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
	return redirect("/browse")


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


@app.route("/query", endpoint='query', methods=["GET", "POST"])
@login_is_required
def query():
	if request.method == "POST":
		target_subject = request.form["subject"]
		q = cur.execute(f"SELECT * FROM books WHERE subject='{target_subject}'")
		results = q.fetchall()
		return render_template("query.html", results=results)
	else:
		return render_template("query.html")

@app.route("/post", endpoint='post', methods=["GET", "POST"])
@login_is_required
def post():
	if request.method == "POST":
		return render_template("post.html", book=request.form["book"])

@app.route("/browse", endpoint='browse', methods=["GET", "POST"])
@login_is_required
def browse():
	if request.method == "POST":
		data = [request.form["book"],
				(session['name'],
				str(time.ctime()),
		        0)]
		cur.executemany("INSERT INTO posts VALUES(?, ?, ?, ?, ?)", data)
		con.commit()

	return render_template("browse.html", posts=posts)


if __name__ == '__main__':
	app.run(port=8040, host='0.0.0.0', debug=False)
