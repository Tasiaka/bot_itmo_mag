# tg_bot.py
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from bot_core import BotSession

load_dotenv()  # локальная загрузка .env
TOKEN = os.getenv("TELEGRAM_TOKEN")  # НЕ клади токен в репозиторий!
if not TOKEN:
    raise RuntimeError("Переменная окружения TELEGRAM_TOKEN не задана")

session = BotSession()

INTRO = (
    "👋 Привет! Я бот-помощник для абитуриентов магистратуры ИТМО.\n\n"
    "Я помогу быстро разобраться с учебными планами двух программ:\n"
    "• AI — «Искусственный интеллект»\n"
    "• AI Product — «Управление ИИ‑продуктами»\n\n"
    "Что я умею:\n"
    "• Показать доступные программы: /programs\n"
    "• Переключить программу: /ai или /aiproduct\n"
    "• Показать обязательные / выборные курсы по семестру\n"
    "• Рассказать про практику, ГИА и Soft Skills\n"
    "• Найти курс по ключевым словам\n\n"
    "Как со мной говорить (примеры):\n"
    "• «обязательные дисциплины 1 семестр»\n"
    "• «выборные 2 семестр»\n"
    "• «практика» / «ГИА» / «soft skills»\n"
    "• «переключись на ai product»\n"
    "• «найди курс: глубокое обучение»\n\n"
    "Подсказка: сначала выбери программу (/ai или /aiproduct), потом задавай вопросы 😉"
)

HELP = (
    "ℹ️ Как пользоваться ботом\n\n"
    "Команды:\n"
    "• /programs — показать доступные программы\n"
    "• /ai — переключиться на «Искусственный интеллект»\n"
    "• /aiproduct — переключиться на «Управление ИИ‑продуктами»\n"
    "• /help — краткая памятка\n\n"
    "Примеры запросов:\n"
    "• обязательные дисциплины 1 семестр\n"
    "• выборные 2 семестр\n"
    "• практика\n"
    "• гиа\n"
    "• soft skills\n"
    "• найди курс: глубокое обучение\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # слегка хак: дернём встроенный хелпер из bot_core через текстовый интент
    ans = session.handle("программы")
    await update.message.reply_text(ans)

async def set_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session.program = "ai"
    await update.message.reply_text("✅ Ок, работаем с программой: «Искусственный интеллект».")

async def set_ai_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session.program = "ai_product"
    await update.message.reply_text("✅ Ок, работаем с программой: «Учебный план ОП Управление ИИ‑продуктами/AI Product».")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    try:
        answer = session.handle(text)
    except Exception as e:
        answer = f"Упс, что-то пошло не так: {e}\nПопробуй ещё раз или напиши /help"
    await update.message.reply_text(answer)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("programs", programs))
    app.add_handler(CommandHandler("ai", set_ai))
    app.add_handler(CommandHandler("aiproduct", set_ai_product))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
