# ingest/ingest_ccp.py
"""
Ingesta de documentos de la Cámara de Comercio de Pamplona (Colombia)
→ Lee PDF/TXT/MD/HTML, hace chunking y los indexa en Chroma.

Backends de embeddings:
- hf: Hugging Face Inference API (recomendado para 100% nube/ligero)
- local: sentence-transformers (requiere CPU/RAM local)

Uso:
  python -m ingest.ingest_ccp --dir knowledge/ccp --backend hf --reset
  python -m ingest.ingest_ccp --dir knowledge/ccp --backend local --chunk-size 420 --chunk-overlap 80
"""

from __future__ import annotations
import os, re, html, argparse
from pathlib import Path
from typing import List, Tuple, Dict

import asyncio
import httpx

# Lectores opcionales
try:
    from bs4 import BeautifulSoup  # para HTML
    HAS_BS4 = True
except Exception:
    HAS_BS4 = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except Exception:
    HAS_PYPDF = False

# backend local opcional
try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except Exception:
    HAS_ST = False

# Chroma client y settings
from app.chroma_client import get_collection
try:
    from app.settings import get_settings  # si tu proyecto lo tiene
    _HAS_SETTINGS = True
except Exception:
    _HAS_SETTINGS = False

# ----------------------------
# Utilidades de texto / chunking
# ----------------------------

_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")

def normalize_text(t: str) -> str:
    t = t.replace("\x00", " ").replace("\u200b", "")
    t = _WHITESPACE_RE.sub(" ", t)
    return t.strip()

def word_chunks(text: str, chunk_size: int = 400, chunk_overlap: int = 80) -> List[str]:
    """
    Fragmenta por palabras (evitamos dependencias de tokenización).
    chunk_size/overlap aproximan tokens.
    """
    words = text.split()
    if not words:
        return []
    out: List[str] = []
    step = max(1, chunk_size - chunk_overlap)
    for i in range(0, len(words), step):
        slice_words = words[i:i + chunk_size]
        if not slice_words:
            break
        out.append(" ".join(slice_words))
    return out

# ----------------------------
# Lectores
# ----------------------------

def read_pdf(path: Path) -> List[Tuple[str, Dict]]:
    if not HAS_PYPDF:
        raise RuntimeError("pypdf no está instalado. Añádelo a requirements si vas a leer PDFs.")
    reader = PdfReader(str(path))
    items: List[Tuple[str, Dict]] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = normalize_text(txt)
        if not txt:
            continue
        md = {"source": path.name, "source_path": str(path), "page": i + 1, "title": path.stem}
        items.append((txt, md))
    return items

def read_txt(path: Path) -> List[Tuple[str, Dict]]:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    txt = normalize_text(txt)
    if not txt:
        return []
    md = {"source": path.name, "source_path": str(path), "title": path.stem}
    return [(txt, md)]

def read_md(path: Path) -> List[Tuple[str, Dict]]:
    return read_txt(path)

def read_html(path: Path) -> List[Tuple[str, Dict]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if HAS_BS4:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    else:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = html.unescape(text)
    text = normalize_text(text)
    if not text:
        return []
    md = {"source": path.name, "source_path": str(path), "title": path.stem}
    return [(text, md)]

READERS = {
    ".pdf": read_pdf,
    ".txt": read_txt,
    ".md":  read_md,
    ".html": read_html,
    ".htm":  read_html,
}

def load_documents(root_dir: Path) -> List[Tuple[str, Dict]]:
    items: List[Tuple[str, Dict]] = []
    if not root_dir.exists():
        print(f"[WARN] No existe el directorio: {root_dir}")
        return items
    for ext, reader in READERS.items():
        for f in root_dir.rglob(f"*{ext}"):
            try:
                items.extend(reader(f))
            except Exception as e:
                print(f"[WARN] No se pudo leer {f}: {e}")
    return items

# ----------------------------
# Embeddings
# ----------------------------

async def embed_hf(texts: List[str], model: str, hf_token: str) -> List[List[float]]:
    """
    Hugging Face Inference API (feature-extraction).
    Devuelve una lista 2D: [[dim], ...] con mean-pooling estable.
    """
    if not hf_token:
        raise RuntimeError("HF_API_TOKEN no configurado.")
    url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}"
    headers = {"Authorization": f"Bearer {hf_token}"}

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            url,
            headers=headers,
            json={"inputs": texts, "options": {"wait_for_model": True}, "truncate": True},
        )
        r.raise_for_status()
        data = r.json()

    def mean_pool(v):
        # Casos:
        # - Un texto → [[seq, dim]] OR [dim]
        # - Varios textos → [[[seq, dim]], ...]
        if not isinstance(v, list) or not v:
            raise RuntimeError("Formato de embeddings inesperado (no lista).")

        # [dim]
        if v and all(isinstance(x, (int, float)) for x in v):
            return v

        # [seq, dim]
        if v and isinstance(v[0], list) and all(isinstance(x, (int, float)) for x in v[0]):
            seq = len(v); dim = len(v[0])
            return [sum(v[t][d] for t in range(seq)) / max(seq, 1) for d in range(dim)]

        # [[seq, dim], ...]
        pooled = []
        for row in v:
            if row and isinstance(row[0], list) and all(isinstance(x, (int, float)) for x in row[0]):
                seq = len(row); dim = len(row[0])
                pooled.append([sum(row[t][d] for t in range(seq)) / max(seq, 1) for d in range(dim)])
            else:
                raise RuntimeError("Formato de embeddings inesperado (sub-lista).")
        return pooled  # ojo: en llamada externa manejamos este caso

    pooled = mean_pool(data)
    # Normalizamos a lista de vectores
    if pooled and isinstance(pooled[0], list) and all(isinstance(x, (int, float)) for x in pooled[0]):
        # ya es [dim] (1 texto) → [[dim]]
        if all(isinstance(x, (int, float)) for x in pooled):
            return [pooled]
        # o es [[dim], [dim], ...] (n textos)
        return pooled
    raise RuntimeError("No se pudo normalizar embeddings (estructura desconocida).")

def embed_local(texts: List[str], model_name: str) -> List[List[float]]:
    if not HAS_ST:
        raise RuntimeError("sentence-transformers no está instalado (backend local no disponible).")
    model = SentenceTransformer(model_name)
    vecs = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    return vecs.tolist()

async def compute_embeddings(texts: List[str], backend: str, model: str, hf_token: str | None) -> List[List[float]]:
    if backend == "hf":
        return await embed_hf(texts, model, hf_token or "")
    elif backend == "local":
        return embed_local(texts, model)
    else:
        raise ValueError("backend inválido: usa 'hf' o 'local'")

# ----------------------------
# Pipeline principal
# ----------------------------

def build_chunks(items: List[Tuple[str, Dict]], chunk_size: int, chunk_overlap: int) -> Tuple[List[str], List[Dict], List[str]]:
    docs: List[str] = []
    metas: List[Dict] = []
    ids: List[str] = []
    idx = 0
    for text, base_md in items:
        chunks = word_chunks(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for ch in chunks:
            md = dict(base_md)
            md["chunk_size"] = len(ch.split())
            docs.append(ch)
            metas.append(md)
            ids.append(f"ccp_{idx}")
            idx += 1
    return docs, metas, ids

def _get_env_settings():
    """Fallback si no existe app.settings.get_settings()."""
    class S:
        hf_api_token = os.getenv("HF_API_TOKEN") or ""
        hf_embed_model = os.getenv("HF_EMBED_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"
    return S()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, default="knowledge/ccp", help="Directorio raíz con documentos")
    parser.add_argument("--backend", type=str, default="hf", choices=["hf", "local"], help="Backend de embeddings")
    parser.add_argument("--model", type=str, default=None, help="Modelo de embeddings (opcional)")
    parser.add_argument("--chunk-size", type=int, default=420)
    parser.add_argument("--chunk-overlap", type=int, default=80)
    parser.add_argument("--reset", action="store_true", help="Borra documentos previos en la colección")
    args = parser.parse_args()

    s = get_settings() if _HAS_SETTINGS else _get_env_settings()
    root = Path(args.dir)

    # Config por entorno
    hf_token = s.hf_api_token
    model = args.model or getattr(s, "hf_embed_model", None) or "sentence-transformers/all-MiniLM-L6-v2"

    # Carga documentos
    items = load_documents(root)
    if not items:
        print(f"[INFO] No se hallaron documentos en {root.resolve()}")
        return

    docs, metas, ids = build_chunks(items, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    if not docs:
        print("[INFO] No se generaron chunks.")
        return

    # Embeddings
    print(f"[INFO] Generando embeddings con backend={args.backend}, modelo={model} ...")
    embs = await compute_embeddings(docs, backend=args.backend, model=model, hf_token=hf_token)

    # Chroma
    coll = get_collection()
    if args.reset:
        try:
            coll.delete(where={})  # limpiar colección completa
            print("[WARN] Colección limpiada (reset).")
        except Exception as e:
            print(f"[WARN] No se pudo limpiar: {e}")

    # upsert
    try:
        coll.add(documents=docs, metadatas=metas, ids=ids, embeddings=embs)
    except Exception as e:
        print(f"[WARN] Falló add(): {e}. Intentando delete+add por lotes ...")
        B = 512
        for i in range(0, len(ids), B):
            sub_ids = ids[i:i+B]
            try:
                coll.delete(ids=sub_ids)
            except Exception:
                pass
            coll.add(
                documents=docs[i:i+B],
                metadatas=metas[i:i+B],
                ids=sub_ids,
                embeddings=embs[i:i+B],
            )

    print(f"[OK] Ingesta completa: {len(docs)} chunks → colección '{coll.name}'.")
    report = {
        "collection": coll.name,
        "docs": len(docs),
        "unique_sources": sorted({m.get('source') for m in metas if m.get('source')}),
        "backend": args.backend,
        "model": model,
        "dir": str(root.resolve()),
    }
    print(report)

if __name__ == "__main__":
    asyncio.run(main())
