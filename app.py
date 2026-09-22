"""应用入口，仅负责组件装配和服务启动。"""

from nicegui import app, ui

from modules.application import configure_application
from settings import APP, PROJECT_ROOT, SECRETS

configure_application(app, PROJECT_ROOT)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(**APP.ui_run_kwargs(), storage_secret=SECRETS.storage_secret)
