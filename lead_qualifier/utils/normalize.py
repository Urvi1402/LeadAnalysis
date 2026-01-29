import re

_SUFFIXES = [
    "pvt", "pvt.", "ltd", "ltd.", "private", "limited", "llp", "inc", "inc.", "corp", "corp.", "co", "co.", "company"
]

def normalize_company_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"[^a-z0-9&.\- ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # remove suffix tokens at end
    tokens = s.split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()

    s = " ".join(tokens).strip()
    s = s.replace("&", "and")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def clean_display_name(name: str) -> str:
    # keep a nicer display version
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name
