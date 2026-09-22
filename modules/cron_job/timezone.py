"""装配层：统一定时任务时区。"""

from zoneinfo import ZoneInfo

from settings import APP

scheduler_tz = ZoneInfo(APP.timezone)
