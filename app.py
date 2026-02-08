from flask import Flask, request, render_template, jsonify, redirect, url_for

app=Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"), 302)

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/main", methods=["GET", "POST"])
def main():
    name = request.form.get("name")
    stock = request.form.get("stock")
    interest = request.form.get("interest")


    return render_template("main.html", name=name, stock=stock, interest=interest)

if __name__ == "__main__":
    app.run(debug=True)