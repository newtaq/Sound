import asyncio 

from aiogram import Bot, Dispatcher

from app.core.config.settings import settings 
from app.interfaces.bot import router

async def main():
    bot = Bot(token=settings.telegram_api.BOT_TOKEN)
    
    dp = Dispatcher()
    
    dp.include_router(router)
    
    await dp.start_polling(bot)
    
    
    
def run_bot():
    asyncio.run(main())
    
    
