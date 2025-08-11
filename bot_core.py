# bot_core.py
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- безопасное разрешение путей ---
def _resolve(p: str) -> Path:
    pth = Path(p)
    cands = [
        Path.cwd()/pth,                         # ./data/ai_plan.json
        Path(__file__).parent/pth.name,         # ./ai_plan.json рядом с файлом
        Path(__file__).parent/'data'/pth.name,  # ./data/ai_plan.json рядом
    ]
    for c in cands:
        if c.exists():
            return c
    return pth

AI_PLAN_PATH = _resolve("data/ai_plan.json")
AI_PRODUCT_PLAN_PATH = _resolve("data/ai_product_plan.json")

ProgramId = str  # "ai" | "ai_product"

# -------------------- Хранилище учебных планов --------------------
class CurriculumStore:
    def __init__(self):
        self.db: Dict[ProgramId, Dict[str, Any]] = {}

    def load(self):
        self.db["ai"] = json.loads(AI_PLAN_PATH.read_text(encoding="utf-8"))
        self.db["ai_product"] = json.loads(AI_PRODUCT_PLAN_PATH.read_text(encoding="utf-8"))

    def list_programs(self) -> List[Tuple[ProgramId, str]]:
        return [
            ("ai", self.db["ai"]["curriculum"]["program_name"]),
            ("ai_product", self.db["ai_product"]["curriculum_name"]),
        ]

store = CurriculumStore()
store.load()

# -------------------- Утилиты выборки --------------------
def _safe_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None

def program_title(pid: ProgramId) -> str:
    for k, v in store.list_programs():
        if k == pid:
            return v
    return pid

def _find_block(blocks: List[dict], name_contains: str) -> Optional[dict]:
    name_contains = name_contains.lower()
    for b in blocks:
        if name_contains in b.get("block_name", "").lower():
            return b
    return None

def get_mandatory_courses_ai(semester: int) -> List[Dict[str, Any]]:
    cur = store.db["ai"]["curriculum"]
    b1 = _find_block(cur["blocks"], "модули")
    out: List[Dict[str, Any]] = []
    if not b1: return out
    for m in b1["modules"]:
        if m["module_name"].startswith("Индивидуальная профессиональная подготовка"):
            for sem in m["semesters"]:
                if sem["semester_number"] == semester:
                    for g in sem["course_groups"]:
                        if "обяз" in g["group_type"].lower():
                            for c in g.get("courses", []):
                                out.append({
                                    "title": c["title"],
                                    "credits": c.get("credits"),
                                    "hours": c.get("hours")
                                })
    return out

def get_selective_courses_ai(semester: int) -> List[Dict[str, Any]]:
    cur = store.db["ai"]["curriculum"]
    b1 = _find_block(cur["blocks"], "модули")
    out: List[Dict[str, Any]] = []
    if not b1: return out
    for m in b1["modules"]:
        if m["module_name"].startswith("Индивидуальная профессиональная подготовка"):
            for sem in m["semesters"]:
                if sem["semester_number"] == semester:
                    for g in sem["course_groups"]:
                        if "путь выбора" in g["group_type"].lower():
                            out.extend(g.get("courses", []))
    return out

def get_practice(pid: ProgramId) -> List[Dict[str, Any]]:
    if pid == "ai":
        cur = store.db["ai"]["curriculum"]
        b2 = _find_block(cur["blocks"], "практика")
        return b2.get("practices", []) if b2 else []
    else:
        blocks = store.db["ai_product"]["blocks"]
        b2 = _find_block(blocks, "практика")
        return b2.get("modules", []) if b2 else []

def get_gia(pid: ProgramId) -> List[Dict[str, Any]]:
    if pid == "ai":
        cur = store.db["ai"]["curriculum"]
        b3 = _find_block(cur["blocks"], "ГИА")
        return b3.get("components", []) if b3 else []
    else:
        blocks = store.db["ai_product"]["blocks"]
        b3 = _find_block(blocks, "ГИА")
        return b3.get("modules", []) if b3 else []

def get_soft_skills(pid: ProgramId) -> List[Dict[str, Any]]:
    if pid == "ai":
        cur = store.db["ai"]["curriculum"]
        b = _find_block(cur["blocks"], "Майнорский факультет")
        return b.get("courses", []) if b else []
    else:
        blocks = store.db["ai_product"]["blocks"]
        b = _find_block(blocks, "Факультативные")
        if not b: return []
        res: List[Dict[str, Any]] = []
        for mod in b.get("modules", []):
            for c in mod.get("courses", []):
                res.append(c)
        return res

def search_courses(pid: ProgramId, query: str) -> List[Dict[str, Any]]:
    q = (query or "").lower()
    res: List[Dict[str, Any]] = []
    if pid == "ai":
        cur = store.db["ai"]["curriculum"]
        for b in cur["blocks"]:
            if "модули" in b["block_name"].lower():
                for m in b.get("modules", []):
                    for sem in m.get("semesters", []):
                        for g in sem.get("course_groups", []):
                            for c in g.get("courses", []):
                                if q in c["title"].lower():
                                    res.append({"title": c["title"], "credits": c.get("credits"), "hours": c.get("hours")})
                    for sm in m.get("sub_modules", []):
                        for c in sm.get("courses", []):
                            title = c.get("title") or c.get("name")
                            if title and q in title.lower():
                                res.append({"title": title, "credits": c.get("credits"), "hours": c.get("hours")})
            else:
                for c in b.get("courses", []):
                    if q in c.get("title", "").lower():
                        res.append({"title": c["title"], "credits": c.get("credits"), "hours": c.get("hours")})
    else:
        blocks = store.db["ai_product"]["blocks"]
        for b in blocks:
            for mod in b.get("modules", []):
                for sec in mod.get("sections", []):
                    for c in sec.get("courses", []):
                        name = c.get("name")
                        if name and q in name.lower():
                            res.append({"title": name, "credits": c.get("credits"), "hours": c.get("hours"), "semester": c.get("semester")})
                for c in mod.get("courses", []):
                    name = c.get("name")
                    if name and q in name.lower():
                        res.append({"title": name, "credits": c.get("credits"), "hours": c.get("hours"), "semester": c.get("semester")})
    return res

# -------------------- Новое: профиль абитуриента + рекомендации --------------------
# Простая карта ключевых слов -> тематик
TAG_TO_QUERY = {
    # инженерия/ML
    "ml": "машинное обучение",
    "ds": "data",
    "cv": "компьютерное зрение",
    "nlp": "язык|текст|nlp|естественного языка",
    "dl": "глубокое обучение|deep",
    "rl": "обучение с подкреплением",
    "stats": "статист",
    "ab": "A/B|эксперимент",
    "sys": "систем|микросервис|оркестраци|контейнер",
    "python": "python",
    "cpp": "c\\+\\+",
    "gpu": "gpu|графическ",
    "bigdata": "больших данных|хранилищ",
    # продукт/менеджмент
    "product": "продукт|менеджм|монетизац|портфел",
    "pm": "менеджмент|продукт",
    "ba": "бизнес-анализ|аналитик",
    "metrics": "метрик|аналитик продукта",
    "design": "дизайн|прототип",
    "mentoring": "ментор",
}

def _score_title(title: str, rx_list: List[re.Pattern]) -> int:
    score = 0
    t = title.lower()
    for rx in rx_list:
        if rx.search(t):
            score += 1
    return score

def _compile_patterns(tags: List[str]) -> List[re.Pattern]:
    pats: List[re.Pattern] = []
    for tag in tags:
        q = TAG_TO_QUERY.get(tag.lower())
        if not q: 
            # если юзер дал свободный текст — тоже добавим
            q = tag
        pats.append(re.compile(q, re.I))
    return pats

def recommend_electives(pid: ProgramId, tags: List[str], semester: Optional[int] = None, top_k: int = 6) -> List[Dict[str, Any]]:
    """Очень простой скорер: собираем все выборные курсы и ранжируем по совпадениям с тегами."""
    rx = _compile_patterns(tags)
    pool: List[Dict[str, Any]] = []

    if pid == "ai":
        # по всем семестрам, но можно сужать
        cur = store.db["ai"]["curriculum"]
        b1 = _find_block(cur["blocks"], "модули")
        if b1:
            for m in b1["modules"]:
                if m["module_name"].startswith("Индивидуальная профессиональная подготовка"):
                    for sem in m["semesters"]:
                        if semester and sem["semester_number"] != semester:
                            continue
                        for g in sem["course_groups"]:
                            if "путь выбора" in g["group_type"].lower():
                                for c in g.get("courses", []):
                                    pool.append({"title": c["title"], "credits": c.get("credits"), "hours": c.get("hours"), "semester": sem["semester_number"]})
    else:
        blocks = store.db["ai_product"]["blocks"]
        for b in blocks:
            for mod in b.get("modules", []):
                # Из выборочных секций 2 семестр + смежные
                for sec in mod.get("sections", []):
                    for c in sec.get("courses", []):
                        sem = c.get("semester")
                        if semester and sem != semester:
                            continue
                        pool.append({"title": c.get("name"), "credits": c.get("credits"), "hours": c.get("hours"), "semester": sem})
                for c in mod.get("courses", []):
                    sem = c.get("semester")
                    if semester and sem != semester:
                        continue
                    pool.append({"title": c.get("name"), "credits": c.get("credits"), "hours": c.get("hours"), "semester": sem})

    # скоринг
    scored = []
    for c in pool:
        s = _score_title(c["title"], rx)
        if s > 0:
            scored.append((s, c))
    # если совсем пусто — вернём топ 6 любых выборных из пула
    if not scored:
        return pool[:top_k]
    scored.sort(key=lambda x: (-x[0], (x[1].get("semester") or 99), x[1]["title"]))
    return [c for _, c in scored[:top_k]]

# -------------------- Правила/Интенты --------------------
INTENTS = {
    "help": r"\b(помощ|что ты умеешь|help)\b",
    "programs": r"\b(программы|направлени|что есть)\b",
    "pick_program": r"\b(ai\s*product|управлени[ея]\s*ии|product|ai\s*продукт|искусственн\w+\s*интеллект|ai)\b",
    "mandatory": r"(обязательн\w+ дисциплин\w+).*?(\d)\s*семестр",
    "selective": r"(выбор|электив\w+).*?(\d)\s*семестр",
    "practice": r"\b(практик\w+)\b",
    "gia": r"\b(гия|вкр|итогов\w+ аттестац\w+)\b",
    "soft": r"(soft\s*skills|софт\s*скил|майнор|микромодул\w+)",
    "search_course": r"(найд[и]|поиск).*?(курс|дисциплин\w+)\s*:?(.+)",
    "set_tags": r"(?:теги|tags|бэкграунд|background)\s*:?(.+)",
    "recommend": r"(рекоменд|рекоменд)\w+(\s*\d\s*семестр)?",
    "compare": r"(сравн|что выбрать|какая программ|подходит)\w+",
}

INTRO = (
    "👋 Я помогу выбрать между магистратурами ИТМО и спланировать учёбу.\n"
    "Доступные программы: /ai и /aiproduct\n"
    "Сначала задай бэкграунд (теги), потом проси рекомендации.\n\n"
    "Примеры:\n"
    "• теги: ml, nlp, python, sys\n"
    "• рекомендации 2 семестр\n"
    "• обязательные дисциплины 1 семестр\n"
    "• выборные 2 семестр\n"
    "• практика / гиа / soft skills\n"
    "• найди курс: глубокое обучение\n"
    "• сравни программы / что выбрать\n"
)

class BotSession:
    def __init__(self):
        self.program: ProgramId = "ai"  # по умолчанию «Искусственный интеллект»
        self.tags: List[str] = []       # короткие теги бэкграунда

    def set_program(self, text: str) -> Optional[str]:
        t = text.lower()
        if re.search(r"ai\s*product|управлени[ея]\s*ии|product|ai\s*продукт", t):
            self.program = "ai_product"
        elif re.search(r"искусственн\w+\s*интеллект|\bai\b", t):
            self.program = "ai"
        else:
            return None
        return f"Ок, работаем с программой: «{program_title(self.program)}»."

    def _set_tags_from_text(self, raw: str) -> str:
        # парсим что угодно: через запятую, пробелы
        vals = [x.strip().lower() for x in re.split(r"[,\s]+", raw) if x.strip()]
        self.tags = list(dict.fromkeys(vals))[:12]  # до 12 штук
        known = ", ".join(self.tags) if self.tags else "—"
        return f"Теги (бэкграунд) обновлены: {known}\nПодсказка: теперь попроси «рекомендации 2 семестр»."

    def _compare_programs(self) -> str:
        # Очень простая эвристика по тегам
        tech_bias = any(t in self.tags for t in ["ml", "ds", "cv", "nlp", "dl", "rl", "python", "cpp", "sys", "gpu", "bigdata", "stats"])
        prod_bias = any(t in self.tags for t in ["product", "pm", "ba", "metrics", "design", "mentoring"])
        if prod_bias and not tech_bias:
            sug = "ai_product"
        elif tech_bias and not prod_bias:
            sug = "ai"
        else:
            sug = self.program  # если не ясно — остаёмся где были
        return (
            "Быстрое сравнение:\n"
            "• AI — больше инженерных и research-курсов (ML/DL/CV/NLP, системные вещи, GPU).\n"
            "• AI Product — управление ИИ‑продуктами: исследования, метрики, монетизация, PM‑навыки.\n\n"
            f"По твоим тегам ({', '.join(self.tags) or '—'}) я бы предложил: «{program_title(sug)}».\n"
            f"Переключиться можно командами: /ai или /aiproduct."
        )

    def handle(self, text: str) -> str:
        t = (text or "").lower().strip()
        if not t or re.search(INTENTS["help"], t):
            return INTRO

        if re.search(INTENTS["programs"], t):
            items = [f"{pid} — {title}" for pid, title in store.list_programs()]
            return "Доступные программы:\n" + "\n".join(items)

        pick = self.set_program(text)
        if pick:
            return pick

        # Установка тегов (бэкграунд)
        m = re.search(INTENTS["set_tags"], t)
        if m:
            raw = (m.group(1) or "").strip(" :")
            if not raw:
                return "Напиши теги после двоеточия. Пример: «теги: ml, nlp, python, sys»."
            return self._set_tags_from_text(raw)

        # Рекомендации
        m = re.search(INTENTS["recommend"], t)
        if m:
            sem = None
            m2 = re.search(r"(\d)\s*семестр", t)
            if m2:
                sem = _safe_int(m2.group(1))
            if not self.tags:
                return "Сначала задай теги (бэкграунд). Пример: «теги: ml, nlp, python»."
            rows = recommend_electives(self.program, self.tags, semester=sem, top_k=6)
            if not rows:
                return "Пока не нашёл подходящих выборных — попробуй расширить теги."
            def line(r): 
                return f"• {r['title']} — {r.get('credits','?')} кр., {r.get('hours','?')} ч. (семестр: {r.get('semester','—')})"
            hdr = f"Рекомендации ({program_title(self.program)})"
            if sem: hdr += f", семестр {sem}"
            hdr += f"\nПо тегам: {', '.join(self.tags)}"
            return hdr + "\n" + "\n".join(map(line, rows))

        # Сравнение/выбор программы
        if re.search(INTENTS["compare"], t):
            return self._compare_programs()

        # Обяз/выборные
        m = re.search(INTENTS["mandatory"], t)
        if m:
            sem = _safe_int(m.group(2))
            if not sem:
                return "Укажи номер семестра (например: «обязательные дисциплины 1 семестр»)."
            if self.program == "ai":
                rows = get_mandatory_courses_ai(sem)
                if not rows:
                    return f"В семестре {sem} нет обязательных дисциплин или данные отсутствуют."
                lines = [f"• {r['title']} — {r.get('credits','?')} кр., {r.get('hours','?')} ч." for r in rows]
                return f"Обязательные дисциплины (семестр {sem}, {program_title(self.program)}):\n" + "\n".join(lines)
            else:
                # в AI Product обязательные лежат в секции «Обязательные дисциплины. 1 семестр»
                rows = [r for r in search_courses("ai_product", "") if r.get("semester") == sem]
                rows = rows[:20]
                if not rows:
                    return f"Обязательные для семестра {sem} не найдены."
                lines = [f"• {r['title']} — {r.get('credits','?')} кр., {r.get('hours','?')} ч." for r in rows]
                return f"Обязательные дисциплины (семестр {sem}, {program_title(self.program)}):\n" + "\n".join(lines)

        m = re.search(INTENTS["selective"], t)
        if m:
            sem = _safe_int(m.group(2))
            if not sem:
                return "Укажи номер семестра (например: «выборные 2 семестр»)."
            if self.program == "ai":
                rows = get_selective_courses_ai(sem)
            else:
                rows = [c for c in search_courses("ai_product", "") if c.get("semester") == sem]
            if not rows:
                return f"Выборные дисциплины не найдены для семестра {sem}."
            lines = []
            for r in rows:
                title = r.get("title") or r.get("name") or ""
                lines.append(f"• {title} — {r.get('credits','?')} кр., {r.get('hours','?')} ч.")
            return f"Выборные дисциплины (семестр {sem}, {program_title(self.program)}):\n" + "\n".join(lines)

        if re.search(INTENTS["practice"], t):
            rows = get_practice(self.program)
            if not rows:
                return "Данных о практике не найдено."
            def fmt(x):
                title = x.get("title") or x.get("name") or x.get("module_name")
                sem = x.get("semester", "—")
                cr = x.get("credits", x.get("total_credits", "—"))
                hrs = x.get("hours", x.get("total_hours", "—"))
                return f"• {title} (семестр: {sem}) — {cr} кр., {hrs} ч."
            return f"Практика — {program_title(self.program)}:\n" + "\n".join(map(fmt, rows))

        if re.search(INTENTS["gia"], t):
            rows = get_gia(self.program)
            if not rows:
                return "Данных по ГИА/ВКР не найдено."
            def fmt(x):
                title = x.get("title") or x.get("module_name", "ГИА")
                sem = x.get("semester", "—")
                cr = x.get("credits", x.get("total_credits", "—"))
                hrs = x.get("hours", x.get("total_hours", "—"))
                return f"• {title} (семестр: {sem}) — {cr} кр., {hrs} ч."
            return f"ГИА/ВКР — {program_title(self.program)}:\n" + "\n".join(map(fmt, rows))

        if re.search(INTENTS["soft"], t):
            rows = get_soft_skills(self.program)
            if not rows:
                return "Софт‑скиллы не найдены."
            def title_of(x):
                return x.get("title") or x.get("name") or "Без названия"
            lines = [f"• {title_of(r)} — {r.get('credits','?')} кр., {r.get('hours','?')} ч." for r in rows]
            return f"Soft Skills / майноры — {program_title(self.program)}:\n" + "\n".join(lines)

        m = re.search(INTENTS["search_course"], t)
        if m:
            q = (m.group(3) or "").strip(" :")
            if not q:
                return "Напиши, что искать. Пример: «найди курс: глубокое обучение»."
            rows = search_courses(self.program, q)
            if not rows:
                return f"Ничего не найдено по запросу «{q}»."
            lines = [f"• {r.get('title')} — {r.get('credits','?')} кр., {r.get('hours','?')} ч." for r in rows[:20]]
            more = "" if len(rows) <= 20 else f"\n…и ещё {len(rows)-20} результатов"
            return f"Найдено по «{q}» — {program_title(self.program)}:\n" + "\n".join(lines) + more

        # Жёсткий фильтр релевантности
        return ("Я отвечаю только на вопросы по двум магистратурам ИТМО, их учебным планам и выбору между ними.\n"
                "Спроси, например: «сравни программы», «рекомендации 2 семестр», «выборные 2 семестр», «практика», «soft skills», «найди курс: …»")
