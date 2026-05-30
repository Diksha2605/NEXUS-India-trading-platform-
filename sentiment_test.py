from transformers import pipeline

sentiment = pipeline("text-classification", model="ProsusAI/finbert")

headlines = [
    "Reliance Industries reports record profits",
    "Sensex crashes 800 points amid FII selloff",
    "Market remains volatile ahead of RBI policy decision",
    "Nifty consolidates, no clear direction expected",
    "FII buying surges, bulls take control of Dalal Street"
]

for headline in headlines:
    result = sentiment(headline)[0]
    label = result['label'].upper()
    confidence = round(result['score'] * 100, 1)
    print(f"{headline}")
    print(f"→ {label} ({confidence}%)")
    print()