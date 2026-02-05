import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import fitz  # PyMuPDF
from PIL import Image

# --- CONFIG PAGE ---
st.set_page_config(page_title="Expense AI", page_icon="🧾", layout="wide")

st.title("☁️ Extracteur de Frais (Web Version)")
st.markdown("Extrais les données de tes factures (PDF/IMG) vers Excel via Gemini Flash.")

# --- GESTION DES SECRETS (CLÉ API) ---
# L'app cherche la clé dans les réglages sécurisés de Streamlit Cloud
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        status_msg = "✅ Mode Entreprise (Clé Sécurisée)"
    else:
        # Fallback : Si tu n'as pas configuré les secrets, l'utilisateur peut entrer la sienne
        api_key = st.sidebar.text_input("Clé API Gemini", type="password")
        status_msg = "⚠️ Mode Utilisateur (Clé requise)"
except FileNotFoundError:
    # Pour le test en local sans fichier secrets.toml
    api_key = st.sidebar.text_input("Clé API Gemini", type="password")
    status_msg = "⚠️ Mode Local"

with st.sidebar:
    st.info(status_msg)
    st.write("---")
    st.write("Ce service utilise Gemini 1.5 Flash.")

# --- FONCTIONS ---
def pdf_to_images(pdf_bytes):
    """Convertit PDF en liste d'images (1 image par page)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    return images

def analyze_image(image, key):
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Analyse ce document comptable.
    Renvoie UNIQUEMENT un JSON strict avec ces clés :
    {
        "date": "YYYY-MM-DD",
        "merchant": "Nom du vendeur",
        "category": "Catégorie (Transport, Resto, Hotel, Tech, Autre)",
        "amount": 0.00 (float),
        "currency": "Symbole (€, £, $)",
        "vat": 0.00,
        "description": "Courte description"
    }
    Si incertain, mets null.
    """
    try:
        response = model.generate_content([prompt, image])
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}

# --- UI PRINCIPALE ---
uploaded_files = st.file_uploader("Glisser-déposer les reçus", 
                                  type=['png', 'jpg', 'jpeg', 'pdf', 'webp'], 
                                  accept_multiple_files=True)

if st.button("Lancer l'analyse ⚡") and uploaded_files:
    if not api_key:
        st.error("Il manque une clé API Gemini pour continuer.")
        st.stop()
        
    results = []
    progress_bar = st.progress(0)
    
    for idx, file in enumerate(uploaded_files):
        try:
            # Gestion PDF (Multi-pages possible) vs Image simple
            images_to_process = []
            if file.type == "application/pdf":
                images_to_process = pdf_to_images(file.read())
            else:
                images_to_process = [Image.open(file)]
            
            # Traitement de chaque "page/image"
            for img in images_to_process:
                data = analyze_image(img, api_key)
                data['fichier_source'] = file.name
                results.append(data)
                
        except Exception as e:
            st.error(f"Erreur sur {file.name}: {e}")
        
        progress_bar.progress((idx + 1) / len(uploaded_files))

    # --- TABLEAU & EXPORT ---
    if results:
        st.success("Extraction terminée !")
        df = pd.DataFrame(results)
        
        # Colonnes propres
        target_cols = ["date", "merchant", "category", "amount", "currency", "vat", "description", "fichier_source"]
        final_cols = [c for c in target_cols if c in df.columns]
        df = df[final_cols]

        # Tableau éditable
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Export')
            worksheet = writer.sheets['Export']
            for i, col in enumerate(edited_df.columns):
                worksheet.set_column(i, i, 20)
                
        st.download_button(
            "📥 Télécharger Excel",
            data=buffer.getvalue(),
            file_name="export_frais.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )