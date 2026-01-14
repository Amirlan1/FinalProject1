from fastapi import FastAPI, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

app = FastAPI()

# Инициализация шаблонов Jinja2
templates = Jinja2Templates(directory="templates")

# Главная страница с формой для ввода текста
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "text": ""})

# Функция для анализа текста
@app.post("/analyze", response_class=HTMLResponse)
async def analyze_text(request: Request, text: str = Form(...)):
    words = text.split()
    word_count = len(words)
    unique_words = len(set(words))
    char_count = len(text)
    line_count = text.count("\n") + 1

    vowels = "aeiouAEIOU"
    consonants = "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ"
    vowel_count = sum(1 for c in text if c in vowels)
    consonant_count = sum(1 for c in text if c in consonants)
    
    word_frequency = {word: words.count(word) for word in set(words)}
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "word_count": word_count,
        "unique_words": unique_words,
        "char_count": char_count,
        "line_count": line_count,
        "vowel_count": vowel_count,
        "consonant_count": consonant_count,
        "word_frequency": word_frequency,
        "text": text
    })
