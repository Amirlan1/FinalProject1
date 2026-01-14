from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Amirlan Pro max"}

@app.get("/analyze")
def analyze_text(text: str):
    # Разделяем текст на слова
    words = text.split()
    
    # Подсчитываем количество слов
    word_count = len(words)
    
    # Подсчитываем количество уникальных слов
    unique_words = len(set(words))
    
    # Подсчитываем количество символов
    char_count = len(text)
    
    # Подсчитываем количество строк
    line_count = text.count("\n") + 1  # Добавляем 1, потому что последняя строка не заканчивается \n
    
    return {
        "total_words": word_count,
        "unique_words": unique_words,
        "char_count": char_count,
        "line_count": line_count,
        "words": words
    }
