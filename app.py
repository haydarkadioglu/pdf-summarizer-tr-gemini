import os
import io
import tempfile

import streamlit as st

from summarizer import summarize_pdf_paragraphs

st.set_page_config(page_title="PDF Özetleyici", page_icon="📄", layout="wide")
st.title("📄 PDF Özetleyici (Gemini)")

st.markdown(
    """
    - .env dosyanıza GOOGLE_API_KEY eklediğinizden emin olun.
    - PDF dosyası yükleyin ya da mevcut bir dosya yolunu girin.
    - Çıkış formatı: Paragraf paragraf özet.
    """
)

# Sidebar
with st.sidebar:
    recommended_models = [
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    selected_model = st.selectbox("Model (önerilen)", recommended_models, index=0)
    custom_model = st.text_input(
        "Özel model (opsiyonel)",
        value=selected_model,
        placeholder="ör. models/gemini-2.5-flash-lite",
    )

    # 'models/' önekinin yazılması halinde SDK için normalleştir
    def normalize_model_name(name: str) -> str:
        name = name.strip()
        return name.removeprefix("models/") if name.lower().startswith("models/") else name

    model_name = normalize_model_name(custom_model) if custom_model.strip() else selected_model

    max_chunk_chars = st.slider("Parça boyutu (karakter)", 2000, 12000, 8000, 500)
    two_stage_threshold = st.slider("İki kademeli reduce eşiği", 20000, 120000, 70000, 5000)

# İki kolonlu düzen
left_column, right_column = st.columns(2)

with left_column:
    uploaded = st.file_uploader("PDF yükle", type=["pdf"])  # kullanıcı dosya yüklerse
    manual_path = st.text_input("Ya da PDF dosya yolu girin", value="TUBA-978-605-2249-48-2_Ch9.pdf")
    user_text = st.text_area("Kendi metninizi girin (opsiyonel)", placeholder="Buraya metin girin...")
    run = st.button("Özetle")

with right_column:
    if run:
        pdf_path = None
        if uploaded is not None:
            # Geçici dosyaya kaydedip yol üzerinden işleyelim
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                pdf_path = tmp.name
        elif manual_path.strip():
            pdf_path = manual_path.strip()

        if not pdf_path and not user_text.strip():
            st.error("Lütfen bir PDF yükleyin, geçerli bir dosya yolu girin ya da metin girin.")
        else:
            with st.spinner("Özet çıkarılıyor, lütfen bekleyin..."):
                try:
                    if user_text.strip():
                        result = summarize_pdf_paragraphs(
                            pdf_path=None,
                            user_text=user_text.strip(),
                            model_name=model_name,
                            max_chunk_chars=max_chunk_chars,
                            two_stage_threshold=two_stage_threshold,
                        )
                    else:
                        result = summarize_pdf_paragraphs(
                            pdf_path=pdf_path,
                            model_name=model_name,
                            max_chunk_chars=max_chunk_chars,
                            two_stage_threshold=two_stage_threshold,
                        )

                    st.subheader("Nihai Özet")
                    st.write(result)

                    # İndirme tuşu
                    st.download_button(
                        label="Özeti İndir",
                        data=result,
                        file_name="ozet.txt",
                        mime="text/plain",
                    )
                except Exception as e:
                    st.error(f"Hata: {e}")
