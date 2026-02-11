import requests

api_key = "d668impr01qots73m1e0d668impr01qots73m1eg" 
url = f"https://finnhub.io/api/v1/news?category=general&token={api_key}"

response = requests.get(url)
news = response.json()
