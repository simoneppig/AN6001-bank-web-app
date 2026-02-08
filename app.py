from flask import Flask, request, render_template, jsonify, redirect, url_for

app=Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"), 302)

@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template("login.html")



if __name__ == "__main__":
    app.run(debug=True)