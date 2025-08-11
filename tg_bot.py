# tg_bot.py
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from bot_core import BotSession, program_title

logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Переменная окружения TELEGRAM_TOKEN не задана")

# Сессии на пользователя (каждому — свой BotSession)
SESSIONS = {}

def session_for(update: Update) -> BotSession:
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in SESSIONS:
        SESSIONS[uid] = BotSession()
    return SESSIONS[uid]

INTRO = (
    "👋 Привет! Я помогу выбрать программу и спланировать учёбу.\n"
    "Выбери программу: /ai или /aiproduct\n"
    "Задай бэкграунд (теги), затем попроси рекомендации.\n\n"
    "Примеры:\n"
    "• теги: ml, nlp, python, sys\n"
    "• рекомендации 2 семестр\n"
    "• обязательные дисциплины 1 семестр\n"
    "• выборные 2 семестр\n"
    "• практика / гиа / soft skills\n"
    "• найди курс: глубокое обучение\n"
    "• сравни программы\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO)

async def programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    ans = s.handle("программы")
    await update.message.reply_text(ans)

async def set_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    s.program = "ai"
    await update.message.reply_text(f"✅ Ок, работаем с программой: «{program_title('ai')}».")
    
async def set_ai_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    s.program = "ai_product"
    await update.message.reply_text(f"✅ Ок, работаем с программой: «{program_title('ai_product')}».")

async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    await update.message.reply_text(s.handle("сравни программы"))

async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    text = " ".join(context.args) if context.args else ""
    # позволим /recommend 2  => семестр 2
    if text and text.isdigit():
        text = f"рекомендации {text} семестр"
    else:
        text = "рекомендации " + text
    await update.message.reply_text(s.handle(text))

async def set_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    # пример: /tags ml, nlp, python
    raw = " ".join(context.args) if context.args else ""
    if not raw:
        await update.message.reply_text("Напиши теги через пробел или запятую. Пример: /tags ml nlp python")
        return
    await update.message.reply_text(s.handle(f"теги: {raw}"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = session_for(update)
    text = update.message.text or ""
    try:
        answer = s.handle(text)
    except Exception as e:
        logging.exception("TG error")
        answer = f"Упс, что-то пошло не так: {e}\nПопробуй ещё раз или напиши /help"
    await update.message.reply_text(answer)

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.exception("Unhandled error: %s", context.error)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("programs", programs))
    app.add_handler(CommandHandler("ai", set_ai))
    app.add_handler(CommandHandler("aiproduct", set_ai_product))
    app.add_handler(CommandHandler("compare", compare))
    app.add_handler(CommandHandler("recommend", recommend))
    app.add_handler(CommandHandler("tags", set_tags))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
