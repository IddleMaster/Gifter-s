# falabella_scraper.py
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# User-Agent decente para no parecer script malicioso
HEADERS = {
    "User-Agent": "gifters-scraper/0.1 (+https://tu-sitio.cl)"
}


def parse_price(text):
    """
    Recibe algo como '$ 579.990' y devuelve 579990 (int).
    """
    if not text:
        return None
    # nos quedamos solo con dígitos
    digits = re.sub(r"\D+", "", text)
    if not digits:
        return None
    return int(digits)


def scrape_falabella_listing(listing_url, category_name="Consolas"):
    """
    Descarga una página de categoría de Falabella y devuelve
    una lista de productos con:
      - name
      - price
      - brand
      - category
      - url
      - image
    """
    resp = requests.get(listing_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    products = []

    # === 1) Buscar todos los links que parecen ser de producto ===
    # Falabella suele usar /falabella-cl/product/ en las URLs de producto
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/falabella-cl/product/" not in href:
            continue

        url = urljoin(resp.url, href)

        # título: texto del link
        name = a.get_text(strip=True)
        if not name:
            continue

        # evitar duplicar el mismo producto varias veces
        if any(p["url"] == url for p in products):
            continue

        # === 2) Intentar encontrar el "contenedor" de la tarjeta ===
        card = a
        for parent in a.parents:
            if parent.name in ("article", "div", "li"):
                # heurística: si dentro hay el texto "Agregar al Carro", lo tomamos como tarjeta
                if parent.find(string=lambda s: s and "Agregar al Carro" in s):
                    card = parent
                    break

        # === 3) BRAND ===
        brand = None

        # Algunas páginas usan data-qa="product-brand"
        brand_el = card.find(attrs={"data-qa": "product-brand"})
        if brand_el:
            brand = brand_el.get_text(strip=True)
        else:
            # Heurística: buscar textos en mayúscula tipo "SONY"
            for tag in card.find_all(["strong", "b", "span"], recursive=True):
                txt = tag.get_text(strip=True)
                if txt.isupper() and 2 <= len(txt) <= 25:
                    brand = txt
                    break

        # === 4) IMAGE ===
        image = None
        img = card.find("img")
        if img:
            src = img.get("data-src") or img.get("data-original") or img.get("src")
            if src:
                image = urljoin(resp.url, src)

        # === 5) PRICE ===
        price = None
        # buscamos el primer elemento que tenga un "$" y dígitos
        for el in card.find_all(["span", "div", "p"]):
            txt = el.get_text(strip=True)
            if "$" in txt and any(c.isdigit() for c in txt):
                candidate = parse_price(txt)
                if candidate:
                    price = candidate
                    break

        # si no encontramos precio, mejor saltar el producto
        if not price:
            continue

        product = {
            "name": name,
            "price": price,
            "brand": brand,
            "category": category_name,
            "url": url,
            "image": image,
        }
        products.append(product)

    return products


if __name__ == "__main__":
    # Ejemplo: Consolas Sony en Falabella
    LISTING_URL = (
        "https://www.falabella.com/falabella-cl/category/cat202303/Consolas"
        "?f.product.brandName=sony"
    )

    items = scrape_falabella_listing(LISTING_URL, category_name="Consolas")

    print(f"Encontrados {len(items)} productos\n")
    print(json.dumps(items, ensure_ascii=False, indent=2))
