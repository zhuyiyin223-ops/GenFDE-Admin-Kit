"""装配层：进程内定时任务闭集注册。

对照 ``routes.py``。平台运维任务（库备份）实现放本包；业务任务只注册并调用
所属域 service，不纳入同一事务、不依赖其 page。不要为此新建业务域。
生命周期负责启停调度器。
"""

from .cron_jobs import scheduler

__all__ = ["scheduler"]
