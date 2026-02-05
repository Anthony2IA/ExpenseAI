import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import fitz  # PyMuPDF
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="Expense Extractor 2.5", page_icon="⚡", layout="wide")
st.title("⚡ Extracteur de Frais (Gemini 2.5 Powered)")

# --- CLÉ API ---
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

def analyze_expense(image, key):
    genai.configure(api_key=key)
    
    # --- LA CORRECTION EST ICI ---
    # On utilise le nom exact que tu as trouvé dans la liste
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = """
    Agis comme un expert comptable. Analyse ce document.
    Extrais les lignes d'achat une par une.
    
    Renvoie UNIQUEMENT ce JSON strict :
    {
        "date": "YYYY-MM-DD",
        "merchant": "Nom du vendeur",
        "currency": "Symbole (€, $, etc)",
        "items": [
            {
                "description": "Nom du produit/service",
                "quantity": 1,
                "price": 0.00 (Prix total de la ligne)
            }
        ]
    }
    Si le document n'a pas de détails (ex: ticket de taxi), crée un seul item "Trajet" ou "Service".
    """
    
    try:
        response = model.generate_content([prompt, image])
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}

# --- UI PRINCIPALE ---
uploaded_files = st.file_uploader("Dépose tes fichiers", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)

if st.button("Lancer l'analyse 🚀") and uploaded_files:
    if not api_key:
        st.error("Clé manquante.")
        st.stop()
        
    all_rows = []
    bar = st.progress(0)
    
    for idx, file in enumerate(uploaded_files):
        try:
            # Conversion PDF ou Image directe
            images = pdf_to_images(file.read()) if file.type == "application/pdf" else [Image.open(file)]
            
            for img in images:
                data = analyze_expense(img, api_key)
                
                if "error" in data:
                    st.error(f"Erreur sur {file.name}: {data['error']}")
                else:
                    # Aplatissement pour Excel
                    merchant = data.get("merchant", "")
                    date = data.get("date", "")
                    currency = data.get("currency", "")
                    
                    if "items" in data and data["items"]:
                        for item in data["items"]:
                            all_rows.append({
                                "Date": date,
                                "Enseigne": merchant,
                                "Description": item.get("description"),
                                "Quantité": item.get("quantity"),
                                "Montant": item.get("price"),
                                "Devise": currency,
                                "Fichier": file.name
                            })
                    else:
                        # Fallback au cas où l'IA renvoie une liste vide
                        all_rows.append({
                            "Date": date, "Enseigne": merchant, "Description": "Total", 
                            "Quantité": 1, "Montant": 0, "Devise": currency, "Fichier": file.name
                        })
                        
        except Exception as e:
            st.error(f"Crash fichier {file.name}: {e}")
            
        bar.progress((idx + 1) / len(uploaded_files))

    if all_rows:
        df = pd.DataFrame(all_rows)
        st.success("Terminé !")
        
        # Tableau éditable
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        # Export Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Export')
            worksheet = writer.sheets['Export']
            for i, col in enumerate(edited_df.columns):
                worksheet.set_column(i, i, 20)
                
        st.download_button("📥 Télécharger Excel", buffer.getvalue(), "frais_detailles.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")