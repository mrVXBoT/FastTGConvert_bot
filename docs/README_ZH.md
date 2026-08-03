# 📘 FastTGConvert — 完整技术与生产文档 (中文)

欢迎阅读 **FastTGConvert** 项目的技术文档。FastTGConvert 是一个高性能、异步的 Telegram Session 管理与格式转换平台。

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [核心功能说明](#3-核心功能说明)
4. [数据库设计](#4-数据库设计)
5. [安全与隐私](#5-安全与隐私)
6. [部署指南](#6-部署指南)
7. [测试与质量控制](#7-测试与质量控制)

---

## 1. 项目概述

FastTGConvert 基于 Python (Aiogram 3.x, Telethon, SQLAlchemy 2.0) 构建，提供安全的 Telegram Session 格式转换、账号健康审计、两步验证 (2FA) 管理及广播推送功能。

---

## 2. 核心功能

- **Session 格式转换**: 双向转换 `.session` ↔ `TData` (Telegram Desktop 格式)，导出 `.json` 和 `.txt`。
- **账号审计工具**: 账号注册时长计算、@SpamBot 封禁状态检测、联系人清理、双重验证 (2FA) 密码修改/重置/禁用。
- **内联键盘管理后台**: 基于 RBAC (OWNER, SUPER_ADMIN, ADMIN, SUPPORT) 的管理面板，支持用户搜索、封禁、VIP 订阅管理及广播引擎。

---

## 3. 快速部署

```bash
git clone https://github.com/mrVXBoT/FastTGConvert_bot.git
cd FastTGConvert_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m app
```

---

## 4. 自动化测试

- **已通过测试数**: 296 (`296 passed`)
- **运行测试命令**: `.venv/bin/pytest`
