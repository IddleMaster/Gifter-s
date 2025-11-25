import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# 1. LISTA BASE DE INSULTOS (forma simple, sin símbolos leet)
# ============================================================
BAD_WORDS = [
    "weon","weón","weona","weonas","wn","qlo","qliao","qlia","culiao","culiá",
    "conchetumadre","conchetumare","conchatumadre","conchatumare",
    "ctm","ctmr","ctmre","csm","csmr","mierda","mrd",
    "maricón","maricon","marikon","marika","hijo del ñato","tula",
    "perra","perro","zorra","puta","puto","putos","putas",
    "huevon","huevón","huevona","gueon","gueona","wea","aweonao","awueonao",
    "pico","pene","verga","coño",
    "chingar","chingado","chingada","chingón","pinche",
    "hdp","hijo de puta","hija de puta",
    "pelotudo","boludo","imbecil","idiota","estupido","estúpido",
    "retrasado","subnormal","mongolico","maraco","mariquita",
    "pajero","pajera",
    "negro ql","negra ql","zorra culiá","zorra ql",
    "puta madre","malparido","qlon",
    "fuck","fucking","motherfucker",
    "shit","bullshit","bitch","asshole","dick","cock","pussy","whore","slut",
    "nigger","nigga",
    "fml","wtf","stfu","gtfo",
    "merda","caralho","otario","viado","bosta",
    "merde","putain","connard","fil de pute","enculé",
    "cazzo","stronzo","puttana","troia",
    "scheisse","arschloch","fotze","hurensohn","wichser",
]


def _leetify(word: str) -> str:
    """Convierte una palabra en una expresión que detecta variantes leet."""
    leet_map = {
        "a": "[a4@Λ∆]",    "e": "[e3€£ɛ]", "i": "[i1!|íìî]", "o": "[o0°øðóòô]",
        "u": "[uúùûüv]",   "c": "[c(¢]",   "l": "[l1|]",     "s": "[s5$z]",
        "t": "[t7+†]",     "g": "[g69]",   "b": "[b8]",      "p": "[pρ]",
        "n": "[nñńη]",     "m": "[mµ]"
    }

    regex = ""
    for ch in word.lower():
        if ch in leet_map:
            regex += leet_map[ch]
        else:
            # cualquier letra admite símbolos antes/después
            regex += f"[{ch}]+"
    return regex

# Construir expresiones leet para TODAS las palabras
LEET_BADWORDS = [ _leetify(w) for w in BAD_WORDS ]

# Construimos un patrón gigante, ultra flexible:
LEET_PATTERN = re.compile(
    r"(" + "|".join(LEET_BADWORDS) + r")",
    flags=re.IGNORECASE
)

# ============================================================
# 3. FUNCIÓN PARA ENMASCARAR PALABRAS
# ============================================================

def _mask(word: str) -> str:
    """Reemplaza letras interiores por * (weon → w**n)."""
    core = re.sub(r'[^a-zA-ZñÑáéíóúÁÉÍÓÚ]', "", word)  # quitar símbolos, dejar letras
    if len(core) <= 2:
        return "*" * len(core)
    return core[0] + "*" * (len(core) - 2) + core[-1]

# ============================================================
# 4. FUNCIÓN PRINCIPAL (CENSURA PERFECTA)
# ============================================================

def censurar(texto: str) -> str:
    """
    Censura insultos en español/inglés, detecta versiones leet,
    variantes con símbolos, números y deformaciones.
    Mantiene espacios, emojis y signos.
    """
    if not texto:
        return texto

    def _replace(match):
        palabra = match.group(0)
        return _mask(palabra)

    try:
        return LEET_PATTERN.sub(_replace, texto)
    except Exception as e:
        logger.error("[Profanity] Error censurando: %s", e)
        return texto

# Compatibilidad con código viejo
censurar_con_openai = censurar
censurar_con_ollama = censurar
