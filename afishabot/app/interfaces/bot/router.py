from aiogram import Router

from app.interfaces.bot.handlers import routers as handlers_routers 


router = Router(name="main_router")

for r in handlers_routers:
    router.include_router(r)    

