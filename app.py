
# FoodLens PP v4 — robust calories-by-photo pipeline
# Features:
# - gpt-4o high-detail vision returns structured components + cooked/raw + method + vessel/size + area_fraction
# - Strong postprocess calibration (per-100 cooked/raw tables, typical gram ranges, vessel capacity clamps)
# - Sanity checks for calories/macros; protein density clamp; fried/oil adjustments
# - Manual edit of components (grams/count) with instant recompute
# - Tracking start for goals; dark UI; single-file Flask

import os, io, json, base64, hashlib, random, re, csv, math
from datetime import datetime, date
from functools import wraps
from typing import Tuple, List, Dict, Any

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_from_directory, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
from openai import OpenAI
from sqlalchemy import text as sql_text

APP_NAME = "FoodLens PP"

load_dotenv()

# ---------------- Settings ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_VISION_MODEL = "gpt-4o"
OPENAI_VISION_MODEL_FALLBACK = "gpt-4o-mini"
OPENAI_TEXT_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT = 60.0
OPENAI_MAX_RETRIES = 2
VISION_DETAIL = "high"

SECRET_KEY = "change-this-in-production"
DATABASE_URL = "sqlite:///app.db"
UPLOAD_FOLDER = "static/uploads"
MAX_CONTENT_LENGTH = 10 * 1024 * 1024

# Image preprocessing
MAX_IMAGE_SIDE = 1280
JPEG_QUALITY = 85
ALLOWED_EXT = {"jpg","jpeg","png","webp","bmp","gif"}

# Demo
DEMO_MODE = False
FALLBACK_TO_DEMO_ON_QUOTA = True

# ------------------------------------------

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SQLALCHEMY_DATABASE_URI=DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=os.path.join(app.root_path, UPLOAD_FOLDER),
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
)
db = SQLAlchemy(app)

_base_client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)
client = _base_client.with_options(max_retries=OPENAI_MAX_RETRIES)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False, default="User")
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.relationship("Profile", backref="user", uselist=False)
    meals_photo = db.relationship("MealPhoto", backref="user", lazy=True)
    meals_manual = db.relationship("ManualMeal", backref="user", lazy=True)

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=True)
    sex = db.Column(db.String(12), nullable=True)  # male/female/other
    height_cm = db.Column(db.Float, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    activity = db.Column(db.String(16), nullable=True)  # sedentary/light/moderate/active/athlete
    goal = db.Column(db.String(12), nullable=True)      # lose/maintain/gain
    macro_p_pct = db.Column(db.Float, nullable=True)
    macro_f_pct = db.Column(db.Float, nullable=True)
    macro_c_pct = db.Column(db.Float, nullable=True)
    tracking_enabled_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MealPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    dish_name = db.Column(db.String(255), nullable=True)
    calories_kcal = db.Column(db.Float, nullable=True)
    proteins_g = db.Column(db.Float, nullable=True)
    fats_g = db.Column(db.Float, nullable=True)
    carbs_g = db.Column(db.Float, nullable=True)
    portion_grams = db.Column(db.Float, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    components_json = db.Column(db.Text, nullable=True)  # list of components
    vessel = db.Column(db.String(32), nullable=True)      # plate/bowl
    size_class = db.Column(db.String(16), nullable=True)  # small/medium/large
    fill_level = db.Column(db.String(16), nullable=True)  # low/medium/high
    count_in_tracking = db.Column(db.Boolean, nullable=False, default=True)  # учитывать в трекинге
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ManualMeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    calories_kcal = db.Column(db.Float, nullable=False, default=0)
    proteins_g = db.Column(db.Float, nullable=True)
    fats_g = db.Column(db.Float, nullable=True)
    carbs_g = db.Column(db.Float, nullable=True)
    portion_grams = db.Column(db.Float, nullable=True)
    count_in_tracking = db.Column(db.Boolean, nullable=False, default=True)  # учитывать в трекинге
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- Auth helpers ----------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Пожалуйста, войдите в аккаунт.", "warning")
            return redirect(url_for("login", next=request.path))
        if not getattr(g, "user", None):
            session.pop("user_id", None)
            flash("Сессия истекла, войдите заново.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.before_request
def load_current_user():
    uid = session.get("user_id")
    user = None
    if uid is not None:
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            uid_int = uid
        user = db.session.get(User, uid_int)
    g.user = user

def admin_required(view):
    @wraps(view)
    def wrapped_admin(*args, **kwargs):
        if not session.get("user_id"):
            flash("Нужно войти в аккаунт.", "warning")
            return redirect(url_for("login", next=request.path))
        user = getattr(g, "user", None)
        if not user or not getattr(user, "is_admin", False):
            flash("Недостаточно прав для доступа в админ-панель.", "danger")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped_admin


@app.context_processor
def inject_user():
    return {"current_user": getattr(g, "user", None), "APP_NAME": APP_NAME, "getattr": getattr}

with app.app_context():
    db.create_all()
    # add new columns if missing
    for stmt in [
        "ALTER TABLE meal_photo ADD COLUMN components_json TEXT",
        "ALTER TABLE meal_photo ADD COLUMN vessel VARCHAR(32)",
        "ALTER TABLE meal_photo ADD COLUMN size_class VARCHAR(16)",
        "ALTER TABLE meal_photo ADD COLUMN fill_level VARCHAR(16)",
        "ALTER TABLE profile ADD COLUMN tracking_enabled_at DATETIME",
        "ALTER TABLE meal_photo ADD COLUMN count_in_tracking BOOLEAN DEFAULT 1",
        "ALTER TABLE manual_meal ADD COLUMN count_in_tracking BOOLEAN DEFAULT 1",
    ]:
        try:
            db.session.execute(sql_text(stmt)); db.session.commit()
        except Exception:
            db.session.rollback()

# ---------------- Nutrition logic ----------------

# Canonical categories and per100 nutrition (kcal, P, F, C), cooked vs raw where relevant
# Values are edges/medians for cooked
PER100_COOKED = {
    "pasta":      {"kcal":150, "p":5,  "f":1,  "c":30},
    "rice":       {"kcal":135, "p":2.5,"f":0.3,"c":29},
    "buckwheat":  {"kcal":115, "p":4,  "f":1,  "c":24},
    "potato":     {"kcal":87,  "p":2,  "f":0.1,"c":20},
    "bread":      {"kcal":250, "p":9,  "f":2.6,"c":49},
    "chicken_breast": {"kcal":165,"p":31,"f":3.6,"c":0},
    "chicken_drumstick":{"kcal":220,"p":27,"f":12,"c":0},
    "chicken_thigh":{"kcal":225,"p":26,"f":13,"c":0},
    "beef_steak": {"kcal":250,"p":26,"f":15,"c":0},
    "pork":       {"kcal":280,"p":24,"f":20,"c":0},
    "fish_lean":  {"kcal":160,"p":26,"f":5, "c":0},
    "salmon":     {"kcal":210,"p":20,"f":14,"c":0},
    "dumplings":  {"kcal":260,"p":10,"f":8, "c":38},
    "cheese":     {"kcal":340,"p":25,"f":26,"c":1.3},
    "vegetables": {"kcal":25, "p":1.2,"f":0.2,"c":4.5},
    "fruits":     {"kcal":50, "p":0.6,"f":0.3,"c":12},
    "sauce_oil":  {"kcal":900,"p":0,  "f":100,"c":0},
}

# Typical grams per piece where count provided
TYPICAL_PER_PIECE = {
    "chicken_drumstick": 80,  # edible
    "chicken_wing": 35,
    "chicken_thigh": 120,
    "sushi_piece": 35,
    "dumpling": 12,
    "cherry_tomato": 15,
    "cucumber_slice": 6,
}

# Vessel capacity estimates (grams) for average-density foods
VESSEL_CAPACITY = {
    ("plate","small"): 450,
    ("plate","medium"): 650,
    ("plate","large"): 850,
    ("bowl","small"): 350,
    ("bowl","medium"): 500,
    ("bowl","large"): 700,
}

FILL_LEVEL_MULT = {"low":0.7, "medium":1.0, "high":1.15}

# Clamp ranges by category (grams per component)
GRAMS_RANGE = {
    "pasta": (80, 300),
    "rice": (80, 350),
    "buckwheat": (80, 300),
    "potato": (80, 400),
    "chicken_breast": (60, 200),
    "chicken_drumstick": (60, 400),  # count-based preferred
    "chicken_thigh": (80, 280),
    "beef_steak": (100, 300),
    "fish_lean": (80, 220),
    "salmon": (80, 220),
    "dumplings": (120, 350),
    "vegetables": (30, 250),
    "fruits": (30, 250),
    "bread": (20, 150),
    "cheese": (10, 120),
}

# Protein density cap (max grams protein per 100g food)
PROTEIN_DENSITY_CAP = {
    "chicken_breast": 33.0,
    "fish_lean": 30.0,
    "salmon": 26.0,
    "beef_steak": 30.0,
    "dumplings": 14.0,
    "pasta": 13.0,
    "rice": 7.0,
}

# Fat adjustment per method (per 100g)
METHOD_FAT_DELTA = {"fried": 4.0, "deep_fried": 8.0, "grill": 1.0, "baked": 0.5, "boiled": -1.0, "steamed": -1.5}

# Map textual tags from LLM to canonical categories
def canonical_category(name:str, tags:List[str])->str:
    n = (name or "").lower()
    t = " ".join(tags or []).lower()
    def has(*ws): return any(w in n or w in t for w in ws)
    if has("penne","pasta","макарон","паста"): return "pasta"
    if has("rice","рис"): return "rice"
    if has("греч","buckwheat"): return "buckwheat"
    if has("картоф"): return "potato"
    if has("bread","хлеб","батон","булк"): return "bread"
    if has("суши"): return "sushi"
    if has("сыр","cheese"): return "cheese"
    if has("огур","помид","томат","овощ","vegetable","cucumber","tomato","salad"): return "vegetables"
    if has("fruit","фрукт","яблок","банан","ягод"): return "fruits"
    if has("dumpling","пельм","вареник","манты"): return "dumplings"
    if has("breast","грудк"): return "chicken_breast"
    if has("drumstick","голен","ножк"): return "chicken_drumstick"
    if has("thigh","бедро"): return "chicken_thigh"
    if has("salmon","лосос","семг"): return "salmon"
    if has("fish","рыб"): return "fish_lean"

    return "vegetables"  # safe default low-cal

# --- Nutrition overrides (broader food coverage & safer defaults) ---
# Добавляем обобщённую категорию "unknown" для любых блюд, которые не попали
# ни в одну из известных категорий, и отдельную категорию "sausages" для колбасок/сосисок.
PER100_COOKED.setdefault("unknown", {"kcal": 180, "p": 7.0, "f": 7.0, "c": 23.0})
PER100_COOKED.setdefault("sausages", {"kcal": 300, "p": 12.0, "f": 27.0, "c": 2.0})

# Типичные веса за штуку остаются лишь ориентиром и не ограничивают пользователя.
TYPICAL_PER_PIECE.setdefault("sausages", 80)  # средняя сосиска/колбаска

# Диапазоны граммов — широкие, чтобы покрывать порции от очень маленьких до крупных.
GRAMS_RANGE.setdefault("sausages", (60, 600))
GRAMS_RANGE.setdefault("unknown", (40, 800))

# Ограничение по белку на 100 г для колбасных изделий
PROTEIN_DENSITY_CAP.setdefault("sausages", 16.0)

# Переопределяем canonical_category так, чтобы она покрывала больше блюд
# и по умолчанию относила неизвестное к "unknown", а не к "vegetables".
def canonical_category(name: str, tags: List[str]) -> str:
    n = (name or "").lower()
    t = " ".join(tags or []).lower()

    def has(*ws):
        return any(w in n or w in t for w in ws)

    # гарниры / крупы
    if has("penne", "pasta", "макарон", "паста"):
        return "pasta"
    if has("rice", "рис"):
        return "rice"
    if has("греч", "buckwheat"):
        return "buckwheat"
    if has("картоф", "potato", "potatoes"):
        return "potato"

    # хлеб / булочки
    if has("bread", "хлеб", "батон", "булк", "bun", "baguette"):
        return "bread"

    # колбасные изделия, хот-доги, сосиски
    if has("sausage", "sausages", "wurst", "сосиск", "колбас", "сардель", "hot dog", "frankfurter"):
        return "sausages"

    # мясо / рыба
    if has("breast", "грудк"):
        return "chicken_breast"
    if has("drumstick", "голен", "ножк"):
        return "chicken_drumstick"
    if has("thigh", "бедро"):
        return "chicken_thigh"
    if has("salmon", "лосос", "семг"):
        return "salmon"
    if has("fish", "рыб"):
        return "fish_lean"
    if has("steak", "стейк", "бифштекс", "говядин"):
        return "beef_steak"
    if has("pork", "свини"):
        return "pork"

    # суши / пельмени / сыр
    if has("суши", "sushi"):
        return "sushi"
    if has("сыр", "cheese"):
        return "cheese"
    if has("dumpling", "пельм", "вареник", "манты"):
        return "dumplings"

    # овощи и фрукты
    if has("огур", "помид", "томат", "овощ", "vegetable", "cucumber", "tomato", "salad"):
        return "vegetables"
    if has("fruit", "фрукт", "яблок", "банан", "ягод"):
        return "fruits"

    # по умолчанию — среднекалорийное блюдо
    return "unknown"

def safe_float(x, default=None):
    try:
        return float(x)
    except:
        return default

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def estimate_piece_grams(cat:str, count:int)->float:
    per = TYPICAL_PER_PIECE.get(cat) or 0
    if per and count:
        return per*count
    return 0.0

def capacity_limit(vessel:str, size_class:str, fill_level:str)->float:
    cap = VESSEL_CAPACITY.get((vessel or "plate", size_class or "medium"), 600)
    return cap * FILL_LEVEL_MULT.get(fill_level or "medium", 1.0)

SYSTEM_PROMPT = (
    "Ты — эксперт по нутрициологии и визуальной оценке порций. "
    "По фотографии ты оцениваешь состав блюда, примерную массу порции и калорийность. "
    "Все названия блюда и компонентов пиши на русском языке. "
    "Если на фото видно общий стол, банкет, буфет или больше 5 разных блюд — "
    "верни JSON: {\"error\": \"too_many_dishes\", \"message\": \"На фото слишком много разных блюд. Загрузите фото одной тарелки.\"}. "
    "Во всех остальных случаях оценивай честно. "
    "Отвечай строго валидным JSON без текста вне JSON."
)

USER_INSTRUCTIONS = (
    "Определи одно основное блюдо на фото и разложи его на компоненты. "
    "Верни строго один JSON-объект. "
    "Поле dish_name — краткое русское название блюда (например: \"Курица с рисом и брокколи\"). "
    "Название компонентов (name) — тоже на русском. "
    "Структура JSON такая: "
    "{"
      "\"dish_name\": str, "
      "\"vessel\": \"plate\"|\"bowl\", "
      "\"size_class\": \"small\"|\"medium\"|\"large\", "
      "\"fill_level\": \"low\"|\"medium\"|\"high\", "
      "\"portion_grams\": number, "
      "\"calories_kcal\": number, "
      "\"proteins_g\": number, "
      "\"fats_g\": number, "
      "\"carbs_g\": number, "
      "\"confidence\": number, "
      "\"notes\": str, "

      "\"components\": [ "
        "{ "
          "\"name\": str, "
          "\"tags\": [str], "
          "\"cooked_state\": \"raw\"|\"cooked\", "
          "\"method\": \"fried\"|\"baked\"|\"boiled\"|\"steamed\"|\"grill\"|null, "
          "\"count\": number|null, "
          "\"unit_weight_g\": number|null, "
          "\"area_fraction\": number|null, "
          "\"est_grams\": number, "
          "\"per100_kcal_used\": number, "
          "\"proteins_g\": number, "
          "\"fats_g\": number, "
          "\"carbs_g\": number "
        "} "
      "]"
    "}. "

    "Если паста выглядит мягкой и увеличенной в объёме — это варёная (≈150 ккал/100 г). "
    "Сумма масс и калорий по компонентам должна соответствовать итоговой массе и калориям (±5%). "
    "Никакого текста вне JSON не добавляй."
)

def _to_small_jpeg_b64(file_storage, max_edge=MAX_IMAGE_SIDE, quality=JPEG_QUALITY) -> Tuple[str, bytes, bytes]:
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    jpeg_bytes = buf.getvalue()
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"
    return "image/jpeg", data_url.encode("utf-8"), jpeg_bytes

def _demo_result(seed_bytes: bytes):
    rnd = random.Random(int.from_bytes(hashlib.sha256(seed_bytes).digest()[:4], "big"))
    comps = [
        {"name":"Паста", "tags":["pasta"], "cooked_state":"cooked", "method":"boiled", "count":None, "unit_weight_g":None,
         "area_fraction":0.42, "est_grams":180, "per100_kcal_used":150, "proteins_g":9, "fats_g":2, "carbs_g":54},
        {"name":"Куриная грудка", "tags":["chicken","breast"], "cooked_state":"cooked", "method":"baked", "count":None,"unit_weight_g":None,
         "area_fraction":0.18, "est_grams":110, "per100_kcal_used":165, "proteins_g":34, "fats_g":4, "carbs_g":0},
        {"name":"Огурец", "tags":["vegetable"], "cooked_state":"raw","method":None,"count":None,"unit_weight_g":None,
         "area_fraction":0.2, "est_grams":60, "per100_kcal_used":16, "proteins_g":1, "fats_g":0, "carbs_g":3},
        {"name":"Помидоры черри", "tags":["vegetable","tomato"], "cooked_state":"raw","method":None,"count":4,"unit_weight_g":15,
         "area_fraction":0.12, "est_grams":60, "per100_kcal_used":20, "proteins_g":1, "fats_g":0, "carbs_g":4},
    ]
    tot_g = sum(c["est_grams"] for c in comps)
    kcal = 180*1.5 + 110*1.65 + 60*0.16 + 60*0.2
    return {
        "dish_name":"Паста с курицей и овощами",
        "vessel":"bowl","size_class":"medium","fill_level":"medium",
        "portion_grams": round(tot_g,1),
        "calories_kcal": round(kcal,1),
        "proteins_g": 9+34+1+1,
        "fats_g": 2+4+0+0,
        "carbs_g": 54+0+3+4,
        "confidence": round(rnd.uniform(0.65, 0.85), 2),
        "notes":"DEMO: оценка без API.",
        "components": comps
    }

def _sum_components(comps):
    s = {"g":0.0,"kcal":0.0,"p":0.0,"f":0.0,"c":0.0}
    for c in comps or []:
        s["g"] += safe_float(c.get("est_grams"),0) or 0
        s["kcal"] += safe_float(c.get("calories_kcal") or (c.get("per100_kcal_used",0)*safe_float(c.get("est_grams"),0)/100.0),0)
        s["p"] += safe_float(c.get("proteins_g"),0) or 0
        s["f"] += safe_float(c.get("fats_g"),0) or 0
        s["c"] += safe_float(c.get("carbs_g"),0) or 0
    return s

def _per100_for_component(cat:str, cooked_state:str)->Dict[str,float]:
    # choose cooked for most; raw seldom used except explicit
    base = PER100_COOKED.get(cat) or PER100_COOKED["vegetables"]
    # if pasta/rice and state raw — force cooked values (we judge by ready-to-eat), unless explicitly "raw pasta"
    if cat in ("pasta","rice","buckwheat","potato","dumplings"):
        return PER100_COOKED[cat]
    return base

def _apply_method_adjust(cat:str, method:str, per100:Dict[str,float])->Dict[str,float]:
    if not method: return per100
    delta_f = METHOD_FAT_DELTA.get(method, 0.0)
    p100 = dict(per100)
    p100["f"] = max(0.0, p100["f"] + delta_f)
    p100["kcal"] = 4*(p100["p"]+p100["c"]) + 9*p100["f"]
    return p100

def _calibrate_components(components:List[Dict[str,Any]], vessel:str, size_class:str, fill_level:str)->List[Dict[str,Any]]:
    cap = capacity_limit(vessel, size_class, fill_level)
    # normalize over-capacity
    total_g = sum(safe_float(c.get("est_grams"),0) or 0 for c in components)
    if total_g > 0 and total_g > cap:
        scale = cap/total_g
        for c in components:
            c["est_grams"] = round((safe_float(c.get("est_grams"),0) or 0)*scale,1)

    for c in components:
        name = c.get("name") or ""
        tags = c.get("tags") or []
        cat = canonical_category(name, tags)
        c["category"] = cat

        grams = safe_float(c.get("est_grams"),0) or 0
        count = int(safe_float(c.get("count"),0) or 0)
        unit_w = safe_float(c.get("unit_weight_g"),None)

        # if count given and grams unrealistically low -> estimate by per-piece
        if count and (grams < count*0.6*TYPICAL_PER_PIECE.get(cat, 0)):
            guess = estimate_piece_grams(cat, count)
            if guess>0:
                grams = max(grams, guess)
                c["est_grams"] = grams

        # clamp by typical range
        if cat in GRAMS_RANGE:
            lo,hi = GRAMS_RANGE[cat]
            c["est_grams"] = clamp(grams, lo*(0.5 if count else 1.0), hi)

        # per100 from cooked/raw and method
        per100 = _per100_for_component(cat, c.get("cooked_state") or "cooked")
        per100 = _apply_method_adjust(cat, c.get("method"), per100)

        # recompute macros from per100
        grams = safe_float(c.get("est_grams"),0) or 0
        c["per100_kcal_used"] = round(per100["kcal"],1)
        c["calories_kcal"] = round(per100["kcal"]*grams/100.0,1)
        c["proteins_g"] = round(per100["p"]*grams/100.0,1)
        c["fats_g"] = round(per100["f"]*grams/100.0,1)
        c["carbs_g"] = round(per100["c"]*grams/100.0,1)

        # protein density sanity
        cap_p = PROTEIN_DENSITY_CAP.get(cat)
        if cap_p:
            max_p = cap_p*grams/100.0
            if c["proteins_g"] > max_p:
                c["proteins_g"] = round(max_p,1)
                # adjust kcal accordingly (subtract protein diff kcal)
                # keep carbs same; adjust fats if needed later by method
                p100_adj = {"p":(c["proteins_g"]/grams*100.0 if grams>0 else 0), "f":(c["fats_g"]/grams*100.0 if grams>0 else 0), "c":(c["carbs_g"]/grams*100.0 if grams>0 else 0)}
                c["calories_kcal"] = round(4*(c["proteins_g"]+c["carbs_g"]) + 9*c["fats_g"],1)

    return components

def _finalize_totals(data:Dict[str,Any])->Dict[str,Any]:
    comps = data.get("components") or []
    sums = _sum_components(comps)
    data["portion_grams"] = round(sums["g"],1)
    data["calories_kcal"] = round(sums["kcal"],1)
    data["proteins_g"] = round(sums["p"],1)
    data["fats_g"] = round(sums["f"],1)
    data["carbs_g"] = round(sums["c"],1)
    # final sanity for full plate: avoid >1200 kcal unless clearly multi-ingredient fried
    data["calories_kcal"] = min(data["calories_kcal"], 1200.0)
    return data

def analyze_with_llm(data_url_text:str)->Dict[str,Any]:
    messages = [
        {"role":"system","content":SYSTEM_PROMPT},
        {"role":"user","content":[
            {"type":"text","text":USER_INSTRUCTIONS},
            {"type":"image_url","image_url":{"url":data_url_text, "detail":VISION_DETAIL}},
        ]},
    ]
    try:
        resp = client.chat.completions.create(
            model=OPENAI_VISION_MODEL,
            messages=messages,
            temperature=0.1,
            response_format={"type":"json_object"},
            max_tokens=900,
        )
    except Exception:
        resp = client.chat.completions.create(
            model=OPENAI_VISION_MODEL_FALLBACK,
            messages=messages,
            temperature=0.1,
            response_format={"type":"json_object"},
            max_tokens=900,
        )
    txt = resp.choices[0].message.content
    try:
        return json.loads(txt)
    except Exception:
        # try to salvage json
        a = txt.find("{"); b = txt.rfind("}")
        return json.loads(txt[a:b+1])

def analyze_image_file(file_storage):
    mime, data_url_bytes, raw_jpeg = _to_small_jpeg_b64(file_storage)
    if DEMO_MODE:
        data = _demo_result(raw_jpeg[:64])
    else:
        llm_data = analyze_with_llm(data_url_bytes.decode("utf-8"))
        # Normalize minimal fields
        data = {
            "dish_name": llm_data.get("dish_name") or "Блюдо",
            "vessel": (llm_data.get("vessel") or "plate"),
            "size_class": (llm_data.get("size_class") or "medium"),
            "fill_level": (llm_data.get("fill_level") or "medium"),
            "confidence": safe_float(llm_data.get("confidence"), 0.7) or 0.7,
            "notes": (llm_data.get("notes") or "").strip() or "Оценка ориентировочная.",
            "components": llm_data.get("components") or []
        }
    # Calibration
    data["components"] = _calibrate_components(data["components"], data.get("vessel"), data.get("size_class"), data.get("fill_level"))
    data = _finalize_totals(data)
    return data, mime, raw_jpeg

# ---------------- Energy calc helpers for plan (unchanged from v3; omitted here for brevity in v4) ----------------
# Minimal features to keep app working: compute_targets for profile
def mifflin_st_jeor(weight_kg, height_cm, age, sex):
    if None in (weight_kg, height_cm, age) or not sex:
        return None
    base = 10*weight_kg + 6.25*height_cm - 5*age
    if sex == "male": return base + 5
    if sex == "female": return base - 161
    return base

ACTIVITY_FACTORS = {"sedentary":1.2,"light":1.375,"moderate":1.55,"active":1.725,"athlete":1.9}
GOAL_ADJUST = {"lose":-0.15,"maintain":0.0,"gain":0.1}

def default_macros_for_goal(goal:str)->Dict[str,float]:
    if goal=="lose":   return {"p":32.0,"f":28.0,"c":40.0}
    if goal=="gain":   return {"p":25.0,"f":30.0,"c":45.0}
    return {"p":30.0,"f":30.0,"c":40.0}

def compute_targets(profile):
    if not profile: return None
    bmr = mifflin_st_jeor(profile.weight_kg, profile.height_cm, profile.age, profile.sex)
    if bmr is None: return None
    pal = ACTIVITY_FACTORS.get(profile.activity or "sedentary", 1.2)
    tdee = bmr*pal
    adjust = GOAL_ADJUST.get(profile.goal or "maintain", 0.0)
    target_cal = tdee*(1.0+adjust)

    macros = default_macros_for_goal(profile.goal or "maintain")
    if profile.macro_p_pct is not None: macros["p"]=profile.macro_p_pct
    if profile.macro_f_pct is not None: macros["f"]=profile.macro_f_pct
    if profile.macro_c_pct is not None: macros["c"]=profile.macro_c_pct
    tot = max(1.0, macros["p"]+macros["f"]+macros["c"])
    p_pct = macros["p"]/tot*100; f_pct = macros["f"]/tot*100; c_pct = macros["c"]/tot*100
    p_g = target_cal*(p_pct/100)/4; f_g = target_cal*(f_pct/100)/9; c_g = target_cal*(c_pct/100)/4
    return {"bmr":round(bmr,1),"tdee":round(tdee,1),"target_cal":round(target_cal,1),
            "p_g":round(p_g,1),"f_g":round(f_g,1),"c_g":round(c_g,1),"p_pct":round(p_pct,1),"f_pct":round(f_pct,1),"c_pct":round(c_pct,1)}

# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")

# Auth (same style as v3)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("name") or "").strip() or "User"
        password = request.form.get("password") or ""
        if not email or not password:
            flash("Введите email и пароль.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("Пароль должен содержать минимум 6 символов.", "danger")
            return render_template("register.html")
        # Обрезаем имя до 60 символов и валидируем
        if len(name) > 60:
            name = name[:60]
            flash("Имя было обрезано до 60 символов.", "warning")
        # Дополнительная проверка на пустое имя после обрезки
        if not name or len(name.strip()) == 0:
            name = "User"
        if db.session.query(User).filter_by(email=email).first():
            flash("Такой email уже зарегистрирован.", "warning")
            return render_template("register.html")
        u = User(email=email, display_name=name, password_hash=generate_password_hash(password))
        db.session.add(u); db.session.commit()
        # профиль без автозапуска трекинга
        prof = Profile(user_id=u.id, activity="sedentary", goal="maintain", tracking_enabled_at=None)
        db.session.add(prof); db.session.commit()
        session["user_id"] = u.id
        flash("Регистрация успешна!", "success")
        return redirect(url_for("index"))
    return render_template("register.html")
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.session.query(User).filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверный email или пароль.", "danger")
            return render_template("login.html")
        session["user_id"] = user.id
        flash("Вы вошли!", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("index"))

# Upload & analysis
def _allowed(filename): return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

@app.route("/upload", methods=["GET","POST"])
@login_required
def upload():
    if request.method == "POST":
        f = request.files.get("photo")
        if not f or not _allowed(f.filename):
            flash("Загрузите изображение (jpg, png, webp...)", "warning")
            return render_template("upload.html")
        try:
            result, mime, raw_jpeg = analyze_image_file(f)
        except Exception as e:
            flash(f"Ошибка анализа изображения: {e}", "danger")
            return render_template("upload.html")
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        base = secure_filename(f.filename.rsplit(".",1)[0]) or "meal"
        filename = datetime.utcnow().strftime("%Y%m%d_%H%M%S_") + base + ".jpg"
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        with open(path, "wb") as out:
            out.write(raw_jpeg)
        # По умолчанию учитываем в трекинге, если чекбокс отмечен
        count_in_tracking = request.form.get("count_in_tracking") == "on"
        meal = MealPhoto(
            user_id=g.user.id, filename=filename,
            dish_name=result.get("dish_name"),
            calories_kcal=result.get("calories_kcal"),
            proteins_g=result.get("proteins_g"),
            fats_g=result.get("fats_g"),
            carbs_g=result.get("carbs_g"),
            portion_grams=result.get("portion_grams"),
            confidence=result.get("confidence"),
            notes=result.get("notes"),
            components_json=json.dumps(result.get("components") or [], ensure_ascii=False),
            vessel=result.get("vessel"), size_class=result.get("size_class"), fill_level=result.get("fill_level"),
            count_in_tracking=count_in_tracking
        )
        db.session.add(meal); db.session.commit()
        flash("Фото проанализировано.", "success")
        return redirect(url_for("meal_detail", meal_id=meal.id))
    return render_template("upload.html")

@app.route("/meal/<int:meal_id>")
@login_required
def meal_detail(meal_id):
    meal = db.session.get(MealPhoto, meal_id)
    if not meal or meal.user_id != g.user.id:
        return "Not found", 404
    comps = []
    try: comps = json.loads(meal.components_json or "[]")
    except: comps = []
    # Обработка count_in_tracking для старых записей
    count_in_tracking = getattr(meal, 'count_in_tracking', True)
    return render_template("meal_detail.html", meal=meal, components=comps, count_in_tracking=count_in_tracking)

# Edit components (grams/count) and recompute
@app.route("/meal/<int:meal_id>/edit", methods=["POST"])
@login_required
def meal_edit(meal_id):
    meal = db.session.get(MealPhoto, meal_id)
    if not meal or meal.user_id != g.user.id:
        return "Not found", 404
    comps = json.loads(meal.components_json or "[]")
    # Expect form inputs like comp-0-grams, comp-0-count
    for i, c in enumerate(comps):
        grams = request.form.get(f"comp-{i}-grams")
        count = request.form.get(f"comp-{i}-count")
        if grams is not None:
            try: c["est_grams"] = float(grams)
            except: pass
        if count is not None and count != "":
            try: c["count"] = int(count)
            except: pass
    comps = _calibrate_components(comps, meal.vessel or "plate", meal.size_class or "medium", meal.fill_level or "medium")
    # finalize
    sums = _sum_components(comps)
    meal.components_json = json.dumps(comps, ensure_ascii=False)
    meal.portion_grams = round(sums["g"],1)
    meal.calories_kcal = round(sums["kcal"],1)
    meal.proteins_g = round(sums["p"],1)
    meal.fats_g = round(sums["f"],1)
    meal.carbs_g = round(sums["c"],1)
    db.session.commit()
    flash("Порции обновлены.", "success")
    return redirect(url_for("meal_detail", meal_id=meal.id))

@app.route("/meal/<int:meal_id>/toggle_tracking", methods=["POST"])
@login_required
def meal_toggle_tracking(meal_id):
    meal = db.session.get(MealPhoto, meal_id)
    if not meal or meal.user_id != g.user.id:
        return "Not found", 404
    meal.count_in_tracking = request.form.get("count_in_tracking") == "on"
    db.session.commit()
    flash("Настройка трекинга обновлена.", "success")
    return redirect(url_for("meal_detail", meal_id=meal.id))

# Dashboard & profile & plan (simplified, same as v3 for brevity)
@app.route("/dashboard")
@login_required
def dashboard():
    meals_p = db.session.query(MealPhoto).filter_by(user_id=g.user.id).order_by(MealPhoto.created_at.desc()).all()
    meals_m = db.session.query(ManualMeal).filter_by(user_id=g.user.id).order_by(ManualMeal.created_at.desc()).all()
    prof = db.session.query(Profile).filter_by(user_id=g.user.id).first()

    # Агрегация по дням для графика
    daily = {}
    def add_to(day_key, kcal, p, f, c):
        daily.setdefault(day_key, {"cal": 0, "p": 0, "f": 0, "c": 0})
        daily[day_key]["cal"] += (kcal or 0)
        daily[day_key]["p"] += (p or 0)
        daily[day_key]["f"] += (f or 0)
        daily[day_key]["c"] += (c or 0)

    for m in meals_p:
        add_to(m.created_at.date().isoformat(), m.calories_kcal, m.proteins_g, m.fats_g, m.carbs_g)
    for m in meals_m:
        add_to(m.created_at.date().isoformat(), m.calories_kcal, m.proteins_g, m.fats_g, m.carbs_g)

    labels = sorted(daily.keys())
    chart = {
        "labels": labels,
        "calories": [round(daily[d]["cal"], 2) for d in labels],
        "proteins": [round(daily[d]["p"], 2) for d in labels],
        "fats": [round(daily[d]["f"], 2) for d in labels],
        "carbs": [round(daily[d]["c"], 2) for d in labels],
    }

    # Блок трекинга целей «съедено сегодня / осталось»
    prof = db.session.query(Profile).filter_by(user_id=g.user.id).first()
    targets = compute_targets(prof) if prof else None
    today_summary = None
    if prof and prof.tracking_enabled_at and targets:
        start = prof.tracking_enabled_at
        # Используем UTC дату для сравнения, так как created_at хранится в UTC
        today_utc = datetime.utcnow().date()
        start_date = start.date() if hasattr(start, 'date') else start

        def use_for_goals(dt):
            # Учитываем все блюда за сегодня, если трекинг включен
            if dt is None:
                return False
            # created_at хранится в UTC, поэтому сравниваем с UTC датой
            meal_date = dt.date() if hasattr(dt, 'date') else dt
            # Просто проверяем, что блюдо создано сегодня (по UTC)
            return meal_date == today_utc

        sum_today = {"cal": 0, "p": 0, "f": 0, "c": 0}
        for m in meals_p:
            # Проверяем count_in_tracking - SQLite хранит BOOLEAN как INTEGER (0 или 1)
            count_val = getattr(m, 'count_in_tracking', None)
            # Если None или отсутствует - считаем True, иначе проверяем значение
            if count_val is None:
                should_count = True
            else:
                # SQLite возвращает 1 или 0, преобразуем в boolean
                should_count = (count_val == 1 or count_val is True)
            
            # Проверяем дату
            is_today = use_for_goals(m.created_at)
            
            if is_today and should_count:
                sum_today["cal"] += (m.calories_kcal or 0)
                sum_today["p"] += (m.proteins_g or 0)
                sum_today["f"] += (m.fats_g or 0)
                sum_today["c"] += (m.carbs_g or 0)
        for m in meals_m:
            # Проверяем count_in_tracking - SQLite хранит BOOLEAN как INTEGER (0 или 1)
            count_val = getattr(m, 'count_in_tracking', None)
            if count_val is None:
                should_count = True
            else:
                # SQLite возвращает 1 или 0, преобразуем в boolean
                should_count = (count_val == 1 or count_val is True)
            
            # Проверяем дату
            is_today = use_for_goals(m.created_at)
            
            if is_today and should_count:
                sum_today["cal"] += (m.calories_kcal or 0)
                sum_today["p"] += (m.proteins_g or 0)
                sum_today["f"] += (m.fats_g or 0)
                sum_today["c"] += (m.carbs_g or 0)

        today_summary = {
            "eaten": sum_today,
            "target_cal": targets["target_cal"],
            "remaining_cal": max(0, targets["target_cal"] - sum_today["cal"]),
        }

    return render_template(
        "dashboard.html",
        meals_photo=meals_p[:6],
        meals_manual=meals_m[:6],
        chart=chart,
        today_summary=today_summary,
    )

@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    prof = db.session.query(Profile).filter_by(user_id=g.user.id).first()
    if request.method == "POST":
        action = request.form.get("action") or "save"
        if action == "start_tracking":
            prof.tracking_enabled_at = datetime.utcnow()
            db.session.commit()
            flash("Трекинг целей включён.", "success")
            return redirect(url_for("plan"))
        if action == "stop_tracking":
            prof.tracking_enabled_at = None
            db.session.commit()
            flash("Трекинг целей выключен.", "info")
            return redirect(url_for("profile"))
        prof.age = int(request.form.get("age") or 0) or None
        prof.sex = request.form.get("sex") or None
        prof.height_cm = float(request.form.get("height_cm") or 0) or None
        prof.weight_kg = float(request.form.get("weight_kg") or 0) or None
        prof.activity = request.form.get("activity") or "sedentary"
        prof.goal = request.form.get("goal") or "maintain"
        p = request.form.get("macro_p_pct"); f = request.form.get("macro_f_pct"); c = request.form.get("macro_c_pct")
        prof.macro_p_pct = float(p) if p else None
        prof.macro_f_pct = float(f) if f else None
        prof.macro_c_pct = float(c) if c else None
        db.session.commit()
        flash("Профиль обновлён.", "success")
        return redirect(url_for("plan"))
    targets = compute_targets(prof)
    return render_template("profile.html", prof=prof, targets=targets, activities=ACTIVITY_FACTORS.keys())

@app.route("/plan")
@login_required
def plan():
    prof = db.session.query(Profile).filter_by(user_id=g.user.id).first()
    targets = compute_targets(prof)
    # Sum only after tracking_enabled_at
    mp = db.session.query(MealPhoto).filter_by(user_id=g.user.id).order_by(MealPhoto.created_at.desc()).all()
    mm = db.session.query(ManualMeal).filter_by(user_id=g.user.id).order_by(ManualMeal.created_at.desc()).all()
    start = prof.tracking_enabled_at if prof else None
    # Используем UTC дату для сравнения, так как created_at хранится в UTC
    today_utc = datetime.utcnow().date()
    
    def use_for_goals(dt):
        if start is None or dt is None: return False
        # created_at хранится в UTC, поэтому сравниваем с UTC датой
        meal_date = dt.date() if hasattr(dt, 'date') else dt
        # Учитываем все блюда за сегодня, если трекинг включен (по UTC)
        return meal_date == today_utc
    
    sum_today = {"cal":0,"p":0,"f":0,"c":0}
    for m in mp:
        # Проверяем count_in_tracking - SQLite хранит BOOLEAN как INTEGER (0 или 1)
        count_val = getattr(m, 'count_in_tracking', None)
        if count_val is None:
            should_count = True
        else:
            # SQLite возвращает 1 или 0, преобразуем в boolean
            should_count = (count_val == 1 or count_val is True)
        
        # Проверяем дату
        is_today = use_for_goals(m.created_at)
        
        if is_today and should_count:
            sum_today["cal"] += (m.calories_kcal or 0); sum_today["p"] += (m.proteins_g or 0); sum_today["f"] += (m.fats_g or 0); sum_today["c"] += (m.carbs_g or 0)
    for m in mm:
        # Проверяем count_in_tracking - SQLite хранит BOOLEAN как INTEGER (0 или 1)
        count_val = getattr(m, 'count_in_tracking', None)
        if count_val is None:
            should_count = True
        else:
            # SQLite возвращает 1 или 0, преобразуем в boolean
            should_count = (count_val == 1 or count_val is True)
        
        # Проверяем дату
        is_today = use_for_goals(m.created_at)
        
        if is_today and should_count:
            sum_today["cal"] += (m.calories_kcal or 0); sum_today["p"] += (m.proteins_g or 0); sum_today["f"] += (m.fats_g or 0); sum_today["c"] += (m.carbs_g or 0)
    return render_template("plan.html", prof=prof, targets=targets, sum_today=sum_today)

# Manual add
@app.route("/manual/add", methods=["GET","POST"])
@login_required
def manual_add():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Введите название блюда.", "warning")
            return render_template("manual_add.html")
        # Обрезаем название до 70 символов
        if len(name) > 70:
            flash("Название не должно превышать 70 символов.", "danger")
            return render_template("manual_add.html")
        
        def fnum(v, max_val=None, min_val=0):
            """Парсит число с валидацией диапазона. Возвращает None если невалидно."""
            if not v or (isinstance(v, str) and v.strip() == ""):
                return None
            try: 
                val = float(v)
                if val < min_val:
                    return None
                if max_val is not None and val > max_val:
                    return None
                return val
            except (ValueError, TypeError, OverflowError): 
                return None
        
        # Валидация калорий (обязательное поле, от 1 до 10000)
        calories_kcal = fnum(request.form.get("calories_kcal"), max_val=10000, min_val=1)
        if calories_kcal is None:
            flash("Калории должны быть положительным числом от 1 до 10000 ккал.", "danger")
            return render_template("manual_add.html")
        
        # Валидация белков (необязательно, но если указано - от 0 до 1000)
        proteins_g_val = request.form.get("proteins_g")
        proteins_g = None
        if proteins_g_val and proteins_g_val.strip():
            proteins_g = fnum(proteins_g_val, max_val=1000, min_val=0)
            if proteins_g is None:
                flash("Белки должны быть от 0 до 1000 г.", "danger")
                return render_template("manual_add.html")
        
        # Валидация жиров (необязательно, но если указано - от 0 до 1000)
        fats_g_val = request.form.get("fats_g")
        fats_g = None
        if fats_g_val and fats_g_val.strip():
            fats_g = fnum(fats_g_val, max_val=1000, min_val=0)
            if fats_g is None:
                flash("Жиры должны быть от 0 до 1000 г.", "danger")
                return render_template("manual_add.html")
        
        # Валидация углеводов (необязательно, но если указано - от 0 до 1000)
        carbs_g_val = request.form.get("carbs_g")
        carbs_g = None
        if carbs_g_val and carbs_g_val.strip():
            carbs_g = fnum(carbs_g_val, max_val=1000, min_val=0)
            if carbs_g is None:
                flash("Углеводы должны быть от 0 до 1000 г.", "danger")
                return render_template("manual_add.html")
        
        # Валидация порции (необязательно, но если указано - от 1 до 10000)
        portion_grams_val = request.form.get("portion_grams")
        portion_grams = None
        if portion_grams_val and portion_grams_val.strip():
            portion_grams = fnum(portion_grams_val, max_val=10000, min_val=1)
            if portion_grams is None:
                flash("Порция должна быть от 1 до 10000 г.", "danger")
                return render_template("manual_add.html")
        
        count_in_tracking = request.form.get("count_in_tracking") == "on"
        entry = ManualMeal(
            user_id=g.user.id,
            name=name,
            calories_kcal=calories_kcal,
            proteins_g=proteins_g,
            fats_g=fats_g,
            carbs_g=carbs_g,
            portion_grams=portion_grams,
            count_in_tracking=count_in_tracking
        )
        db.session.add(entry); db.session.commit()
        flash("Блюдо добавлено.", "success")
        return redirect(url_for("dashboard"))
    return render_template("manual_add.html")

# Export CSV
@app.route("/export.csv")
@login_required
def export_csv():
    rows = []
    for m in db.session.query(MealPhoto).filter_by(user_id=g.user.id).all():
        rows.append(["photo", m.created_at.isoformat(), m.dish_name or "", m.calories_kcal or 0, m.proteins_g or 0, m.fats_g or 0, m.carbs_g or 0, m.portion_grams or "", m.filename])
    for m in db.session.query(ManualMeal).filter_by(user_id=g.user.id).all():
        rows.append(["manual", m.created_at.isoformat(), m.name, m.calories_kcal or 0, m.proteins_g or 0, m.fats_g or 0, m.carbs_g or 0, m.portion_grams or "", ""])
    out = io.StringIO()
    cw = csv.writer(out); cw.writerow(["type","created_at","name","kcal","protein_g","fat_g","carb_g","portion_g","filename"])
    cw.writerows(rows)
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=foodlens_export.csv"
    return resp



@app.route("/admin")
@admin_required
def admin_index():
    users = db.session.query(User).order_by(User.created_at.desc()).limit(100).all()
    # Статистика
    total_users = db.session.query(User).count()
    total_meals = db.session.query(MealPhoto).count()
    total_manual = db.session.query(ManualMeal).count()
    active_tracking = db.session.query(Profile).filter(Profile.tracking_enabled_at.isnot(None)).count()
    total_admins = db.session.query(User).filter_by(is_admin=True).count()
    stats = {
        "total_users": total_users,
        "total_meals": total_meals,
        "total_manual": total_manual,
        "active_tracking": active_tracking,
        "total_admins": total_admins,
    }
    return render_template("admin.html", users=users, stats=stats)

@app.route("/admin/user/<int:user_id>")
@admin_required
def admin_user_detail(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден.", "danger")
        return redirect(url_for("admin_index"))
    meals_photo = db.session.query(MealPhoto).filter_by(user_id=user_id).order_by(MealPhoto.created_at.desc()).limit(20).all()
    meals_manual = db.session.query(ManualMeal).filter_by(user_id=user_id).order_by(ManualMeal.created_at.desc()).limit(20).all()
    profile = db.session.query(Profile).filter_by(user_id=user_id).first()
    return render_template("admin_user_detail.html", user=user, meals_photo=meals_photo, meals_manual=meals_manual, profile=profile)

@app.route("/admin/user/<int:user_id>/toggle_admin", methods=["POST"])
@admin_required
def admin_toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден.", "danger")
        return redirect(url_for("admin_index"))
    if user.id == g.user.id:
        flash("Нельзя изменить свой статус администратора.", "warning")
        return redirect(url_for("admin_index"))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f"Статус администратора {'включен' if user.is_admin else 'выключен'} для {user.email}.", "success")
    return redirect(url_for("admin_user_detail", user_id=user_id))

@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден.", "danger")
        return redirect(url_for("admin_index"))
    if user.id == g.user.id:
        flash("Нельзя удалить свой аккаунт.", "warning")
        return redirect(url_for("admin_index"))
    # Удаляем связанные данные
    db.session.query(MealPhoto).filter_by(user_id=user_id).delete()
    db.session.query(ManualMeal).filter_by(user_id=user_id).delete()
    db.session.query(Profile).filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f"Пользователь {user.email} удален.", "success")
    return redirect(url_for("admin_index"))

@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5556)


# --- Prompt overrides tuned for generic dishes and better mass estimation ---
