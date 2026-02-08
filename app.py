from flask import Flask, request, render_template, jsonify, redirect, url_for
from google import genai
from dotenv import load_dotenv
import os
import yfinance as yf
import requests
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

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


def get_six_month_return(symbol):
    ticker = yf.Ticker(symbol)

    hist = ticker.history(period="6mo", auto_adjust=True)

    start_price = hist['Close'].iloc[0]
    end_price = hist['Close'].iloc[-1]

    percentage_return = ((end_price - start_price) / start_price) * 100

    return round(percentage_return, 2)


def get_overall_news_sentiment(news_list):
    """
    Returns a single float (-1.0 to 1.0) representing the average sentiment
    of all news articles provided.
    """
    if not news_list:
        return 0.0

    # Initialize VADER once (more efficient)
    analyzer = SentimentIntensityAnalyzer()
    scores = []

    for article in news_list:
        # Safe extraction: prevents crashes if 'description' or 'content' is None
        title = article.get('title') or ""
        desc = article.get('description') or ""
        content = article.get('content') or ""

        # Combine text
        full_text = f"{title} {desc} {content}"

        # Get ONLY the compound score (The one number you need)
        score = analyzer.polarity_scores(full_text)['compound']
        scores.append(score)

    # Return the simple average
    return np.mean(scores)


app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"), 302)


@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")


@app.route("/main", methods=["GET", "POST"])
def main():
    # Getting user inputs
    name = request.form.get("name")
    stock = request.form.get("stock")
    interest = float(request.form.get("interest"))

    # Using Gemini API to get industry and stock symbol
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_api_key)

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

    # Use Yahoo Finance to get financial information
    try:
        stock_price = get_stock_price(ticker)
        symbol = stock_price["symbol"]
        price = round(stock_price["price"],2)
        currency = stock_price["currency"]
        six_month_return = get_six_month_return(ticker)
    except:
        return "Financial information could not be extracted. Please try again later."

    if six_month_return > interest:
        better_investment = stock
        difference = six_month_return - interest
    else:
        better_investment = "Your current savings plan"
        difference = interest - six_month_return

    # Use News API to get news articles
    news_api_key = os.getenv("NEWS_API_KEY")

    company_news = []
    query = f"{stock} OR {symbol}"
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=5&page=1&searchIn=title&apiKey={news_api_key}"
    response = requests.get(url).json()
    for article in response.get('articles', []):
        company_news.append({
            "title": article['title'],
            "description": article["description"],
            "content": article["content"],
            "source": article['source']['name'],
            "url": article['url'],
            "publishedAt": article['publishedAt']
        })

    industry_news = []
    query = industry
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=5&page=1&searchIn=title&apiKey={news_api_key}"
    response = requests.get(url).json()
    for article in response.get('articles', []):
        industry_news.append({
            "title": article['title'],
            "description": article["description"],
            "content": article["content"],
            "source": article['source']['name'],
            "url": article['url'],
            "publishedAt": article['publishedAt']
        })

    # News Sentiment Analysis
    company_news_sentiment = get_overall_news_sentiment(company_news)
    company_news_sentiment_scaled = int((company_news_sentiment + 1) * 50)


    industry_news_sentiment = get_overall_news_sentiment(industry_news)
    industry_news_sentiment_scaled = int((industry_news_sentiment + 1) * 50)

    # AI Summary
    summary_info = {
        "company": stock,
        "symbol": symbol,
        "industry": industry,
        "current_stock_price": price,
        "stock_price_currency": currency,
        "six_month_stock_return": six_month_return,
        "users_current_savings_plan_interest": interest,
        "difference_between_current_plan_and_stock_return": difference,
        "better_investment_over_last_six_months": better_investment,
        "company_news_articles": company_news,
        "company_news_sentiment_from_zero_to_hundred": company_news_sentiment_scaled,
        "industry_news_articles": industry_news,
        "industry_news_sentiment_from_zero_to_hundred": industry_news_sentiment_scaled
    }

    summary = client.models.generate_content(
        model="gemma-3-27b-it",
        contents=f"You are a personal banking support assistant. Your task is to provide a one paragraph summary of the market situation for a company and industry for the user to make financial decisions. However, you are not supposed to give actual financial advice, just give the user enough information to make the decision themselves. Here is the information you should base you summary on: {summary_info}"
    ).candidates[0].content.parts[0].text

    return render_template("main.html",
                           name = name,
                           stock = stock,
                           interest = interest,
                           industry = industry,
                           symbol = symbol,
                           price = price,
                           currency = currency,
                           stock_return = six_month_return,
                           better_investment = better_investment,
                           difference = difference,
                           company_news = company_news,
                           company_news_sentiment = company_news_sentiment_scaled,
                           industry_news_sentiment = industry_news_sentiment_scaled,
                           industry_news = industry_news,
                           summary = summary
                           )


if __name__ == "__main__":
    app.run(debug=True)
