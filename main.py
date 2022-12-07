import os
import requests
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

app = Flask("Google Login App")
app.secret_key = os.environ['SECRET_KEY']

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "532469693622-22sldndpftkgp3k3h9nfkbe2h517f0da.apps.googleusercontent.com"
client_secrets_file = "client_secret.json"

flow = Flow.from_client_secrets_file(
 client_secrets_file=client_secrets_file,
 scopes=[
  "https://www.googleapis.com/auth/userinfo.profile",
  "https://www.googleapis.com/auth/userinfo.email", "openid"
 ],
 redirect_uri="https://google-login-flask.q23rf.repl.co/callback")


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

@app.route("/browse", endpoint='browse')
@login_is_required
def browse():
	return render_template("browse.html")

if __name__ == '__main__':
    app.run(port=8040, host='0.0.0.0', debug=False)
