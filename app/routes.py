from app import app
from flask import render_template, request, redirect, url_for, send_file
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import requests
import json
import os
import io
from app import utils

@app.route('/')
@app.route('/index')
def index():
    return render_template("index.html")

@app.route('/extract', methods=['POST','GET'])
@app.route('/extract', methods=['POST', 'GET'])
def extract():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        url = f"https://www.ceneo.pl/{product_id}"
        response = requests.get(url=url)
        if response.status_code == requests.codes['ok']:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions_count = utils.extract(page_dom, "a.product-review__link > span")

            if opinions_count:
                product_name = utils.extract(page_dom, "h1")
                url = f"https://www.ceneo.pl/{product_id}/opinie-1"
                all_opinions = []
                while (url):
                    response = requests.get(url)
                    page_dom = BeautifulSoup(response.text, "html.parser")
                    opinions = page_dom.select("div.js_product-review")
                    for opinion in opinions:
                        single_opinion = {
                            key: utils.extract(opinion, *value)
                                for key, value in utils.selectors.items()
                        }
                        all_opinions.append(single_opinion)
                    try:
                        url = "https://www.ceneo.pl" + utils.extract(page_dom, "a.pagination__next", "href")
                    except TypeError:
                        url = None
                if not os.path.exists("app/data"):
                    os.mkdir("app/data")
                if not os.path.exists("app/data/opinions"):
                    os.mkdir("app/data/opinions")
                with open(f"app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as jf:
                    json.dump(all_opinions, jf, indent=4, ensure_ascii=False)
                opinions = pd.DataFrame.from_dict(all_opinions)
                opinions.rating = opinions.rating.apply(lambda r: r.split("/")[0].replace(",","."), ).astype(float)
                opinions.recommendation = opinions.recommendation.apply(lambda r: "Brak rekomendacji" if r is None else r)
                stats = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "opinions_count": opinions.shape[0],
                    "pros_count": int(opinions.pros.apply(lambda p: 1 if p else 0).sum()),
                    "cons_count": int(opinions.cons.apply(lambda c: 1 if c else 0).sum()),
                    "average_rating" : opinions.rating.mean(),
                    "rating_distribution" : opinions.rating.value_counts().reindex(np.arange(0,5.5,0.5), fill_value=0).to_dict(),
                    "recommendation_distribution" :opinions.recommendation.value_counts().reindex(["Polecam", "Nie polecam", "Brak rekomendacji"], fill_value=0).to_dict()
                }                

                if not os.path.exists("app/data/stats"):
                    os.mkdir("app/data/stats")
                with open(f"app/data/stats/{product_id}.json", "w", encoding="UTF-8") as jf:
                    json.dump(stats, jf, indent=4, ensure_ascii=False)
                    
                return redirect(url_for('product', product_id=product_id))
            error = "Brak opinii 🙁"
            return render_template('extract.html', error=error)
        error = "Błędny kod - strona nie istnieje 🙁"
        return render_template('extract.html', error=error)
    return render_template('extract.html')

@app.route('/products')
def products():
    products_list = [filename.split(".")[0] for filename in os.listdir("app/data/opinions")]
    products = []
    for product_id in products_list:
        with open(f"app/data/stats/{product_id}.json", "r", encoding="UTF-8") as jf:
            products.append(json.load(jf))
    return render_template("products.html", products = products)

@app.route('/author')
def author():
    return render_template("author.html")

@app.route('/product/<product_id>')
def product(product_id):
    with open(f"app/data/opinions/{product_id}.json", "r", encoding="UTF-8") as jf:
        opinions_data = json.load(jf)

    opinions_df = pd.DataFrame(opinions_data)

    sort_by = request.args.get('sort_by')
    if sort_by in opinions_df.columns:
        opinions_df = opinions_df.sort_values(by=sort_by)

    return render_template('product.html', product_id=product_id, opinions=opinions_df.to_html(classes='table table-striped', index=False))

@app.route('/product/download_json/<product_id>')
def download_json(product_id):
    return send_file(f"data/opinions/{product_id}.json", "text/json", as_attachment=True)

@app.route('/product/download_csv/<product_id>')
def download_csv(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    buffer = io.BytesIO(opinions.to_csv(sep=";", decimal=",", index=False).encode())
    return send_file(buffer, "text/json", as_attachment=True, download_name=f"{product_id}.csv")

@app.route('/product/download_xlsx/<product_id>')
def download_xlsx(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        opinions.to_excel(writer, index=False, sheet_name='Opinions')
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{product_id}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
