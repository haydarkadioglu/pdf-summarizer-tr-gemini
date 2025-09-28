import os
import re
from typing import List, Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv
import google.generativeai as genai

SENT_SPLIT_RE = re.compile(r"(?us)(.*?[\.\!\?\:\;]+)(?=\s|$)|(.+?)(?=\n|$)")


def extract_text_from_pdf(path: str) -> str:
    parts = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts)


def split_into_chunks(text: str, max_chars: int = 8000) -> List[str]:
    sents = []
    for m in SENT_SPLIT_RE.finditer(text):
        s = (m.group(1) or m.group(2) or '').strip()
        if s:
            sents.append(s)
    chunks = []
    buf = []
    size = 0
    for s in sents:
        if size + len(s) + 1 > max_chars:
            if buf:
                chunks.append(" ".join(buf))
                buf = []
                size = 0
        buf.append(s)
        size += len(s) + 1
    if buf:
        chunks.append(" ".join(buf))
    return chunks


PARA_CHUNK_PROMPT = (
    "Aşağıdaki Türkçe metni 1-2 paragraf halinde akıcı ve öz bir dille özetle.\n"
    "- Bilimsel/teknik terimleri koru\n"
    "- Madde işaretleri kullanma\n"
    "- Yalnızca metindeki bilgilere dayan\n\n"
    "Metin:\n{content}\n\nÖzet (paragraf):\n"
)

PARA_REDUCE_PROMPT = (
    "Aşağıda aynı belgeden elde edilmiş parça özetleri var.\n"
    "Bu özetleri birleştirerek 2-4 paragraf halinde kısa, tutarlı ve tekrar içermeyen bir nihai özet yaz.\n"
    "Madde işaretleri kullanma; bağlamı akıcı biçimde aktar.\n\n"
    "Parça özetleri:\n{content}\n\nNihai özet (paragraf):\n"
)


def _ensure_gemini(model_name: str) -> genai.GenerativeModel:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY bulunamadı. Lütfen .env dosyasına ekleyin.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def summarize_pdf_paragraphs(
    pdf_path: str,
    model_name: str = "gemini-2.5-flash-lite",
    max_chunk_chars: int = 8000,
    two_stage_threshold: int = 70000,
) -> str:
    """Gemini ile PDF'yi paragraf paragraf özetler (map-reduce).

    Args:
        pdf_path: Özetlenecek PDF yolu.
        model_name: Google Generative AI model adı (örn. gemini-1.5-flash, gemini-1.5-pro).
        max_chunk_chars: Her parça için en fazla karakter.
        two_stage_threshold: Reduce aşamasında bu sınırı aşan metinleri iki kademede birleştir.
    Returns:
        Nihai paragraf özet metni.
    """
    model = _ensure_gemini(model_name)

    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return "PDF'den metin çıkarılamadı. PDF tarama görüntüsü olabilir. OCR deneyin."

    chunks = split_into_chunks(text, max_chars=max_chunk_chars)
    if not chunks:
        return "Metin parçalara ayrılamadı."

    # Map
    partial_summaries = []
    for ch in chunks:
        prompt = PARA_CHUNK_PROMPT.format(content=ch)
        resp = model.generate_content(prompt)
        partial_summaries.append(resp.text.strip())

    # Reduce
    joined = "\n\n".join(partial_summaries)
    if len(joined) > two_stage_threshold:
        mid = len(partial_summaries) // 2
        part1 = "\n\n".join(partial_summaries[:mid])
        part2 = "\n\n".join(partial_summaries[mid:])
        r1 = model.generate_content(PARA_REDUCE_PROMPT.format(content=part1)).text.strip()
        r2 = model.generate_content(PARA_REDUCE_PROMPT.format(content=part2)).text.strip()
        final = model.generate_content(PARA_REDUCE_PROMPT.format(content=r1 + "\n\n" + r2)).text.strip()
    else:
        final = model.generate_content(PARA_REDUCE_PROMPT.format(content=joined)).text.strip()

    return final
