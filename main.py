from nicegui import ui, run
from init_db import engine, Base, create_db_and_tables
from views.login import login_view

@ui.page('/')
def main():
    login_view()

ui.run()