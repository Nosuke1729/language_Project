from flask import Flask, request, render_template, session, redirect, url_for
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / 'prompt.txt'
HISTORY_FILE = BASE_DIR / 'history.json'
LOG_DIR = BASE_DIR / 'logs'
MODEL_NAME = os.getenv('MODEL_NAME', 'bigscience/bloomz-560m')
MAX_NEW_TOKENS = int(os.getenv('MAX_NEW_TOKENS', '80'))
MAX_TOTAL_TOKENS = int(os.getenv('MAX_TOTAL_TOKENS', '1800'))
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.6'))
TOP_P = float(os.getenv('TOP_P', '0.9'))

LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-before-production')

_tokenizer = None
_model = None


def load_initial_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding='utf-8').strip()
    return 'Ko koe he kaiāwhina atawhai e kōrero ana i te reo Māori. Whakahoki i ngā kōrero ki te reo Māori anake, kia poto, kia mārama hoki.'


def get_model():
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        _model.eval()
    return _tokenizer, _model


def save_history_entry(user_input: str, bot_response: str) -> None:
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            history = []
    history.append({
        'time': datetime.now().isoformat(timespec='seconds'),
        'user': user_input,
        'bot': bot_response,
    })
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')


def append_log(user_input: str, bot_response: str) -> None:
    now = datetime.now()
    log_path = LOG_DIR / f"chat_{now.strftime('%Y%m%d')}.txt"
    with log_path.open('a', encoding='utf-8') as f:
        f.write(f"[{now.strftime('%H:%M:%S')}] USER: {user_input}\n")
        f.write(f"[{now.strftime('%H:%M:%S')}] BOT: {bot_response}\n\n")


def format_history(session_history: list[dict]) -> str:
    parts = []
    for pair in session_history:
        parts.append(f"Pātai: {pair['user']}\nWhakautu: {pair['bot']}")
    return '\n'.join(parts)


def trim_history_to_fit(base_prompt: str, history_text: str, user_input: str, tokenizer) -> str:
    lines = history_text.splitlines()
    while True:
        prompt = f"{base_prompt}\n{history_text}\nPātai: {user_input}\nWhakautu:"
        tokenized = tokenizer(prompt, return_tensors='pt')
        if tokenized.input_ids.shape[1] + MAX_NEW_TOKENS <= MAX_TOTAL_TOKENS:
            return history_text
        if len(lines) <= 2:
            return ''
        lines = lines[2:]
        history_text = '\n'.join(lines)


def clean_response(decoded: str) -> str:
    if 'Whakautu:' in decoded:
        decoded = decoded.split('Whakautu:')[-1]
    for marker in ['Pātai:', 'User:', 'AI:']:
        if marker in decoded:
            decoded = decoded.split(marker)[0]
    text = decoded.strip()
    return text or 'Aroha mai, kāore au i whai whakautu pai i tēnei wā.'


def generate_reply(user_input: str, session_history: list[dict]) -> str:
    tokenizer, model = get_model()
    base_prompt = load_initial_prompt()
    history_text = trim_history_to_fit(base_prompt, format_history(session_history), user_input, tokenizer)
    prompt = f"{base_prompt}\n{history_text}\nPātai: {user_input}\nWhakautu:"
    tokenized = tokenizer(prompt, return_tensors='pt')

    with torch.no_grad():
        outputs = model.generate(
            **tokenized,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return clean_response(decoded)


@app.route('/', methods=['GET', 'POST'])
def index():
    if 'session_history' not in session:
        session['session_history'] = []

    error = None
    if request.method == 'POST':
        user_input = request.form.get('user_input', '').strip()
        if user_input:
            try:
                bot_response = generate_reply(user_input, session['session_history'])
                history = session['session_history']
                history.append({'user': user_input, 'bot': bot_response})
                session['session_history'] = history
                session.modified = True
                save_history_entry(user_input, bot_response)
                append_log(user_input, bot_response)
            except Exception as e:
                error = f'Error: {e}'

    return render_template('index.html', session_history=session.get('session_history', []), error=error)


@app.post('/reset')
def reset():
    session.pop('session_history', None)
    return redirect(url_for('index'))


@app.get('/health')
def health():
    return {'status': 'ok', 'model': MODEL_NAME}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
