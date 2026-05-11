import streamlit as st
from transformers import pipeline

@st.cache_resource
def load_model():
    return pipeline("text-classification", model="ProsusAI/finbert")

sentiment = load_model()

st.title("NXIO — News Sentiment Signal")
st.subheader("Powered by FinBERT")

headline = st.text_input("Enter a market headline:")
lstm_signal = st.selectbox("Your LSTM Signal:", ["BUY", "SELL", "HOLD"])

if st.button("Analyse"):
    if headline:
        result = sentiment(headline)[0]
        label = result['label'].upper()
        confidence = round(result['score'] * 100, 1)

        st.write(f"**Sentiment:** {label} ({confidence}%)")

        if lstm_signal == "BUY" and label == "POSITIVE":
            st.success("STRONG BUY ✅")
        elif lstm_signal == "BUY" and label == "NEGATIVE":
            st.warning("WEAK BUY ⚠️ — news conflicts with signal")
        elif lstm_signal == "SELL" and label == "NEGATIVE":
            st.error("STRONG SELL 🔴")
        else:
            st.info("HOLD 🟡")
    else:
        st.write("Please enter a headline.")