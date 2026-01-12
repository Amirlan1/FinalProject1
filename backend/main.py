from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/analyze")
def analyze_text(text: str):
    words = text.split()
    word_count = len(words)
    unique_words = len(set(words))
    return {
        "total_words": word_count,
        "unique_words": unique_words,
        "words": words
    }
