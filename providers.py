import os, requests
from typing import List, Union

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_HF_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_EMBED_MODEL}"
_HF_HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

def hf_embed(texts: Union[str, List[str]]) -> List[List[float]]:
    """
    Devuelve embeddings 2D: [[dim], [dim], ...] aun si se pasa un solo texto.
    """
    if isinstance(texts, str):
        payload = {"inputs": [texts], "truncate": True}
    else:
        payload = {"inputs": texts, "truncate": True}

    r = requests.post(_HF_URL, headers=_HF_HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    # La API a veces devuelve 2D si mandas 1 texto, o 3D si mandas varios; normalizamos.
    if isinstance(texts, str):
        # data: [dim] -> [[dim]]
        return [data]
    else:
        # data: [[dim], [dim], ...]
        return data
