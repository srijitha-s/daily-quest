"""."""

import os
from datetime import datetime
from functools import wraps

# from flask.ext.principal import Principal, Permission, RoleNeed
#  from flask_login import logout_user

from apscheduler.schedulers.background import BackgroundScheduler

import flask
from flask import Flask, render_template, request

import firebase_admin
import google.oauth2.id_token
from dotenv import load_dotenv
from firebase_admin import auth, credentials, db
from google.auth.transport import requests

load_dotenv()
app = Flask(__name__)

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

cred = credentials.Certificate(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
firebase_admin.initialize_app(cred, {
    'databaseURL':
    'https://faqsbymayank-default-rtdb.asia-southeast1.firebasedatabase.app/'
})


app.secret_key = os.getenv("secret_key")


# Disable them in production
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

firebase_request_adapter = requests.Request()


def get_date():
    """Returns date time for url format in firebase"""
    return datetime.now().strftime("%Y/%m/%d")


def get_user_details():
    id_token = request.cookies.get("token")
    if id_token:
        try:
            user_data = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
        except Exception as error:
            print(f"Error in getting user_data: {error}")
            user_data = None
        if user_data:
            return True, user_data
    return False, None


def is_allowed(role):
    """."""
    flg, user_data = get_user_details()
    if not flg:
        return False
    user_email = user_data['email']
    user_id = user_data['user_id']
    ref_url = f"/access_control_list/{role}"
    return (user_id, user_email) in db.reference(ref_url).get().items()


def need_role(role):
    def decorator(fun):
        @wraps(fun)
        def wrapper(*args, **kwargs):
            if is_allowed(role):
                return fun(*args, **kwargs)
            return flask.redirect('/')
        # return {"error": "unauthorised"}
        return wrapper
    return decorator


def auth_required(func):
    """."""
    def _inner_(*args):
        """."""
        id_token = request.cookies.get("token")
        if id_token:
            try:
                user_data = google.oauth2.id_token.verify_firebase_token(
                    id_token, firebase_request_adapter)
            except Exception as error:
                print(f"Error in getting user_data: {error}")
                user_data = None
            if user_data:
                print(f"funtion template, {user_data=}")
                return func(user_data=user_data, *args)
        print("returning detault template")
        return render_template(
            "enter_quest.j2"
        )
    # Renaming the function name:
    _inner_.__name__ = func.__name__
    return _inner_

def push_quest(quest, ans, name):
    ref = db.reference("/QuestionBank") 
    ref.push( {'solution': ans, "name": name, 
               'Quest': quest , "used": 0})

def get_next_free_quest():
    """Use Push to add the questions else this will fail :("""
    ref = db.reference("/QuestionBank") 
    # ref.push( {'ans': 'TODO', 'question': "Write a function to find all the Palindrome Permutations by using different combinations of the characters prensent in the string", "used": 1})
    ref1 = ref.order_by_child("used").equal_to(0)
    data = ref1.limit_to_first(1).get()
    if data:
        key, value = list(data.items())[0]
        print(key)
        today = get_date()
        quest_ref = db.reference(f"/Quests/{today}")
        quest_ref.set(value)
        
        # Now lets update the questionbank
        child = ref.child(key)
        child.update({
            "used": 1
            })

def schedule_quest():
    scheduler = BackgroundScheduler()
    sched.add_job(get_next_free_quest, trigger='cron', hour='04', minute='12', second="01")
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

@app.route("/")
@auth_required
def index(user_data=None):
    """."""
    quest_date = get_date()
    try:
        print(f"{user_data=}")
        # Lets get today's Quest
        ref = db.reference(f'/Quests/{quest_date}/Quest')
    except Exception as error:
        print(f"Error in getting user_data: {error}")
        user_data = None

    return render_template(
        "index1.j2",
        user_data=user_data,
        quest_date=quest_date,
        Quest=ref.get() if ref
        else None
    )


@app.route("/past_quests_by_month", methods=["GET"])
@auth_required
def past_quests_by_month(user_data=None):
    """."""
    print(f"Rendering list_proposed.j2 with {user_data=}")
    return render_template("list_proposed.j2", user_data=user_data)


@app.route("/evaluate_past_quests", methods=["GET"])
@auth_required
@need_role("admins")
def evaluate_past_quests(user_data=None):
    """."""
    print(f"Rendering list_proposed.j2 with {user_data=}")
    return render_template("evaluate_quests.j2", user_data=user_data)


@app.route("/evaluate", methods=["POST"])
@auth_required
def evaluate_quest(user_data=None):
    """."""
    data = request.form.to_dict(flat=False)
    quest_date = data.get('quest_date')[0]
    for key, val in data.items():
        if key != 'quest_date':
            print("lets update the evaluations")
            user = key.split("_")[1]
            path = f"/Quests/{quest_date}/proposed_solution/{user}"
            ref = db.reference(path)
            ref.update({"eval": val[0]})
    return {"task": "done"}


@app.route("/add_quest", methods=["GET", "POST"])
@need_role("admins")
@auth_required
def add_quest(user_data):
    new_quest_path = "/QuestionBank"
    quest = db.reference(new_quest_path)
    print(quest)


@app.route("/get_past_quests_by_month", methods=["POST"])
@auth_required
def get_past_quest_by_month(user_data=None):
    """."""
    data = request.form
    quest_date = data.get("month", datetime.now().strftime("%Y/%m"))
    print(quest_date)
    ref = db.reference(f'/Quests/{quest_date}')
    monthly_data = {}

    for res_data in ref.get():
        monthly_data[res_data] = ref.child(res_data).get()
    return {'data': monthly_data}


@app.route("/submit_solution", methods=['POST'])
@auth_required
def submit_solution(user_data=None):
    """."""
    print(f"{user_data=}")
    proposed_solution = request.form['proposed_solution']
    quest_date = request.form['quest_date']
    user = user_data.get("user_id", "anon")
    url = f"/Quests/{quest_date}/proposed_solution/{user}"
    ref = db.reference(url)
    ref.set({
        "username": user_data.get("name", ""),
        "email": user_data.get("email", ""),
        "proposed": proposed_solution,
    })

    return "<html><body>Thanks for Submitting the solution</body></html>"


@app.route("/logout")
def logout():
    """."""
    id_token = flask.request.cookies.get('token')
    try:
        decoded_claims = google.oauth2.id_token.verify_firebase_token(
            id_token, firebase_request_adapter)
        # decoded_claims = auth.verify_session_cookie(session_cookie)
        auth.revoke_refresh_tokens(decoded_claims['sub'])
        response = flask.make_response(flask.redirect('/'))
        response.set_cookie('token', expires=0)
        return response
    except auth.InvalidSessionCookieError as error:
        print(f"ERRor: {error}")
        return flask.redirect('/')


if __name__ == '__main__':
    get_next_free_quest()
    # for q in ref.order_by_child("used").equal_to(0).get():
    # print(db.reference(f"/QuestionBank/{q}").limitToFirst(1).get())

    # On IBM Cloud Cloud Foundry, get the port number from the environment
    # variable PORT when running this app on the local machine, default
    # the port to 8000
    # port = int(os.getenv('PORT', "8000"))
    # app.run(host='0.0.0.0', port=port, debug=True)
