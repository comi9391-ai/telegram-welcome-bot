from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8209007476:AAGr6oisq5RQrDWXSDLJv1JfaSUcJ-FiDa0"
PHOTO_FILE_ID = "AgACAgUAAxkBAAMFaRa9j8eibKhqAg5ICTmqU9fGDaAAApULaxvQqLhUAk7xQFgkRGUBAAMCAAN5AAM2BA"


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        chat_title = update.effective_chat.title
        first_name = member.first_name

        caption = (
            f"{first_name}님\n"
            f"{chat_title}에 오신 걸 환영합니다 🎉\n\n"
            "상단 공지 먼저 한 번 확인해 주세요.\n"
            "궁금한 점 있으면 편하게 질문 남겨주시면 됩니다."
        )

        await update.message.reply_photo(
            photo=PHOTO_FILE_ID,
            caption=caption
        )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome,
        )
    )

    print("환영봇 가동 중...")
    app.run_polling()


if __name__ == "__main__":
    main()
