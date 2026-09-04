# scraper.py

import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from config import DEFAULT_CSV_PATH

def scrape_books(url="https://books.toscrape.com/", output_csv=DEFAULT_CSV_PATH):
    """
    Scrapes book title, price, rating, and availability from BooksToScrape.
    Saves cleaned data to output_csv and returns pandas DataFrame.
    """
    print(f"Scraping data from: {url}")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch website. HTTP Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error requesting URL '{url}': {str(e)}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    books = []
    book_cards = soup.find_all("article", class_="product_pod")

    for book in book_cards:
        # Title
        title_tag = book.find("h3")
        title = title_tag.a.get("title") if (title_tag and title_tag.a) else "N/A"

        # Price
        price_tag = book.find("p", class_="price_color")
        price_str = price_tag.text.replace("Â", "").replace("£", "").strip() if price_tag else "0.00"

        # Rating
        rating_tag = book.find("p", class_="star-rating")
        rating = rating_tag["class"][1] if rating_tag and len(rating_tag.get("class", [])) > 1 else "Unknown"

        # Availability
        availability_tag = book.find("p", class_="instock availability")
        availability = availability_tag.text.strip() if availability_tag else "Unknown"

        books.append({
            "Title": title,
            "Price": f"£{price_str}",
            "Rating": rating,
            "Availability": availability
        })

    df = pd.DataFrame(books)

    # Ensure target directory exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"CSV file created successfully at '{output_csv}' ({len(df)} records)")

    return df

if __name__ == "__main__":
    scrape_books()