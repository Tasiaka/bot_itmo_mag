#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скачивает страницы магистратур ИТМО и вытаскивает учебный план в упрощённый JSON,
совместимый с нашим bot_core.py (ai_plan.json, ai_product_plan.json).

Быстрый запуск:
  python scraper_itmo.py --out data
"""

import re
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
from slugify import slugify

HDRS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

URLS = {
    "ai": "https://abit.itmo.ru/program/master/ai",
    "ai_product": "https://abit.itmo.ru/program/master/ai_product",
}

# ---------- Утилиты ----------

def fetch(url: str, retries: int = 3, sleep: float = 1.0) -> str:
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=HDRS, timeout=20)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last = e
            time.sleep(sleep * (i + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")

def clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip())

def num_or_none(x: Optional[str]) -> Optional[int]:
    if not x:
        return None
    try:
        return int(x)
    except Exception:
        return None

def parse_credits_hours(text: str):
    """
    Пытаемся вытащить кредиты/часы из строки, если присутствуют.
    паттерны вида: '3 кр.' '108 ч.' или '3 кредита' etc.
    """
    text = text.lower()
    cr = None
    hr = None
    m = re.search(r"(\d+)\s*(кр|кредит)", text)
    if m:
        cr = int(m.group(1))
    m = re.search(r"(\d+)\s*(ч|час)", text)
    if m:
        hr = int(m.group(1))
    return cr, hr

def section_after_heading(soup: BeautifulSoup, keywords: List[str]) -> List[BeautifulSoup]:
    """
    Ищем заголовок (h2/h3) с ключевыми словами и возвращаем ~блок: ближайшие списки/таблицы под ним.
    Это эвристика, но на страницах ИТМО работает приемлемо.
    """
    heads = soup.select("h1, h2, h3, h4")
    targets = []
    for h in heads:
        t = clean_text(h.get_text()).lower()
        if any(k in t for k in keywords):
            # собираем соседние элементы до следующего заголовка того же уровня
            cur = h
            block = []
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in {"h1", "h2", "h3", "h4"}:
                    break
                if getattr(sib, "name", None) in {"ul", "ol", "table", "p", "div", "section"}:
                    block.append(sib)
            if block:
                targets.append(block)
    # расплющим список
    flat = []
    for b in targets:
        flat.extend(b)
    return flat

def extract_list_items(block_nodes: List[BeautifulSoup]) -> List[str]:
    out = []
    for n in block_nodes:
        for li in n.select("li"):
            txt = clean_text(li.get_text(" "))
            if txt:
                out.append(txt)
    return out

def extract_table_rows(block_nodes: List[BeautifulSoup]) -> List[List[str]]:
    rows = []
    for n in block_nodes:
        for tr in n.select("tr"):
            cells = [clean_text(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            if len(cells) >= 1:
                rows.append(cells)
    return rows

# ---------- Парсинг «по смыслу» ----------

def parse_ai(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    program_name = "Искусственный интеллект"
    # Основной блок «Учебный план/модули»
    modules_nodes = section_after_heading(soup, ["учебный план", "модули", "дисциплин"])
    items_list = extract_list_items(modules_nodes)
    table_rows = extract_table_rows(modules_nodes)

    # Эвристика: в списках часто идут названия дисциплин; семестр — ищем по «1 семестр/2 семестр…»
    # Мы собираем всё как «Путь выбора» по семестрам 1–4, если явно не указано обратное.
    semesters = {1: [], 2: [], 3: [], 4: []}

    def put_course(txt: str, guess_sem: Optional[int] = None):
        cr, hr = parse_credits_hours(txt)
        title = re.sub(r"\(.*?(кр|час).*\)", "", txt, flags=re.I).strip(" •-—")
        # пытаемся выцепить «N семестр»
        m = re.search(r"(\d)\s*семестр", txt, re.I)
        sem = num_or_none(m.group(1)) if m else guess_sem
        sem = sem if sem in {1,2,3,4} else None
        return {"title": title, "credits": cr, "hours": hr, "semester": sem}

    # 1) пробуем таблицы
    for row in table_rows:
        row_txt = " ".join(row)
        c = put_course(row_txt)
        if c["title"]:
            # грубо: если не нашли семестр в строке — раскидаем позднее
            semesters.setdefault(c["semester"] or 0, []).append(c)

    # 2) списки <li>
    for it in items_list:
        c = put_course(it)
        semesters.setdefault(c["semester"] or 0, []).append(c)

    # эвристика: без семестра — кидаем в 2/3 семестр (часто выборки там),
    # но чтобы не гадать, оставим без семестра — бот и так отработает поиск/рекомендации.
    # Сформируем структуру близкую к уже используемой.
    selective_by_sem = []
    for sem in [1,2,3,4]:
        pool = [c for c in semesters.get(sem, []) if c["title"]]
        if pool:
            selective_by_sem.append({
                "semester_number": sem,
                "course_groups": [{
                    "group_type": "Путь выбора дисциплин",
                    "courses": [
                        {"title": c["title"], "credits": c["credits"], "hours": c["hours"]}
                        for c in pool
                    ]
                }]
            })

    # Практика/ГИА — отдельные блоки
    practice_nodes = section_after_heading(soup, ["практика"])
    gia_nodes = section_after_heading(soup, ["гиа", "итоговая", "вкр"])

    practices = []
    for txt in extract_list_items(practice_nodes):
        cr, hr = parse_credits_hours(txt)
        m = re.search(r"(\d)\s*семестр", txt, re.I)
        sem = num_or_none(m.group(1)) if m else None
        practices.append({
            "type": "Практика",
            "title": re.sub(r"\(.*\)", "", txt).strip(" •-—"),
            "semester": sem,
            "credits": cr,
            "hours": hr
        })

    gia_components = []
    for txt in extract_list_items(gia_nodes):
        cr, hr = parse_credits_hours(txt)
        gia_components.append({
            "title": re.sub(r"\(.*\)", "", txt).strip(" •-—"),
            "credits": cr, "hours": hr
        })

    # Собираем итог
    data = {
        "curriculum": {
            "program_name": program_name,
            "blocks": [
                {
                    "block_name": "Блок 1. Модули (дисциплины)",
                    "modules": [
                        {
                            "module_name": "Индивидуальная профессиональная подготовка",
                            "semesters": selective_by_sem or []
                        }
                    ]
                },
                {
                    "block_name": "Блок 2. Практика",
                    "practices": practices
                },
                {
                    "block_name": "Блок 3. ГИА (Государственная итоговая аттестация)",
                    "components": gia_components
                }
            ]
        }
    }
    return data

def parse_ai_product(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    curriculum_name = "Учебный план ОП Управление ИИ-продуктами/AI Product"

    nodes = section_after_heading(soup, ["учебный план", "модули", "дисциплин"])
    items = extract_list_items(nodes) + [" ".join(r) for r in extract_table_rows(nodes)]

    def mk(name: str, sem: Optional[int], txt: str):
        cr, hr = parse_credits_hours(txt)
        return {"name": name, "semester": sem, "credits": cr, "hours": hr}

    by_sem: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: [], 4: []}
    for raw in items:
        title = re.sub(r"\(.*?(кр|час).*\)", "", raw, flags=re.I).strip(" •-—")
        if not title or len(title) < 2:
            continue
        m = re.search(r"(\d)\s*семестр", raw, re.I)
        sem = num_or_none(m.group(1))
        by_sem.setdefault(sem or 0, []).append(mk(title, sem, raw))

    # Блоки по семестрам как «секции»
    sections = []
    for sem in [1, 2, 3, 4]:
        pool = by_sem.get(sem, [])
        if not pool:
            continue
        sec_name = "Обязательные дисциплины. 1 семестр" if sem == 1 else "Из выборочных дисциплин. %d семестр" % sem
        sections.append({
            "section_name": sec_name,
            "courses": pool
        })

    # Практика/ГИА
    practice_nodes = section_after_heading(soup, ["практика"])
    gia_nodes = section_after_heading(soup, ["гиа", "итоговая", "вкр"])

    practice_courses = []
    for txt in extract_list_items(practice_nodes):
        cr, hr = parse_credits_hours(txt)
        m = re.search(r"(\d)\s*семестр", txt, re.I)
        sem = num_or_none(m.group(1)) if m else None
        practice_courses.append({"name": re.sub(r"\(.*\)", "", txt).strip(" •-—"),
                                 "semester": sem, "credits": cr, "hours": hr})

    gia_modules = []
    for txt in extract_list_items(gia_nodes):
        cr, hr = parse_credits_hours(txt)
        gia_modules.append({"module_name": re.sub(r"\(.*\)", "", txt).strip(" •-—"),
                            "credits": cr, "hours": hr})

    data = {
        "curriculum_name": curriculum_name,
        "blocks": [
            {
                "block_name": "Блок 1. Модули (дисциплины)",
                "modules": [
                    {
                        "module_name": "Индивидуальная профессиональная подготовка",
                        "sections": sections
                    }
                ]
            },
            {
                "block_name": "Блок 2. Практика",
                "modules": [
                    {"module_name": "Производственная практика", "courses": practice_courses}
                ]
            },
            {
                "block_name": "Блок 3. ГИА",
                "modules": gia_modules
            }
        ]
    }
    return data

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data"), help="Папка для JSON")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # AI
    html_ai = fetch(URLS["ai"])
    (args.out / "ai.html").write_text(html_ai, encoding="utf-8")
    ai_json = parse_ai(html_ai)
    (args.out / "ai_plan.json").write_text(json.dumps(ai_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # AI Product
    html_prod = fetch(URLS["ai_product"])
    (args.out / "ai_product.html").write_text(html_prod, encoding="utf-8")
    prod_json = parse_ai_product(html_prod)
    (args.out / "ai_product_plan.json").write_text(json.dumps(prod_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK: data/ai_plan.json, data/ai_product_plan.json готовы")

if __name__ == "__main__":
    main()
