import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time
import fitz  # PyMuPDF
from PIL import Image

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Expense AI - Universal", page_icon="🌍", layout="wide")
st.title("🌍 Extracteur Universel (Toutes Langues → Français)")

# --- GESTION DE LA CLÉ API ---
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
st.sidebar.warning("🛡️ Mode Anti-Quota : Pause de 15s activée entre les fichiers.")

# --- FONCTIONS UTILITAIRES ---
def pdf_to_images(pdf_bytes):
    """Convertit chaque page d'un PDF en image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    return images

def analyze_universal(image, key):
    """Le Cerveau : Analyse n'importe quel document et le normalise."""
    genai.configure(api_key=key)
    # On garde le 2.5 Flash car c'est lui qui a débloqué la situation
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # --- PROMPT UNIVERSEL ---
    prompt = """
    Tu es un auditeur comptable international expert.
    Ta mission : Analyser ce document (ticket, facture, reçu) quelle que soit sa langue d'origine (Grec, Chinois, Anglais, Allemand, etc.).

    RÈGLES DE TRAITEMENT STRICTES :
    1. **DÉTECTION DE DATE** : Trouve la date réelle de la TRANSACTION (achat). Ignore les dates d'impression ou d'export (souvent la date du jour). Cherche le format YYYY-MM-DD.
    2. **TRADUCTION** : Traduis IMPÉRATIVEMENT toutes les descriptions en FRANÇAIS. 
       - Ex: "Pita Gyros" (Grec) -> "Sandwich Gyros"
       - Ex: "Subway Ticket" (Anglais) -> "Ticket de métro"
    3. **NETTOYAGE** : Ne garde que les lignes payantes. Supprime les lignes "Total", "TVA", "Service" ou "Livraison" si elles sont à 0€.
    4. **DEVISE** : Identifie le symbole monétaire du document (€, $, £, CNY, JPY...).

    Structure de sortie (JSON UNIQUEMENT) :
    {
        "date": "YYYY-MM-DD",
        "merchant": "Nom du commerce (Garde le nom original)",
        "currency": "Symbole",
        "items": [
            {
                "description": "Description traduite en Français",
                "quantity": 1,
                "price": 0.00
            }
        ]
    }
    """
    
    try:
        response = model.generate_content([prompt, image])
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}

# --- INTERFACE UTILISATEUR ---
uploaded_files = st.file_uploader("Dépose tes fichiers (Monde entier acceptés)", 
                                  type=['png', 'jpg', 'jpeg', 'pdf'], 
                                  accept_multiple_files=True)

if st.button("Lancer l'analyse Monde 🌍") and uploaded_files:
    if not api_key:
        st.error("Il manque la clé API !")
        st.stop()
        
    all_extracted_rows = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file in enumerate(uploaded_files):
        try:
            status_text.text(f"🌍 Analyse de {file.name} en cours...")
            
            # Préparation (PDF ou Image)
            images_to_process = []
            if file.type == "application/pdf":
                images_to_process = pdf_to_images(file.read())
            else:
                images_to_process = [Image.open(file)]
            
            # Analyse de chaque page
            for img in images_to_process:
                data = analyze_universal(img, api_key)
                
                if "error" in data:
                    st.error(f"Erreur sur {file.name}: {data['error']}")
                else:
                    # Extraction des métadonnées
                    merchant = data.get("merchant", "Inconnu")
                    date = data.get("date", "")
                    currency = data.get("currency", "")
                    
                    # Traitement des items
                    if "items" in data and data["items"]:
                        for item in data["items"]:
                            # Filtre : on ne garde que ce qui coûte de l'argent
                            if item.get("price", 0) > 0:
                                all_extracted_rows.append({
                                    "Date Transaction": date,
                                    "Enseigne": merchant,
                                    "Description (FR)": item.get("description"),
                                    "Quantité": item.get("quantity", 1),
                                    "Montant": item.get("price", 0),
                                    "Devise": currency,
                                    "Fichier Source": file.name
                                })
                    else:
                        # Cas de secours (Ticket de taxi sans détail)
                        all_extracted_rows.append({
                            "Date Transaction": date,
                            "Enseigne": merchant,
                            "Description (FR)": "Dépense globale (Sans détail)",
                            "Quantité": 1,
                            "Montant": 0,
                            "Devise": currency,
                            "Fichier Source": file.name
                        })
            
            # --- PAUSE ANTI-QUOTA (Vital pour le compte gratuit) ---
            if idx < len(uploaded_files) - 1:
                for i in range(15, 0, -1):
                    status_text.warning(f"✅ {file.name} traité. Pause de sécurité Google : {i}s...")
                    time.sleep(1)
                
        except Exception as e:
            st.error(f"Problème critique sur {file.name}: {e}")
        
        progress_bar.progress((idx + 1) / len(uploaded_files))

    # --- RÉSULTATS ---
    status_text.success("Traitement terminé ! Tout est traduit.")

    if all_extracted_rows:
        df = pd.DataFrame(all_extracted_rows)
        
        # Affichage du tableau
        st.markdown("### 📝 Vérification des données (Traduites)")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        # Export Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Export_Frais')
            # Auto-ajustement des colonnes
            worksheet = writer.sheets['Export_Frais']
            for i, col in enumerate(edited_df.columns):
                worksheet.set_column(i, i, 25)
                
        st.download_button(
            label="📥 Télécharger l'Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="frais_international_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )