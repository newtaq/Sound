from aiogram import Router 
from aiogram.types import Message
from aiogram.filters import Command


router = Router(name="start_router")


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Все работает!")
    
