# GenFDE-Admin-Kit

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![NiceGUI](https://img.shields.io/badge/NiceGUI-3.x-009485)](https://nicegui.io/)
[![Tortoise ORM](https://img.shields.io/badge/Tortoise--ORM-1.x-1C7C54)](https://tortoise.github.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

**基于 NiceGUI 构建，FDE 快速交付、生产环境可用的小而美全栈项目骨架。 本项目集成了现代 Web
开发所需的核心配置与常用库，帮你省去数据库连接、身份认证、RBAC权限、异步任务、开放API、操作审计、定时任务、自动化部署等繁琐的初始化工作。真正做到克隆即用，专注于你的业务逻辑。**

## AI-Native 核心优势

- 纯 Python 前后端一体化，单一上下文，无需前后端联调，消除 AI 的“精神分裂”
- 类型提示一穿到底：AI 的“自动纠错导航”
- 组件即函数：消除了复杂的“生命周期”和“打包构建”
- AGENTS.md 工程级约束，与 ruff 静态强管制

## 核心功能

- 清晰合理、可复用的项目结构
- PWA 后台模版
- RBAC 权限
- 列表工作台
- 操作审计
- 开放接口
- 后台、定时任务
- 自动化 CI/CD
- 站内消息
- 精美主题

## 项目结构详见 [AGENTS.md](AGENTS.md)

## 启动

```bash
pip install requirements.txt
cp .env.example .env          # 自行修改
source .venv/bin/activate
python app.py                 # 默认 http://127.0.0.1:8899
```

## 迁移

```bash
tortoise makemigrations         
tortoise migrate
```
