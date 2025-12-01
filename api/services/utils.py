import re, unicodedata

def code_from_label(label: str) -> str:
    """
    Construit un CODE normalisé à partir du label:
    - supprime les accents
    - remplace tout non-alphanum par "_"
    - compresse les "_" multiples
    - trim "_" en bord
    - met en MAJUSCULES
    """
    s = unicodedata.normalize("NFKD", label)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # sans accents
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)  # non-alnum -> _
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()