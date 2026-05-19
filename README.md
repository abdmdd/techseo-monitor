\# TechSEO Monitor



Автоматизированная система технического SEO-мониторинга сайтов.



\## Возможности системы



\- Ежемесячный SEO-аудит

\- Ежеквартальный расширенный аудит

\- Анализ sitemap.xml

\- Проверка robots.txt

\- Анализ meta-тегов

\- Проверка canonical

\- Анализ пагинации

\- Проверка битых ссылок

\- Проверка редиректов

\- AI SEO-рекомендации

\- История аудитов

\- PDF-отчёты

\- FastAPI API

\- Dashboard аналитики



\---



\# Технологии



\## Backend

\- Python

\- FastAPI

\- SQLite

\- Streamlit



\## SEO crawler

\- Requests

\- BeautifulSoup

\- Playwright



\## Data

\- Pandas



\## Reports

\- ReportLab



\---



\# Архитектура проекта



```text

app.py

api/

components/

config/

crawlers/

database/

integrations/

services/

tasks/

views/

```



\---



\# Основные модули



\## Streamlit UI

Интерфейс системы:

\- Dashboard

\- Аудиты

\- История

\- PDF

\- Генерация meta-тегов



\## FastAPI API

REST API:

\- /health

\- /audit/monthly

\- /audit/quarterly



\## SEO Crawler

Проверяет:

\- title

\- description

\- canonical

\- H1

\- viewport

\- alt

\- robots.txt

\- sitemap.xml

\- redirects

\- duplicates

\- pagination

\- broken links



\## AI SEO Module

Rule-based AI recommendations engine для генерации SEO-рекомендаций.



\---



\# Запуск проекта



\## 1. Создание venv



```bash

python -m venv venv

```



\## 2. Активация



\### Windows



```bash

venv\\Scripts\\activate

```



\## 3. Установка зависимостей



```bash

pip install -r requirements.txt

```



\## 4. Установка Playwright



```bash

playwright install chromium

```



\## 5. Запуск Streamlit



```bash

streamlit run app.py

```



\## 6. Запуск FastAPI



```bash

uvicorn api.main:app --reload

```



\---



\# API



\## Health check



```http

GET /health

```



\## Monthly audit



```http

POST /audit/monthly

```



\## Quarterly audit



```http

POST /audit/quarterly

```



\---



\# AI-функции



Система генерирует:

\- SEO risk analysis

\- AI recommendations

\- SEO score summary

\- Technical recommendations



\---



\# Статус проекта



MVP / Diploma Project



\---



\# Автор



Madina

