# core/services/calendarific.py

import requests
from datetime import date, datetime
from django.conf import settings

API_URL = "https://calendarific.com/api/v2/holidays"
API_CHILE = "https://apis.digital.gob.cl/fl/feriados"

# === Traducción feriados chilenos ===
HOLIDAY_ES_CL = {
    "Reformation Day": "Día de las Iglesias Evangélicas y Protestantes",
    "Christmas Day": "Navidad",
    "New Year's Day": "Año Nuevo",
    "Labor Day": "Día del Trabajador",
    "Independence Day": "Fiestas Patrias (18 de septiembre)",
    "Army Day": "Fiestas Patrias (19 de septiembre)",
    "Good Friday": "Viernes Santo",
    "Holy Saturday": "Sábado Santo",
    "All Saints' Day": "Día de Todos los Santos",
    "Immaculate Conception": "Inmaculada Concepción",
    "Assumption Day": "Asunción de la Virgen",
    "Saint Peter and Saint Paul": "San Pedro y San Pablo",
    "Columbus Day": "Encuentro de Dos Mundos",
    "National Day": "Fiestas Patrias",
    "Indigenous Peoples' Day": "Día Nacional de los Pueblos Indígenas",
    "Day of the Glories of the Navy": "Día de las Glorias Navales",
    "Day of the Evangelical and Protestant Churches": "Día de las Iglesias Evangélicas y Protestantes",

    # Días regalables
    "Mother's Day": "Día de la Madre",
    "Father's Day": "Día del Padre",
    "Valentine's Day": "Día de San Valentín",
}

OCASIONES_PRIORITARIAS = {
    "Mother's Day",
    "Father's Day",
    "Valentine's Day",
    "Christmas Day",
    "New Year's Day",
    "Independence Day",
    "National Day",
}


# ===============================================================
# 1️⃣ Calendarific (principal)
# ===============================================================
def _fetch_calendarific(year: int, country: str):
    try:
        api_key = settings.CALENDARIFIC_API_KEY
        if not api_key:
            return None

        r = requests.get(
            API_URL,
            params={"api_key": api_key, "country": country, "year": year},
            timeout=10,
        )

        # Si la API falla → retornar None
        if r.status_code != 200:
            return None

        data = r.json()

        # Si credenciales inválidas o permisos insuficientes
        if data.get("meta", {}).get("error_type"):
            return None

        return data.get("response", {}).get("holidays", [])

    except Exception:
        return None


def _normalize_calendarific(raw, country: str):
    if not raw:
        return []

    parsed = []

    for h in raw:
        try:
            iso = h.get("date", {}).get("iso")
            d = datetime.fromisoformat(iso).date()
        except Exception:
            continue

        name_en = h.get("name", "")
        name_es = HOLIDAY_ES_CL.get(name_en, name_en)

        parsed.append({
            "date": d,
            "name": name_en,
            "name_es": name_es,
            "type": h.get("type", []),
            "description": h.get("description", ""),
            "country": country,
        })

    parsed.sort(key=lambda x: x["date"])
    return parsed


# ===============================================================
# 2️⃣ API OFICIAL DE CHILE (fallback)
# ===============================================================
def _fetch_chile_api():
    try:
        r = requests.get(API_CHILE, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    parsed = []
    for h in data:
        try:
            d = datetime.fromisoformat(h["fecha"]).date()
        except Exception:
            continue

        parsed.append({
            "date": d,
            "name": h["nombre"],
            "name_es": h["nombre"],
            "type": [h.get("tipo", "")],
            "description": "",
            "country": "CL",
        })

    parsed.sort(key=lambda x: x["date"])
    return parsed



def next_holiday(country=None):
    """
    1) Intenta Calendarific
    2) Si no trae nada, usa API del Gobierno de Chile (fallback)
    """
    country = country or getattr(settings, "CALENDARIFIC_COUNTRY", "CL") or "CL"
    today = date.today()

    # === 1) Calendarific ===
    try:
        raw_this_year = _fetch_calendarific(today.year, country)
        holidays_this_year = _normalize_calendarific(raw_this_year, country)

        # Prioritarios
        for h in holidays_this_year:
            if h["date"] >= today and h["name"] in OCASIONES_PRIORITARIAS:
                return h

        # Cualquier feriado posterior
        for h in holidays_this_year:
            if h["date"] >= today:
                return h

        # Año siguiente
        raw_next_year = _fetch_calendarific(today.year + 1, country)
        holidays_next_year = _normalize_calendarific(raw_next_year, country)

        if holidays_next_year:
            return holidays_next_year[0]

    except Exception:
        pass  # ignoramos errores de Calendarific

    # === 2) API oficial de Chile ===
    try:
        data = _fetch_chile_api()
        for h in data:
            if h["date"] >= today:
                return h
    except Exception:
        pass

    return None

