# falabella_scraper.py
import asyncio
import json
import os
import re
from urllib.parse import urljoin

import django

# --- Configurar Django ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from core.models import ProductoExterno  # noqa: E402
from playwright.async_api import async_playwright

HEADLESS = True


def parse_price(text):
    digits = re.sub(r"\D+", "", text or "")
    return int(digits) if digits else None


async def scrape_falabella(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()

        print(f"🕒 Cargando página: {url}")
        await page.goto(url, timeout=90000)
        await page.wait_for_selector("a[href*='/falabella-cl/product/']", timeout=60000)
        await page.wait_for_timeout(2000)

        cards = await page.query_selector_all("a[href*='/falabella-cl/product/']")
        print(f"🔍 Detectadas {len(cards)} tarjetas de producto (preliminar)")

        base = "https://www.falabella.com/falabella-cl"
        products = []

        for a in cards:
            href = await a.get_attribute("href")
            full_text = " ".join((await a.inner_text()).split())
            if not href or not full_text:
                continue

            url_abs = urljoin(base, href)
            card = a  

            # ---- IMAGEN ----
            img = await card.query_selector("img")
            img_src = await img.get_attribute("src") if img else None

            # 🔥 1. DESCARTAR PRODUCTOS SIN IMAGEN REAL
            if not img_src or not img_src.startswith("http"):
                continue

            # ---- PRECIO ----
            price_el = await card.query_selector("text=$")
            price = None
            if price_el:
                txt = (await price_el.inner_text()).strip()
                price = parse_price(txt)

            if not price:
                continue

            # ---- NOMBRE LIMPIO ----
            parts = full_text.split("$", 1)
            name_clean = parts[0].strip()

            # ---- GUARDAR ----
            products.append(
                {
                    "name": name_clean,
                    "price": price,
                    "brand": "Sony",
                    "category": "Consolas",
                    "url": url_abs,
                    "image": img_src,   # ya validado
                }
            )

        await browser.close()
        return products


def guardar_en_bd(productos):
    """Guarda o actualiza los productos en ProductoExterno."""
    creados = 0
    actualizados = 0

    for p in productos:
        obj, created = ProductoExterno.objects.update_or_create(
            url=p["url"],
            defaults={
                "nombre": p["name"],
                "precio": p["price"],
                "marca": p["brand"],
                "categoria": p["category"],
                "imagen": p["image"],  # imagen real
                "fuente": "Falabella",
            },
        )
        if created:
            creados += 1
        else:
            actualizados += 1

    print(f"💾 Guardados {creados} nuevos, actualizados {actualizados} productos externos.")


if __name__ == "__main__":
    url = "https://www.falabella.com/falabella-cl/category/cat202303/Consolas?f.product.brandName=sony"
    data = asyncio.run(scrape_falabella(url))
    print(f"\n✅ Encontrados {len(data)} productos válidos (con imagen)\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    guardar_en_bd(data)
