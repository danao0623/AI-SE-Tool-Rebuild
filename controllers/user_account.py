from models.user_account import UserAccount
from controllers.base import BaseController

class UserAccountController(BaseController):
    model = UserAccount  # 指定這個 Controller 使用的 model 是 UserAccount