from flask import Flask, request, render_template, redirect, url_for
from google import genai
from dotenv import load_dotenv
import os
import json
import yfinance as yf
import requests
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from concurrent.futures import ThreadPoolExecutor

# Loading environment to retrieve the API keys
load_dotenv()


# Defining helper functions to be used in the main code

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


def get_financial_info(symbol):
    financial_data = {}

    try:
        stock_price = get_stock_price(symbol)
        financial_data["symbol"] = stock_price["symbol"]
        financial_data["price"] = round(stock_price["price"], 2)
        financial_data["currency"] = stock_price["currency"]
        financial_data["six_month_return"] = get_six_month_return(symbol)
        return financial_data
    except:
        return "not found"


def get_company_news(company_name, ticker):
    news_api_key = os.getenv("NEWS_API_KEY")
    company_news = []
    query = f"{company_name} OR {ticker}"
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

    return company_news


def get_industry_news(industry):
    news_api_key = os.getenv("NEWS_API_KEY")
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

    return industry_news


def get_overall_news_sentiment(news_list):
    if not news_list:
        return 0.0

    analyzer = SentimentIntensityAnalyzer()
    scores = []

    for article in news_list:
        title = article.get('title') or ""
        desc = article.get('description') or ""
        content = article.get('content') or ""

        full_text = f"{title} {desc} {content}"

        score = analyzer.polarity_scores(full_text)['compound']
        scores.append(score)

    return np.mean(scores)

#Flask Setup
app = Flask(__name__)

# Flask pages

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
    model = "gemini-2.5-flash"
    client = genai.Client(api_key=gemini_api_key)

    ai_response = client.models.generate_content(
        model=model,
        contents=f"Please return the industry and the correct Yahoo finance symbol/ticker for the following company: {stock} Return the output strictly as a JSON object with keys 'industry' and 'ticker'. If not found, return 'not found' in the respective value."
    ).candidates[0].content.parts[0].text

    clean_response = ai_response.replace("```json", "").replace("```", "").strip()
    ai_response_json = json.loads(clean_response)

    industry = ai_response_json.get("industry")
    ticker = ai_response_json.get("ticker")

    if industry.strip() == "not found":
        return render_template("error.html", error_message="Company not found.")

    if ticker.strip() == "not found":
        return render_template("error.html", error_message="Company is not publicly listed.")

    # Parallelising external API calls to speed up loading times
    with ThreadPoolExecutor() as executor:
        financial_data_submit = executor.submit(get_financial_info, ticker)
        company_news_submit = executor.submit(get_company_news, stock, ticker)
        industry_news_submit = executor.submit(get_industry_news, industry)

        financial_data = financial_data_submit.result()
        company_news = company_news_submit.result()
        industry_news = industry_news_submit.result()

    # Processing financial data from Yahoo Finance
    if financial_data == "not found":
        return render_template("error.html", error_message="Financial information could not be extracted. Please try again later.")
    else:
        symbol = financial_data["symbol"]
        price = financial_data["price"]
        currency = financial_data["currency"]
        six_month_return = financial_data["six_month_return"]

    if six_month_return > interest:
        better_investment = stock
        difference = round((six_month_return - interest),2)
    else:
        better_investment = "Your current savings plan"
        difference = round((interest - six_month_return),2)

    # Analysing news sentiment
    company_news_sentiment = get_overall_news_sentiment(company_news)
    company_news_sentiment_scaled = int((company_news_sentiment + 1) * 50)

    industry_news_sentiment = get_overall_news_sentiment(industry_news)
    industry_news_sentiment_scaled = int((industry_news_sentiment + 1) * 50)

    # Creating AI summary
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
        model=model,
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
    app.run(debug=False)