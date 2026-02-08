from flask import Flask, request, render_template, jsonify, redirect, url_for
from google import genai
from dotenv import load_dotenv
import os
import yfinance as yf

load_dotenv()


def get_stock_price(symbol):
    ticker = yf.Ticker(symbol)

    current_price = ticker.fast_info['last_price']
    currency = ticker.fast_info['currency']

    return {
        "symbol": symbol.upper(),
        "price": current_price,
        "currency": currency
    }


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

    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    industry = client.models.generate_content(
        model="gemma-3-27b-it",
        contents=f"Please return the industry related to the following company: {stock} Only return the industry name, nothing else. If the company does not exist, return 'not found'."
    ).candidates[0].content.parts[0].text

    if industry.strip() == "not found":
        return "Company not found."

    ticker = client.models.generate_content(
        model="gemma-3-27b-it",
        contents=f"Please return the correct Yahoo finance symbol/ticker for the following company: {stock} Remember to return the correct suffix, e.g. .SI for Singapore, .DE for Germany, etc. (no suffix for US). Only return the symbol, nothing else. If the company does not exist or is not publicly listed, return 'not found'."
    ).candidates[0].content.parts[0].text

    if ticker.strip() == "not found":
        return "Company is not publicly listed."

    try:
        stock_price = get_stock_price(ticker)
    except:
        stock_price = "not found"
        return "Financial information could not be extracted. Please try again later."


    return render_template("main.html", name=name, stock=stock, interest=interest, industry=industry, price=stock_price)

if __name__ == "__main__":
    app.run(debug=True)