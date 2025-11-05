# core/services/profanity_filter.py
from django.conf import settings
from openai import OpenAI, AuthenticationError, APIError
import re

# === Config OpenAI ===
api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
client = OpenAI(api_key=api_key, timeout=5) if api_key else None

SYSTEM_PROMPT = (
    "Eres un filtro de malas palabras para una red social en español e inglés. "
    "Tu trabajo es devolver el MISMO texto que recibes, pero con las "
    "malas palabras, garabatos e insultos fuertes censurados.\n\n"
    "Reglas:\n"
    "- Mantén el texto igual (mismos espacios, emojis y signos).\n"
    "- Cuando detectes una mala palabra, reemplaza sus letras centrales "
    "por asteriscos, dejando la primera y la última.\n"
    "  Ejemplos:\n"
    '  \"weon\" -> \"w**n\"\n'
    '  \"qlo\" -> \"q*o\"\n'
    '  \"culiao\" -> \"c****o\"\n'
    '  \"fuck\" -> \"f*ck\"\n'
    "- No agregues comentarios, explicaciones ni texto extra. "
    "Solo devuelve el texto censurado."
)

# === Fallback local (blindado) ===
BAD_WORDS = [
    # --- Español ---
    "weon","weón","weona","weonas","wn","qlo","qliao","qlia","culiao","culiá","ql","qla","klo","kliao",
    "conchetumadre","conchetumare","conchatumadre","conchatumare","ctm","ctmr","ctmre","csm","csmr","csmre",
    "mierda","mierd@","mierd#","mierd0","mrd","maricón","maricon","marikon","marika","marikón",
    "perra","perro","zorra","puta","puto","putos","putas","putazo","putaza","putita",
    "huevon","huevón","huevona","gueon","gueona","wea","weás","wna","weno",
    "ctmrd","ctmrq","ctmq","csmq","pico","pene","verga","vergazo","vergaso","coño","coñazo",
    "chingar","chingado","chingada","chingón","chingona","pinche","pinches",
    "hijo de puta","hija de puta","hdp",
    "carepoto","careverga","caremonda","careculo","carechimba",
    "cabrón","cabron","pelotudo","boludo",
    "imbecil","imbécil","idiota","estupido","estúpido","estupida","estúpida",
    "retrasado","subnormal","mongólico","mongolico","maraco","maraka","mariquita",
    "tarado","tarada","pajero","pajera",
    "hijo de perra","perra ctm","zorra culiá","zorra ql","wea ql","mierda ql",
    "puta madre","negro ql","negra ql","mariconazo","malparido","maldito",
    "sapoperro","qlon","aweonao", 

    # --- Inglés ---
    "fuck","fucks","fucking","fucker","motherfucker","motherfuckers",
    "shit","shits","shitty","bullshit","bastard","bitch","bitches",
    "asshole","ass","dick","dicks","dickhead","cock","cocksucker",
    "pussy","pussies","slut","whore","cum","cumshot","jerkoff","jerking",
    "nigger","nigga","retard","retarded","dumbass","jackass","loser",
    "niggers","niggas",
    "fml","wtf","stfu","gtfo",
    "fck","fcking","fcker","fckr","f@ck",
    "b!tch","b1tch","sh!t","a$$","a$$hole","d!ck","d1ck",
    "suckmydick","eatshit",

    # --- Portugués ---
    "merda","porra","caralho","putinha","vadia",
    "vagabunda","vagabundo","otário","otario","burro","arrombado",
    "foda","fodase","fuder","fdp","filhodaputa","filho da puta",
    "corno","cornudo","viado","viadinho","bosta",
    "cuzão","cuzona","desgraçado","pqp","pau","pau no cu","pauzudo",

    # --- Francés ---
    "merde","putain","salope","connard","con","batard","nique","nique ta mere",
    "ta gueule","fils de pute","enfoiré","bordel","cul","bite","chienne",
    "enculé","encule","pute",

    # --- Italiano ---
    "cazzo","stronzo","puttana","troia","merda","bastardo",
    "culo","vaffanculo","porca","minchia","testa di cazzo",

    # --- Alemán ---
    "scheisse","arschloch","fotze","hurensohn","wichser","miststück",

    # --- Variaciones con símbolos ---
    "f*ck","f@ck","sh!t","b!tch","b1tch","a$$","a$$hole","d1ck","d!ck",
    "n1gga","p3rra","cabr0n","m!erda","m13rda",
    "pvt@","pvt0","put@","ql@","q1o","q10","cul1o","cul1@","cvli@",

    # --- Abreviaciones de internet ---
    "wtf","stfu","gtfo","omfg","lmfao","lmao","fml","smh","idgaf",
    "smd","btch","mf","mfer","fuq","fuk","fuken","fkn",
    "nibba","bish","biatch","thot","hoe","skank","simp",
]

# Compilamos el patrón
_pattern = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in BAD_WORDS) + r")\b",
    flags=re.IGNORECASE,
)


def _enmascarar_palabra(palabra: str) -> str:
    """
    Reemplaza letras internas de la palabra por asteriscos
    dejando primera y última letra.
    """
    if len(palabra) <= 2:
        return "*" * len(palabra)
    return palabra[0] + "*" * (len(palabra) - 2) + palabra[-1]


def _censurar_basico(texto: str) -> str:
    """Filtro rápido local sin IA."""

    def _repl(match: re.Match) -> str:
        original = match.group(0)
        # Si es una frase con espacios ("hijo de puta"), censuramos cada palabra.
        if " " in original:
            partes = original.split(" ")
            return " ".join(_enmascarar_palabra(p) for p in partes)
        return _enmascarar_palabra(original)

    return _pattern.sub(_repl, texto)


def censurar_con_openai(texto: str) -> str:
    """
    Devuelve el texto con malas palabras censuradas.
    - Intenta primero con OpenAI (GPT).
    - Si falla o no detecta nada, usa el filtro local.
    """
    if not texto:
        return texto

    resultado = None

    # 1) Intento con OpenAI
    if client is not None:
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": texto},
                ],
            )
            contenido = resp.choices[0].message.content
            resultado = (contenido or "").strip()
        except (AuthenticationError, APIError, Exception) as e:
            print("[OpenAI] Error en censurar_con_openai:", e)
            resultado = None

    # 2) Fallback local
    if not resultado or resultado == texto:
        return _censurar_basico(texto)

    return resultado
