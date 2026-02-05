import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import fitz  # PyMuPDF
from PIL import Image

# --- CONFIGURATION ---
st.set_page_config(page_title="Universal Extractor", page_icon="📊", layout="wide")
st.title("📊 Extracteur Universel (Ligne par Ligne)")

# --- GESTION CLÉ API ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        status = "✅ Clé Sécurisée"
    else:
        api_key = st.sidebar.text_input("Clé API Gemini", type="password")
        status = "⚠️ Clé Manuelle"
except:
    api_key = st.sidebar.text_input("Clé API Gemini", type="password")
    status = "⚠️ Clé Manuelle"

with st.sidebar:
    st.info(f"Status : {status}")
    st.markdown("---")
    st.write("Cet outil détecte automatiquement s'il faut extraire une liste de produits ou juste un total.")

# --- FONCTIONS ---
def pdf_to_images(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    return images

def analyze_universal(image, key):
    genai.configure(api_key=key)
    # Le modèle Pro est parfois meilleur pour les longs tableaux, mais Flash est plus rapide.
    # On reste sur Flash pour la gratuité/vitesse, il est très capable.
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # --- PROMPT UNIVERSEL ---
    prompt = """
    Tu es un assistant comptable automatisé. Ton but est de structurer les données de ce document (facture, reçu, ticket).
    
    Règles d'extraction :
    1. Identifie les métadonnées globales (Date, Vendeur, Devise).
    2. Identifie le CONTENU de l'achat :
       - CAS A (Ticket détaillé, Facture matériel, Supermarché, Resto avec menu) : Extrais CHAQUE ligne de produit/service individuellement.
       - CAS B (Ticket global, Taxi, Petit reçu CB) : Si aucun détail n'est listé, crée une seule ligne résumant le service (ex: "Trajet Uber", "Repas", "Divers").
    
    Format de sortie attendu (JSON STRICT UNIQUEMENT) :
    {
        "date": "YYYY-MM-DD",
        "merchant": "Nom de l'entreprise",
        "currency": "Symbole (€, £, $)",
        "category": "Catégorie suggérée (Transport, Alimentation, Tech, Services, etc.)",
        "items": [
            {
                "description": "Nom précis du produit ou service sur la ligne",
                "quantity": 1 (par défaut 1 si non précisé),
                "price": 0.00 (Prix total de la ligne TTC)
            }
        ]
    }
    
    Attention :
    - Ne pas inventer de données. Si une info manque, mets null ou une chaine vide.
    - Les frais de service, livraison ou pourboires doivent être des lignes ("items") séparées.
    - Le total des prix des "items" doit correspondre au total du document.
    """
    
    try:
        response = model.generate_content([prompt, image])
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}

# --- UI PRINCIPALE ---
uploaded_files = st.file_uploader("Dépose tes factures / reçus", 
                                  type=['png', 'jpg', 'jpeg', 'pdf', 'webp'], 
                                  accept_multiple_files=True)

if st.button("Lancer l'analyse 🚀") and uploaded_files:
    if not api_key:
        st.error("Il manque la clé API !")
        st.stop()
        
    all_extracted_rows = []
    progress_bar = st.progress(0)
    
    for idx, file in enumerate(uploaded_files):
        try:
            # 1. Préparation des images
            images_to_process = []
            if file.type == "application/pdf":
                images_to_process = pdf_to_images(file.read())
            else:
                images_to_process = [Image.open(file)]
            
            # 2. Boucle sur chaque page/image
            for img in images_to_process:
                data = analyze_universal(img, api_key)
                
                # Vérification d'erreur API
                if "error" in data:
                    st.warning(f"Erreur sur {file.name} : {data['error']}")
                    continue
                
                # 3. Aplatissement du JSON vers Excel
                meta_date = data.get("date")
                meta_merchant = data.get("merchant")
                meta_currency = data.get("currency")
                meta_category = data.get("category")
                
                # Si l'IA trouve des items, on crée une ligne par item
                if "items" in data and isinstance(data["items"], list) and len(data["items"]) > 0:
                    for item in data["items"]:
                        new_row = {
                            "Date": meta_date,
                            "Vendeur": meta_merchant,
                            "Catégorie": meta_category,
                            "Description": item.get("description", "Non spécifié"),
                            "Quantité": item.get("quantity", 1),
                            "Montant": item.get("price", 0.0),
                            "Devise": meta_currency,
                            "Fichier Source": file.name
                        }
                        all_extracted_rows.append(new_row)
                else:
                    # Fallback de sécurité : Si l'IA renvoie une structure vide ou bizarre
                    # On essaie de récupérer au moins un total global s'il existe ailleurs dans le JSON
                    # (Dépend de la flexibilité du modèle, mais ici on sécurise le code Python)
                    new_row = {
                        "Date": meta_date,
                        "Vendeur": meta_merchant,
                        "Catégorie": meta_category,
                        "Description": "Dépense globale (Détail non extrait)",
                        "Quantité": 1,
                        "Montant": 0.0, # À corriger manuellement si échec
                        "Devise": meta_currency,
                        "Fichier Source": file.name
                    }
                    all_extracted_rows.append(new_row)

        except Exception as e:
            st.error(f"Crash critique sur {file.name}: {e}")
        
        progress_bar.progress((idx + 1) / len(uploaded_files))

    # --- AFFICHAGE & EXPORT ---
    if all_extracted_rows:
        df = pd.DataFrame(all_extracted_rows)
        
        st.success(f"Terminé ! {len(df)} lignes générées.")
        st.info("Tu peux modifier les descriptions ou montants directement dans le tableau avant d'exporter.")
        
        # Tableau interactif
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        # Génération Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Export_Frais')
            
            # Formatage automatique des colonnes
            worksheet = writer.sheets['Export_Frais']
            for i, col in enumerate(edited_df.columns):
                worksheet.set_column(i, i, 20)
                
        st.download_button(
            label="📥 Télécharger le fichier Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="ma_compta_detaillee.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Aucune donnée n'a pu être extraite.")