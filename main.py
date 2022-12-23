import os
import requests
import time
from flask import Flask, session, abort, redirect, request, render_template, flash
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
	try:
		data = [(session["name"], id_info.get("email"), session["google_id"], 0)]
		cur.executemany("INSERT INTO users VALUES(?, ?, ?, ?)", data)
		con.commit()
		print("new user:"+session["google_id"])
	except:
		print("old user:"+session["google_id"])
	return redirect("/query")


@app.route("/logout")
def logout():
	session.clear()
	return redirect("/")


@app.route("/")
def index():
	return render_template("index.html")


@app.route("/protected", endpoint='protected', methods=["GET", "POST"])
@login_is_required
def protected():
	if request.method == "POST":	#已領取
		post_id = request.form["id"]
		cur.execute(f"DELETE FROM gets WHERE post_id={post_id}")
		cur.execute(f"DELETE FROM posts WHERE time={post_id}")
		con.commit()

	google_id = session['google_id']
	user_query = cur.execute(f"SELECT * FROM users WHERE google_id={google_id}")
	user = user_query.fetchone()
	gets_query = cur.execute(f"SELECT * FROM gets WHERE getter_id={google_id} AND status=0")
	gets = gets_query.fetchall()
	give_query = cur.execute(f"SELECT * FROM posts WHERE user_id={google_id}")
	gives = give_query.fetchall()
	if len(gets)>0:
		if len(gives)>0:
			return render_template("protected.html", user=user, gets=gets, gives=gives)
		else:
			return render_template("protected.html", user=user, gets=gets, no_gives="暫無捐書紀錄")
	else:
		if len(gives)>0:
			return render_template("protected.html", user=user, no_gets="暫無取書紀錄", gives=gives)
		else:
			return render_template("protected.html", user=user, no_gets="暫無取書紀錄", no_gives="暫無捐書紀錄")



@app.route("/query", endpoint='query', methods=["GET", "POST"])
@login_is_required
def query():
	if request.method == "POST":
		sql = "SELECT * FROM books WHERE "
		constraints = []
		exam = request.form["exam"]
		subject = request.form["subject"]
		category = request.form["category"]
		if exam != "全部":
			constraints.append("exam='"+exam+"'")
		if subject != "全部":
			constraints.append("subject='"+subject+"'")
		if category != "全部":
			constraints.append("category='"+category+"'")

		if len(constraints)>0:
			sql += " AND ".join(constraints)
		else:
			sql += "LENGTH(name)>0"
		print(sql)
		q = cur.execute(sql)
		results = q.fetchall()
		return render_template("query.html", results=results)
	else:
		return render_template("query.html")

@app.route("/give", endpoint='give', methods=["GET", "POST"])
@login_is_required
def give():
	if request.method == "POST":
		id = request.form["id"]
		return render_template("give.html", id=id)
	else:
		return redirect("/query")

@app.route("/get", endpoint='get', methods=["GET", "POST"])
@login_is_required
def get():
	if request.method == "POST":
		id = request.form["id"]
		q = cur.execute(f"SELECT * FROM posts WHERE book_id='{id}' AND status=0")
		results = q.fetchall()
		if len(results)>0:
			return render_template("get.html", results=results)
		else:
			empty = "暫時沒有人捐贈這本書..."
			return render_template("get.html", empty=empty)
			
	else:
		return redirect("/query")

@app.route("/giveCallback", endpoint='giveCallback', methods=["GET", "POST"])
@login_is_required
def giveCallback():
	if request.method == "POST":
		id = request.form["id"]
		description = request.form["description"]
		book_query = cur.execute(f"SELECT * FROM books WHERE id_inherited={id}")
		book = book_query.fetchone()
		book_name = book[1]
		data = [(id, book_name, session["google_id"], session["name"], description, time.time(), 0, time.ctime())]
		cur.executemany("INSERT INTO posts VALUES(?, ?, ?, ?, ?, ?, ?, ?)", data)
		cur.execute(f"UPDATE books SET quantity=quantity+1 WHERE id_inherited={id}")
		cur.execute(f"UPDATE users SET coins=coins+10 WHERE google_id={session['google_id']}")
		con.commit()
		print(id, "捐贈成功!")
		flash("捐贈成功!")
	return redirect("/query")


@app.route("/getCallback", endpoint='getCallback', methods=["GET", "POST"])
@login_is_required
def getCallback():
	if request.method == "POST":
		time = request.form["time"]
		getter_id = session["google_id"]
		post_query = cur.execute(f"SELECT * FROM posts WHERE time={time}")
		post = post_query.fetchone()
		book_id = post[0]
		giver_id = post[2]
		description = post[4]

		book_query = cur.execute(f"SELECT * FROM books WHERE id_inherited={book_id}")
		book = book_query.fetchone()
		book_name = book[1]

		giver_query = cur.execute(f"SELECT * FROM users WHERE google_id={giver_id}")
		giver = giver_query.fetchone()
		giver_name = giver[0]

		getter_query = cur.execute(f"SELECT * FROM users WHERE google_id={getter_id}")
		getter = getter_query.fetchone()
		getter_coins = getter[3]
		if getter_coins>=10:
			cur.execute(f"INSERT INTO gets VALUES ('{giver_name}', '{book_name}', '{description}', {time}, {getter_id}, {giver_id}, 0)")
			cur.execute(f"UPDATE posts SET status = 1 WHERE time={time};")
			cur.execute(f"UPDATE books SET quantity = quantity-1 WHERE id_inherited={book_id};")
			
			cur.execute(f"UPDATE users SET coins = coins-10 WHERE google_id={getter_id};")
			con.commit()
			return redirect("/protected")
		else:
			return render_template("getCallback.html")


if __name__ == '__main__':
	app.run(port=8040, host='0.0.0.0', debug=False)
