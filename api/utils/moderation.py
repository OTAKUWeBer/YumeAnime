import re


BANNED_WORDS = {
    "nigger", "nigga", "faggot", "fag", "retard",
    "cunt", "slut", "whore", "fuck", "motherfucker",
    "kys", "kill yourself", "go die", "end yourself",
    "madarchod", "bhenchod", "chutiya", "randi", "gandu", "lund",
    "chod", "choda", "khanki", "bhoda", "chudi", "bainchod",
    "magir pola", "shuwor", "kuttar baccha",
    "sharmuta", "ibn sharmuta", "ya kalb", "ya ibn al kalb",
    "puta", "hijo de puta", "maricon", "cabron",
    "pute", "salope", "connard",
    "hurensohn", "fotze",
    "putang ina", "gago",
    "anjing", "bangsat",
    "orospu", "orospu cocugu",
}

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in BANNED_WORDS) + r")\b",
    re.IGNORECASE,
)

_CONTEXT_PATTERN = re.compile(
    r"\b(bc|mc)\b(?=\s+\w)|\b\w+\s+(bc|mc)\b",
    re.IGNORECASE,
)


def contains_banned_words(text):
    if not text:
        return False
    return bool(_PATTERN.search(text) or _CONTEXT_PATTERN.search(text))
