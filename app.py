import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import fitz  # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Expense Extractor", page_icon="🧾", layout="wide")
st.title("🧾 Extracteur Robuste (Anti-Crash)")

# --- GESTION CLÉ API ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        status = "✅ Clé Secrets"
    else:
        api_key = st.sidebar.text_input("Clé API Gemini", type="password").strip()
        status = "⚠️ Clé Manuelle"
except:
    api_key = st.sidebar.text_input("Clé API Gemini", type="password").strip()
    status = "⚠️ Clé Manuelle"

st.sidebar.info(f"Status : {status}")

# --- FONCTIONS ---
def pdf_to_images(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    return images

def analyze_smart(image, key):
    genai.configure(api_key=key)
    
    # LISTE DE SECOURS : On essaie ces noms l'un après l'autre
    # Si le 1er plante (404), on prend le 2ème, etc.
    models_to_try = [
        'gemini-1.5-flash',          # Nom standard
        'gemini-1.5-flash-latest',   # Alias parfois requis
        'gemini-1.5-flash-001',      # Version numérotée (souvent la plus stable)
        'gemini-1.5-pro',            # Version Pro (plus lente mais puissante)
        'gemini-pro'                 # Vieux modèle (valeur sûre)
    ]
    
    prompt = """
    Analyse ce document comptable. Renvoie un JSON strict :
    {
        "date": "YYYY-MM-DD",
        "merchant": "Nom",
        "category": "Catégorie",
        "currency": "Symbole",
        "items": [
            {"description": "Nom produit", "quantity": 1, "price": 0.00}
        ]
    }
    Si items impossibles à distinguer, fais une ligne globale.
    """
    
    last_error = ""
    
    for model_name in models_to_try:
        try:
            # On tente le modèle
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, image])
            
            # Si on arrive ici, c'est que ça a marché !
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
            
        except Exception as e:
            # Si ça plante, on note l'erreur et on continue la boucle
            last_error = str(e)
            continue 

    # Si on sort de la boucle, c'est que TOUS les modèles ont échoué
    return {"error": f"Échec total. Dernier message: {last_error}"}

# --- UI ---
uploaded_files = st.file_uploader("Fichiers (PDF/IMG)", type=['png', 'jpg', 'pdf'], accept_multiple_files=True)

if st.button("Lancer") and uploaded_files:
    if not api_key:
        st.error("Clé manquante")
        st.stop()
        
    all_data = []
    bar = st.progress(0)
    
    for idx, file in enumerate(uploaded_files):
        try:
            images = pdf_to_images(file.read()) if file.type == "application/pdf" else [Image.open(file)]
            
            for img in images:
                data = analyze_smart(img, api_key) # On utilise la fonction intelligente
                
                if "error" in data:
                    st.error(f"Erreur sur {file.name}: {data['error']}")
                else:
                    # Traitement des données réussies
                    merchant = data.get("merchant", "")
                    date = data.get("date", "")
                    currency = data.get("currency", "")
                    category = data.get("category", "")
                    
                    if "items" in data and data["items"]:
                        for item in data["items"]:
                            all_data.append({
                                "Date": date, "Enseigne": merchant, "Catégorie": category,
                                "Description": item.get("description"), "Prix": item.get("price"),
                                "Devise": currency, "Fichier": file.name
                            })
                    else:
                        all_data.append({
                            "Date": date, "Enseigne": merchant, "Catégorie": category,
                            "Description": "Total", "Prix": 0,
                            "Devise": currency, "Fichier": file.name
                        })
        except Exception as e:
            st.error(f"Erreur fichier {file.name}: {str(e)}")
                    
        bar.progress((idx+1)/len(uploaded_files))
        
    if all_data:
        df = pd.DataFrame(all_data)
        st.success("Extraction réussie !")
        st.data_editor(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Export')
            worksheet = writer.sheets['Export']
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, 20)
                
        st.download_button("📥 Télécharger Excel", data=buffer.getvalue(), file_name="export_final.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")