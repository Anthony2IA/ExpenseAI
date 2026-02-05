import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Spy", page_icon="🕵️")
st.title("🕵️ Liste Officielle des Modèles")

# 1. On récupère la clé
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("Clé chargée depuis les Secrets")
    else:
        api_key = st.text_input("Colle ta clé API", type="password").strip()
except:
    api_key = st.text_input("Colle ta clé API", type="password").strip()

# 2. On appelle la fonction ListModels
if st.button("Lister les modèles maintenant") and api_key:
    try:
        genai.configure(api_key=api_key)
        
        st.write("---")
        st.subheader("Voici ce que Google autorise pour ta clé :")
        
        found_any = False
        # C'est la commande exacte demandée par le message d'erreur
        for m in genai.list_models():
            # On affiche tout, brut de décoffrage
            st.code(f"Nom technique : {m.name}")
            st.caption(f"Description : {m.description}")
            st.write("---")
            found_any = True
            
        if not found_any:
            st.error("La commande a marché mais la liste est vide. Ta clé n'a accès à rien ?")
            
    except Exception as e:
        st.error(f"Erreur fatale : {e}")