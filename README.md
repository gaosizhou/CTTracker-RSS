# 内容追踪（CT）| 通用型学术与技术资源追踪管理工具

## 项目简介

内容追踪（CT）是一款**全场景、通用型学术与技术资源全生命周期追踪管理工具**，无任何领域限制，适用于计算机、理工科、人文社科、行业技术研究等所有方向。项目旨在解决科研、学习、技术研究过程中资源分散、前沿信息更新滞后、资料杂乱难以管理、学者动态难以持续追踪等行业痛点，一站式聚合多平台学术论文、技术教程、行业视频、学者最新成果，帮助用户高效搭建结构化个人知识库与前沿追踪体系。

本项目**所有代码、架构设计、功能逻辑、整体开发工作均由 Codex 独立完成**，为原创开源项目，具备完整、独立的自主知识产权。

## ✨ 核心功能

### 1. 全平台资源统一聚合管理

支持主流学术与技术内容平台数据整合，涵盖论文、技术视频、公开教程、学者动态等全类型资源。系统自动同步平台最新内容，统一格式展示标题、作者、发布时间、摘要、来源链接等关键信息，无需多平台反复切换检索，实现所有学习、科研资源集中管控。

### 2. 自定义多维度精细化管理

内置完善的筛选、分类、标签体系，支持按创作者、发布年份、来源平台、自定义标签、阅读状态、时间排序等多维度组合筛选。用户可自由创建任意领域主题标签，适配**所有专业、所有研究方向、所有技术领域**的资源分类需求，快速构建专属结构化知识体系。同时支持分页管理、批量操作、内容编辑、收藏关注等便捷功能，适配个人日常学习与深度科研场景。

### 3. 精准学者/创作者动态追踪

支持自定义关注领域学者、科研团队、技术创作者，系统自动同步其最新发布的论文、教程、研究成果与动态。可长期追踪目标团队的研究脉络、技术迭代与前沿突破，精准捕捉行业最新进展，彻底解决前沿信息滞后、成果遗漏的问题。

## 🎯 核心优势

- **全领域通用**：不局限于单一技术或科研方向，适配所有学科、所有技术赛道的资源管理与前沿追踪需求，通用性极强。

- **一站式闭环管理**：整合论文、视频、动态、学者追踪、标签分类、资源收藏全流程能力，实现从资源采集、整理、归档到追踪的完整闭环。

- **轻量化高效易用**：本地轻量Web服务部署，配置简单、启动快速，界面简洁清晰，支持中英文双语，适配国内外用户使用习惯。

- **高度自由可扩展**：架构灵活，支持后续新增平台数据源、新增分类规则与自定义功能，可根据个人或团队需求持续迭代优化。

## 🚀 适用场景

- 科研人员：追踪顶会顶刊论文、跟进领域大牛最新研究、整理文献资料、辅助论文写作与课题调研

- 技术开发者：跟进行业前沿技术、收纳优质教程视频、跟踪技术博主与官方团队动态

- 学生与学习者：系统化整理学习资源、分类沉淀知识、长期跟踪目标领域发展趋势

- 团队教研：统一归集领域资源、同步前沿动态、搭建团队公共知识库

## ⚠️ 版权与商用声明（必读）

1. 本项目**全程由 Codex 独立设计、架构、开发完成**，所有代码逻辑、架构方案、功能设计均为原创，知识产权归创作者所有。

2. **个人非开源、非商用场景可免费使用**。

3. **任何商业用途、二次商用、二次封装售卖、开源商用、企业内部商用部署、基于本项目二次开发用于商业产品**，均**必须提前与原作者沟通获得授权**。

4. 未经作者授权的一切商用、侵权二创、商业复刻、售卖行为，均属于**侵权行为**，作者将保留追究法律责任的权利。



# Content Tracker

A local FastAPI web app for tracking papers, videos, posts, and personally focused content.

## Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Features

- Papers from Google Scholar profiles.
- Videos from YouTube RSS feeds.
- Posts/tweets/short links by manual entry.
- Separate pages for Papers, Videos, Posts, Focus, Creators, and Tags.
- Shared focus toggle, reading state, notes, and tags across all content types.
- Reusable tags with dropdown checkbox selection.
- English/Chinese UI toggle.

Google Scholar may return 403 or captcha pages for automated requests. The app shows those errors instead of creating bad data.

## Database

Default database:

```text
rss_papers.db
```

Override:

```powershell
$env:DATABASE_URL = "sqlite:///my-content.db"
```

## Documentation

Full project documentation:

```text
docs/PROJECT.md
```

## Tests

```powershell
python -m pytest
```
