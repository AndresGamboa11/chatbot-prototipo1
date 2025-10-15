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
import os, re, glob, argparse, html
from pathlib import Path
from typing import List, Tuple, Dict, Iterable

import asyncio
import httpx
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

from app.chroma_client import get_collection
from app.settings import get_settings

# ----------------------------
# Utilidades de texto / chunking
# ----------------------------

_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")

def normalize_text(t: str) -> str:
    t = t.replace("\x00", " ")
    t = t.replace("\u200b", "")
    t = _WHITESPACE_RE.sub(" ", t)
    return t.strip()

def word_chunks(text: str, chunk_size: int = 400, chunk_overlap: int = 80) -> List[str]:
    """
    Fragmenta por palabras para mantener simplicidad (evitamos dependencias a tiktoken).
    chunk_size y chunk_overlap aproximan tokens; ajusta según resultados.
    """
    words = text.split()
    if not words:
        return []
    out = []
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
    items = []
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
    # leemos como texto plano (podrías convertir a HTML/limpiar más si lo necesitas)
    return read_txt(path)

def read_html(path: Path) -> List[Tuple[str, Dict]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = ""
    if HAS_BS4:
        soup = BeautifulSoup(raw, "html.parser")
        # eliminar scripts/estilos
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    else:
        # fallback muy básico si no está bs4
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
    ".md": read_md,
    ".html": read_html,
    ".htm": read_html,
}

def load_documents(root_dir: Path) -> List[Tuple[str, Dict]]:
    items: List[Tuple[str, Dict]] = []
    if not root_dir.exists():
        print(f"[WARN] No existe el directorio: {root_dir}")
        return items
    for ext in READERS.keys():
        for f in root_dir.rglob(f"*{ext}"):
            try:
                items.extend(READERS[ext](f))
            except Exception as e:
                print(f"[WARN] No se pudo leer {f}: {e}")
    return items

# ----------------------------
# Embeddings
# ----------------------------

async def embed_hf(texts: List[str], model: str, hf_token: str) -> List[List[float]]:
    """
    Usa Hugging Face Inference API (feature-extraction pipeline).
    """
    url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}"
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, headers=headers, json={"inputs": texts, "options": {"wait_for_model": True}})
        r.raise_for_status()
        data = r.json()
    # mean-pooling ligero
    def mean_pool(v):
        # [seq, dim]
        if v and isinstance(v[0], list) and all(isinstance(x, (int, float)) for x in v[0]):
            dim = len(v[0]); seq = len(v)
            return [sum(v[t][d] for t in range(seq)) / max(seq, 1) for d in range(dim)]
        # [[seq, dim], ...]
        if v and isinstance(v[0], list) and isinstance(v[0][0], list):
            pooled = [mean_pool(x) for x in v]
            dim = len(pooled[0]); n = len(pooled)
            return [sum(pooled[i][d] for i in range(n)) / max(n, 1) for d in range(dim)]
        raise RuntimeError("Formato de embeddings inesperado")
    return [mean_pool(x) for x in data]

def embed_local(texts: List[str], model_name: str) -> List[List[float]]:
    if not HAS_ST:
        raise RuntimeError("sentence-transformers no está instalado.")
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

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, default="knowledge/ccp", help="Directorio raíz con documentos")
    parser.add_argument("--backend", type=str, default="hf", choices=["hf", "local"], help="Backend de embeddings")
    parser.add_argument("--model", type=str, default=None, help="Modelo de embeddings (opcional)")
    parser.add_argument("--chunk-size", type=int, default=420)
    parser.add_argument("--chunk-overlap", type=int, default=80)
    parser.add_argument("--reset", action="store_true", help="Borra documentos previos en la colección")
    args = parser.parse_args()

    s = get_settings()
    root = Path(args.dir)

    # Config por entorno
    hf_token = s.hf_api_token
    model = args.model or s.hf_embed_model or "sentence-transformers/all-MiniLM-L6-v2"

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
        # Elimina por 'source_path' si existe; si no, vacía todo
        try:
            coll.delete(where={})  # simple: limpiar colección completa
            print("[WARN] Colección limpiada (reset).")
        except Exception as e:
            print(f"[WARN] No se pudo limpiar: {e}")

    # upsert
    # Chroma 0.5.x acepta add() para nuevos ids; si colisiona, puedes manejar delete+add.
    # Para simplicidad: intentamos add; si falla por IDs, borramos esos ids y reintentamos.
    try:
        coll.add(documents=docs, metadatas=metas, ids=ids, embeddings=embs)
    except Exception as e:
        print(f"[WARN] Falló add(): {e}. Intentando delete+add por lotes ...")
        # borrado por ids en lotes
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
    # Sugerencia: guarda un pequeño reporte…
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
