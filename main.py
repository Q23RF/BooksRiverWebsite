import os
import requests
import time
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from bs4 import BeautifulSoup
from urllib import request as rq
import notice
import validation

app = Flask('BooksRiver')
app.secret_key = os.environ['SECRET_KEY']

import sqlite3

con = sqlite3.connect("instance/info.db", check_same_thread=False)
cur = con.cursor()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


#與參考書推薦平台同步
def parse_more(current):
	url = "https://study-guides.dstw.dev/detail.php?id="
	hdr = {
	 'User-Agent':
	 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'
	}
	empty_count = 0
	while empty_count < 10:
		req = rq.Request(url + str(current), headers=hdr)
		page = rq.urlopen(req)
		content = page.read()
		soup = BeautifulSoup(content, 'html.parser')
		result = soup.find("div", {"class": "name_rating"})
		name = result.find("h2").get_text()
		tags = result.find("p").get_text().split(" / ")
		data = [(current, name, tags[0], tags[1], tags[2], 0)]
		print(data)
		if len(name) > 0:
			cur.executemany("INSERT INTO books VALUES(?, ?, ?, ?, ?, ?)", data)
			con.commit()
		else:
			empty_count += 1
		current += 1
	print("done synchronizing")


admin_list = ["114748790465633345027"]
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
			return redirect(
			 "https://BooksRiver.q23rf.repl.co")  # Authorization required
		else:
			return function()

	return wrapper


def admin_is_required(function):

	def wrapper(*args, **kwargs):
		if "google_id" in session and session["google_id"] in admin_list:
			return function()
		else:
			return redirect("https://BooksRiver.q23rf.repl.co")

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
		data = [(session["name"], id_info.get("email"), session["google_id"], 0, 0)]
		cur.executemany("INSERT INTO users VALUES(?, ?, ?, ?, ?)", data)
		con.commit()
		msg = "歡迎您加入書愛流動網站會員！\n若這個帳號不是您本人註冊，請回信告知。\n\n書愛流動專案團隊\nbooksriver.noreply@gmail.com\nins: @booksriver.2022"
		notice.send_mail(id_info.get("email"), "【書愛流動】註冊通知", msg)
	except:  # old user
		pass
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
	if request.method == "POST":  #已領取
		post_id = request.form["id"]
		cur.execute(f"DELETE FROM gets WHERE post_id={post_id}")
		cur.execute(f"DELETE FROM posts WHERE id={post_id}")
		con.commit()

	google_id = session['google_id']
	user_query = cur.execute(f"SELECT * FROM users WHERE google_id={google_id}")
	user = user_query.fetchone()
	gets_query = cur.execute(
	 f"SELECT * FROM gets WHERE getter_id={google_id} AND status=0")
	gets = gets_query.fetchall()
	give_query = cur.execute(f"SELECT * FROM posts WHERE user_id={google_id}")
	gives = give_query.fetchall()
	if len(gets) > 0:
		if len(gives) > 0:
			return render_template("protected.html", user=user, gets=gets, gives=gives)
		else:
			return render_template("protected.html",
			                       user=user,
			                       gets=gets,
			                       no_gives="暫無捐書紀錄")
	else:
		if len(gives) > 0:
			return render_template("protected.html",
			                       user=user,
			                       no_gets="暫無取書紀錄",
			                       gives=gives)
		else:
			return render_template("protected.html",
			                       user=user,
			                       no_gets="暫無取書紀錄",
			                       no_gives="暫無捐書紀錄")


@app.route("/query", endpoint='query', methods=["GET", "POST"])
@login_is_required
def query():
	if request.method == "POST":
		sql = "SELECT * FROM books WHERE "
		constraints = []
		name = request.form["name"]
		exam = request.form["exam"]
		subject = request.form["subject"]
		category = request.form["category"]
		if name != "":
			constraints.append("name LIKE'%" + name + "%'")
		if exam != "全部":
			constraints.append("exam='" + exam + "'")
		if subject != "全部":
			constraints.append("subject='" + subject + "'")
		if category != "全部":
			constraints.append("category='" + category + "'")

		if len(constraints) > 0:
			sql += " AND ".join(constraints)
		else:
			sql += "LENGTH(name)>0"
		q = cur.execute(sql)
		results = q.fetchall()
		return render_template("query.html", results=results)
	else:
		return render_template("query.html")


@app.route("/give/id=<id>", endpoint='give')
def give(id):
	print(id)
	return render_template("give.html", id=id)


@app.route("/get/id=<id>", endpoint='get')
def get(id):
	query = cur.execute(f"SELECT * FROM posts WHERE book_id='{id}' AND (status=1 OR status=2)")
	results = query.fetchall()
	book_query = cur.execute(f"SELECT name FROM books WHERE id_inherited='{id}'")
	name = book_query.fetchone()[0]
	print(name)
	if len(results) > 0:
		return render_template("get.html", name=name, results=results)
	else:
		empty = "暫時沒有人捐贈這本書..."
		return render_template("get.html", name=name, empty=empty)


@app.route("/giveCallback", endpoint='giveCallback', methods=["GET", "POST"])
@login_is_required
def giveCallback():
	if request.method == "POST":
		id = request.form["id"]
		description = request.form["description"]
		box = request.form["box"]
		book_query = cur.execute(f"SELECT * FROM books WHERE id_inherited={id}")
		book = book_query.fetchone()
		book_name = book[1]
		data = [(id, book_name, session["google_id"], session["name"], description, str(time.time())[-4:], 0, time.ctime(), box)]
		print(data)
		cur.executemany("INSERT INTO posts VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", data)
		con.commit()
		validation_code = validation.generate()
		print(validation_code)
	return render_template("giveCallback.html", code=validation_code)


@app.route("/getCallback", endpoint='getCallback', methods=["GET", "POST"])
@login_is_required
def getCallback():
	if request.method == "POST":
		box= request.form["box"]
		print(box)
		post_id = request.form["post_id"]
		getter_id = session["google_id"]
		post_query = cur.execute(f"SELECT * FROM posts WHERE id={post_id}")
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

		getter_query = cur.execute(
		 f"SELECT coins FROM users WHERE google_id={getter_id}")
		getter_coins = getter_query.fetchone()[0]
		if getter_coins >= 10:
			cur.execute(
			 f"INSERT INTO gets VALUES ('{giver_name}', '{book_name}', '{description}', {post_id}, {getter_id}, {giver_id}, 0, '{box}')")
			cur.execute(f"UPDATE posts SET status=3 WHERE id={post_id};")
			cur.execute(
			 f"UPDATE books SET quantity = quantity-1 WHERE id_inherited={book_id};")

			cur.execute(
			 f"UPDATE users SET coins = coins-10 WHERE google_id={getter_id};")
			con.commit()
			return redirect("/protected")
		else:
			return render_template("getCallback.html")


@app.route("/newBook", endpoint='newBook')
@login_is_required
def newBook():
	return render_template("newBook.html")


@app.route("/sync", endpoint='sync')
@login_is_required
def sync():
	count = cur.execute("SELECT count(*) FROM books")
	current_count = count.fetchone()[0]
	parse_more(current_count)
	return redirect("/query")


@app.route("/admin", endpoint='admin', methods=["GET", "POST"])
@admin_is_required
def admin():
	return render_template("admin.html")


@app.route("/delete", endpoint='delete', methods=["POST"])
@admin_is_required
def delete():
	id = request.form["post_id"]
	print(id)
	user_id_query = cur.execute(f"SELECT user_id FROM posts WHERE id={id}")
	user_id = user_id_query.fetchone()[0]
	user_email_query = cur.execute(f"SELECT email FROM users WHERE google_id={user_id}")
	user_email = user_email_query.fetchone()[0]
	msg = "test msg: weve deleted ur post!"
	notice.send_mail(user_email, "【書愛流動】審核未通過", msg)
	cur.execute(f"DELETE FROM posts WHERE id={id}")
	con.commit()
	return redirect("/admin")


@app.route("/review", endpoint='review', methods=["GET", "POST"])
@admin_is_required
def review():
	if request.method == "POST":
		id = request.form["post_id"]
		posts_query = cur.execute(f"SELECT * FROM posts WHERE status=0 AND id={id}")
	else:
		posts_query = cur.execute("SELECT * FROM posts WHERE status=0")
	posts = posts_query.fetchall()
	return render_template("review.html", posts=posts)


@app.route("/passed", endpoint='passed', methods=["POST"])
@admin_is_required
def passed():
	passed_id = request.form["post_id"]
	cur.execute(f"UPDATE posts SET status=1 WHERE id={passed_id}")
	book_query = cur.execute(f"SELECT book_id FROM posts WHERE id={passed_id}")
	book_id = book_query.fetchone()[0]
	user_query = cur.execute(f"SELECT user_id FROM posts WHERE id={passed_id}")
	user_id = user_query.fetchone()[0]
	print(user_id)
	cur.execute(f"UPDATE books SET quantity=quantity+1 WHERE id_inherited={book_id}")
	cur.execute(f"UPDATE users SET coins=coins+10 WHERE google_id={user_id}")
	con.commit()
	return redirect("/review")
	

@app.route("/censored", endpoint='censored', methods=["POST"])
@admin_is_required
def censored():
	censored_id = request.form["post_id"]
	cur.execute(f"UPDATE posts SET status=2 WHERE id={censored_id}")
	cur.execute(f"UPDATE posts SET description='(不予顯示)' WHERE id={censored_id}")
	book_query = cur.execute(f"SELECT book_id FROM posts WHERE id={censored_id}")
	book_id = book_query.fetchone()[0]
	user_query = cur.execute(f"SELECT user_id FROM posts WHERE id={censored_id}")
	user_id = user_query.fetchone()[0]
	cur.execute(f"UPDATE books SET quantity=quantity+1 WHERE id_inherited={book_id}")
	cur.execute(f"UPDATE users SET coins=coins+10 WHERE google_id={user_id}")
	con.commit()
	return redirect("/review")

@app.route("/policy", endpoint='policy')
def policy():
	return render_template("policy.html")

@app.route("/studyguides", endpoint='studyguides', methods=["POST"])
def studyguides():
	sg_url = "https://study-guides.dstw.dev/cms.php"
	print(request.headers.get("Referer"))
	code = request.form["redeemCode"]
	cur.execute(f"INSERT INTO codes VALUES ({code}, 0)")
	return code + " added"

if __name__ == '__main__':
	app.run(port=8000, host='0.0.0.0', debug=False)
