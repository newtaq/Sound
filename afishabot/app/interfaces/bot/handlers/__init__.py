from .user import routers as user_routers
from .admin import routers as admin_routers

routers = user_routers + admin_routers

