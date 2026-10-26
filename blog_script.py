import os
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configuration
GOOGLE_NEWS_RSS_URL = os.getenv('GOOGLE_NEWS_RSS_URL', 'https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja')

# Hatena Blog API Configuration
HATENA_ID = os.getenv('HATENA_ID')
HATENA_BLOG_ID = os.getenv('HATENA_BLOG_ID')
HATENA_API_KEY = os.getenv('HATENA_API_KEY')

# Set up Gemini API key (version-independent 'latest')
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def fetch_news(rss_url):
    """Fetches news from the given RSS URL."""
    try:
        response = requests.get(rss_url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return None

def parse_news(rss_content):
    """Parses RSS content and extracts news articles."""
    soup = BeautifulSoup(rss_content, 'xml')
    articles = []
    for item in soup.find_all('item'):
        title = item.title.text if item.title else 'No Title'
        link = item.link.text if item.link else 'No Link'
        pub_date = item.pubDate.text if item.pubDate else 'No Date'
        articles.append({'title': title, 'link': link, 'pub_date': pub_date})
    return articles

def generate_gemini_response(prompt):
    """Generates a response using the Gemini API."""
    try:
        model = genai.GenerativeModel('gemini-flash-lite-latest') # 必要に応じて調整、または latest 相当モデル
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating Gemini response: {e}")
        return ""

def post_to_hatena_blog(title, content, categories=None, draft=False):
    """Posts content to Hatena Blog using Basic Authentication."""
    if not all([HATENA_ID, HATENA_BLOG_ID, HATENA_API_KEY]):
        print("Error: HATENA_ID, HATENA_BLOG_ID, or HATENA_API_KEY is not set.")
        return False

    url = f"https://blog.hatena.ne.jp/{HATENA_ID}/{HATENA_BLOG_ID}/atom/entry"

    now = datetime.now()
    formatted_now = now.strftime("%Y/%m/%d %H:%M:%S")
    full_title = f"{title} - {formatted_now}"

    categories = categories or ["ニュース"]
    category_tags = "".join([f'<category term="{cat}" />' for cat in categories])
    draft_flag = "yes" if draft else "no"

    xml_data = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:app="http://www.w3.org/2007/app">
  <title>{full_title}</title>
  <author><name>{HATENA_ID}</name></author>
  <content type="text/html"><![CDATA[{content}]]></content>
  {category_tags}
  <app:control>
    <app:draft>{draft_flag}</app:draft>
  </app:control>
</entry>""".encode('utf-8')

    try:
        response = requests.post(
            url,
            data=xml_data,
            auth=(HATENA_ID, HATENA_API_KEY),
            headers={'Content-Type': 'application/xml'}
        )
        response.raise_for_status()

        root = ET.fromstring(response.text)
        alternate_link = ""
        for link in root.findall('{http://www.w3.org/2005/Atom}link'):
            if link.attrib.get('rel') == 'alternate':
                alternate_link = link.attrib.get('href')
                break

        print(f"Successfully posted to Hatena Blog: {alternate_link or response.status_code}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to Hatena Blog: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response details: {e.response.text}")
        return False

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching news...")
    rss_content = fetch_news(GOOGLE_NEWS_RSS_URL)
    if rss_content:
        articles = parse_news(rss_content)
        if not articles:
            print("No articles found.")
            return

        for article in articles[:3]:
            print(f"Processing article: {article['title']}")
            #prompt = f"この記事について感想を200字程度でまとめてください。記事のタイトル: {article['title']}\n記事のリンク: {article['link']}"
            #prompt = f"この記事について感想を200字程度でまとめてください。記事のタイトル: {article['title']}"
            prompt = f"以下の記事タイトルから受ける印象や感想を、前置きや断り書きの一切なしで、200字程度で自然な文章としてまとめてください。\n記事のタイトル: {article['title']}"

            impression = generate_gemini_response(prompt)

            if impression:
                blog_content = f"<h1>{article['title']}</h1>\n<p><strong>公開日:</strong> {article['pub_date']}</p>\n<p><strong>リンク:</strong> <a href=\"{article['link']}\">{article['link']}</a></p>\n<h2>感想</h2>\n<p>{impression}</p>"
                post_to_hatena_blog(article['title'], blog_content)
            else:
                print(f"Could not generate impression for {article['title']}")
    else:
        print("Failed to fetch RSS content.")

if __name__ == '__main__':
    main()