# core/services/calendarific.py
import requests
from datetime import date, datetime
from django.conf import settings

API_URL = "https://calendarific.com/api/v2/holidays"

# === Traducción y priorización de feriados chilenos ===
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
    # Observancias frecuentes (regalables)
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


def _fetch_holidays(year: int, country: str):
    api_key = settings.CALENDARIFIC_API_KEY
    if not api_key:
        raise RuntimeError("Falta CALENDARIFIC_API_KEY")
    r = requests.get(
        API_URL,
        params={"api_key": api_key, "country": country, "year": year},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("response", {}).get("holidays", [])


def _normalize_holidays(raw_holidays, country: str):
    """Convierte la respuesta cruda en una lista ordenada con name_es incluido."""
    parsed = []
    for h in raw_holidays:
        iso = h.get("date", {}).get("iso")
        try:
            d = datetime.fromisoformat(iso).date()
        except Exception:
            continue

        name_en = h.get("name", "")
        name_es = HOLIDAY_ES_CL.get(name_en, name_en)

        parsed.append(
            {
                "date": d,
                "name": name_en,      # nombre original de Calendarific
                "name_es": name_es,   # nombre traducido / “chilenizado”
                "type": h.get("type", []),
                "description": h.get("description", ""),
                "country": country,
            }
        )

    parsed.sort(key=lambda x: x["date"])
    return parsed


def next_holiday(country=None):

    country = country or getattr(settings, "CALENDARIFIC_COUNTRY", "CL") or "CL"
    today = date.today()

    # === Año actual ===
    raw_this_year = _fetch_holidays(today.year, country)
    holidays_this_year = _normalize_holidays(raw_this_year, country)

    # 1) Próxima ocasión “importante” (Madre/Padre/Navidad/etc.) que no haya pasado
    for h in holidays_this_year:
        if h["date"] >= today and h["name"] in OCASIONES_PRIORITARIAS:
            return h

    # 2) Si no hay de esas, el próximo feriado cualquiera
    for h in holidays_this_year:
        if h["date"] >= today:
            return h

    # === Año siguiente (si ya no queda nada este año) ===
    raw_next_year = _fetch_holidays(today.year + 1, country)
    holidays_next_year = _normalize_holidays(raw_next_year, country)
    return holidays_next_year[0] if holidays_next_year else None
