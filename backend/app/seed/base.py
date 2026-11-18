"""Reference/configuration seed. Idempotent: safe to run repeatedly.

This seeds configuration (roles, regions, units, categories, settings, data source registry),
NOT market data. Everything here can be edited afterwards in the admin panel."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    AttributeOption,
    Category,
    CategoryAttribute,
    DataConnector,
    DataSource,
    District,
    Organization,
    OrganizationMember,
    Permission,
    PlatformSetting,
    Region,
    Role,
    SubscriptionPlan,
    Unit,
    User,
)
from app.services.settings_service import FALLBACKS

PERMISSIONS = {
    "products.create": "Create products in the catalog",
    "catalog.manage": "Manage categories, attributes, units, regions and all products",
    "suppliers.manage_own": "Create/manage own organization's supplier profiles and offers",
    "suppliers.manage_all": "Manage any supplier profile",
    "suppliers.verify": "Verify suppliers",
    "offers.manage_all": "Manage any offer",
    "quotes.request": "Request quotations and rate suppliers",
    "quotes.respond": "Respond to quotation requests",
    "market_data.manage": "Manage data sources, connectors, imports, matches, observations",
    "users.manage": "Manage users",
    "roles.manage": "Manage roles and permissions",
    "settings.manage": "Manage platform settings and exchange rates",
    "audit.view": "View audit logs",
    "demo.manage": "View and purge simulated demo data",
}

ROLES = {
    "buyer": ("Biznes xaridor", "Бизнес-покупатель", "Business Buyer", True, ["quotes.request"]),
    "supplier": ("Yetkazib beruvchi", "Поставщик", "Supplier", True,
                 ["products.create", "suppliers.manage_own", "quotes.respond"]),
    "manufacturer": ("Ishlab chiqaruvchi", "Производитель", "Manufacturer", True,
                     ["products.create", "suppliers.manage_own", "quotes.respond"]),
    "market_data_admin": ("Bozor ma'lumotlari administratori", "Администратор рыночных данных", "Market Data Administrator", False,
                          ["products.create", "catalog.manage", "suppliers.verify", "offers.manage_all", "market_data.manage",
                           "suppliers.manage_own"]),
    "super_admin": ("Platforma super administratori", "Супер-администратор платформы", "Platform Super Administrator", False,
                    list(PERMISSIONS)),
}

# Administrative centres (approximate) — used only for region-level markers and distances.
REGIONS = [
    ("UZ-TK", "Toshkent shahri", "г. Ташкент", "Tashkent city", 41.2995, 69.2401, ["toshkent", "ташкент", "tashkent", "toshkent shahar"]),
    ("UZ-TO", "Toshkent viloyati", "Ташкентская область", "Tashkent region", 41.0167, 69.7500, ["toshkent viloyat", "ташкентская"]),
    ("UZ-SA", "Samarqand viloyati", "Самаркандская область", "Samarkand region", 39.6542, 66.9597, ["samarqand", "самарканд", "samarkand"]),
    ("UZ-BU", "Buxoro viloyati", "Бухарская область", "Bukhara region", 39.7747, 64.4286, ["buxoro", "бухара", "bukhara"]),
    ("UZ-AN", "Andijon viloyati", "Андижанская область", "Andijan region", 40.7821, 72.3442, ["andijon", "андижан", "andijan"]),
    ("UZ-FA", "Farg'ona viloyati", "Ферганская область", "Fergana region", 40.3842, 71.7843, ["fargona", "farg'ona", "фергана", "fergana"]),
    ("UZ-NG", "Namangan viloyati", "Наманганская область", "Namangan region", 40.9983, 71.6726, ["namangan", "наманган"]),
    ("UZ-JI", "Jizzax viloyati", "Джизакская область", "Jizzakh region", 40.1158, 67.8422, ["jizzax", "джизак", "jizzakh"]),
    ("UZ-QA", "Qashqadaryo viloyati", "Кашкадарьинская область", "Kashkadarya region", 38.8606, 65.7891, ["qashqadaryo", "кашкадарья", "kashkadarya", "qarshi", "карши"]),
    ("UZ-SU", "Surxondaryo viloyati", "Сурхандарьинская область", "Surkhandarya region", 37.2242, 67.2783, ["surxondaryo", "сурхандарья", "surkhandarya", "termiz", "термез"]),
    ("UZ-NW", "Navoiy viloyati", "Навоийская область", "Navoi region", 40.0844, 65.3792, ["navoiy", "навои", "navoi"]),
    ("UZ-XO", "Xorazm viloyati", "Хорезмская область", "Khorezm region", 41.5500, 60.6333, ["xorazm", "хорезм", "khorezm", "urganch", "ургенч"]),
    ("UZ-SI", "Sirdaryo viloyati", "Сырдарьинская область", "Syrdarya region", 40.4897, 68.7842, ["sirdaryo", "сырдарья", "syrdarya", "guliston"]),
    ("UZ-QR", "Qoraqalpog'iston Respublikasi", "Республика Каракалпакстан", "Republic of Karakalpakstan", 42.4600, 59.6100, ["qoraqalpogiston", "каракалпакстан", "karakalpakstan", "nukus", "нукус"]),
]

TASHKENT_DISTRICTS = [("Bektemir", "Бектемир"), ("Chilonzor", "Чиланзар"), ("Mirobod", "Мирабад"),
                      ("Mirzo Ulug'bek", "Мирзо-Улугбек"), ("Olmazor", "Алмазар"), ("Sergeli", "Сергели"),
                      ("Shayxontohur", "Шайхантахур"), ("Uchtepa", "Учтепа"), ("Yakkasaroy", "Яккасарай"),
                      ("Yashnobod", "Яшнабад"), ("Yunusobod", "Юнусабад"), ("Yangihayot", "Янгихаёт")]

UNITS = [  # code, uz, ru, en, symbol, dimension, factor_to_base, aliases
    ("piece", "dona", "штука", "piece", "pcs", "count", "1", ["dona", "ta", "шт", "pcs", "pc", "sht"]),
    ("kg", "kilogramm", "килограмм", "kilogram", "kg", "mass", "1", ["кг", "kilo", "kilogramm"]),
    ("g", "gramm", "грамм", "gram", "g", "mass", "0.001", ["г", "гр", "gr", "gramm"]),
    ("t", "tonna", "тонна", "ton", "t", "mass", "1000", ["т", "tonna", "ton", "tn"]),
    ("l", "litr", "литр", "liter", "l", "volume", "1", ["л", "litr", "liter", "litre"]),
    ("ml", "millilitr", "миллилитр", "milliliter", "ml", "volume", "0.001", ["мл"]),
    ("m", "metr", "метр", "meter", "m", "length", "1", ["м", "metr", "metre"]),
    ("m2", "kvadrat metr", "квадратный метр", "square meter", "m²", "area", "1", ["м2", "м²", "kv.m", "кв.м", "sqm"]),
    ("m3", "kub metr", "кубический метр", "cubic meter", "m³", "volume", "1000", ["м3", "м³", "kub", "куб"]),
    ("box", "quti", "коробка", "box", "box", "package", None, ["quti", "коробка", "кор", "karobka"]),
    ("pack", "qadoq", "упаковка", "package", "pack", "package", None, ["qadoq", "упаковка", "уп", "upakovka", "pachka"]),
    ("set", "to'plam", "комплект", "set", "set", "package", None, ["toplam", "комплект", "компл", "nabor"]),
    ("pallet", "poddon", "поддон", "pallet", "pallet", "package", None, ["poddon", "поддон", "паллета"]),
    ("bag", "qop", "мешок", "bag", "bag", "package", None, ["qop", "мешок", "meshok"]),
]


def A(code, uz, ru, en, t, req=False, filt=False, key=False, opts=None, unit=None):
    return dict(code=code, name_uz=uz, name_ru=ru, name_en=en, data_type=t, is_required=req, is_filterable=filt,
                is_matching_key=key, options=opts or [], unit=unit)


def O(*vals):
    return [(v, uz, ru) for v, uz, ru in vals]


COND = O(("new", "Yangi", "Новый"), ("used", "Ishlatilgan", "Б/у"), ("refurbished", "Qayta tiklangan", "Восстановленный"))

CATEGORIES = [
    ("food", "Oziq-ovqat va ichimliklar", "Продукты питания и напитки", "Food & beverages", "utensils",
     ["oziq", "ovqat", "продукт", "food"],
     [A("brand", "Brend", "Бренд", "Brand", "text", filt=True, key=True),
      A("manufacturer", "Ishlab chiqaruvchi", "Производитель", "Manufacturer", "text"),
      A("net_weight", "Sof og'irlik", "Вес нетто", "Net weight", "number", key=True, unit="kg"),
      A("packaging", "Qadoq", "Упаковка", "Packaging", "select", filt=True,
        opts=O(("bag", "Qop", "Мешок"), ("bottle", "Shisha", "Бутылка"), ("can", "Banka", "Банка"), ("box", "Quti", "Коробка"), ("bulk", "Sochma", "Развес"))),
      A("shelf_life_days", "Saqlash muddati (kun)", "Срок годности (дней)", "Shelf life (days)", "number"),
      A("production_date", "Ishlab chiqarilgan sana", "Дата производства", "Production date", "date"),
      A("expiration_date", "Yaroqlilik muddati", "Срок годности до", "Expiration date", "date"),
      A("ingredients", "Tarkibi", "Состав", "Ingredients", "text")]),
    ("electronics", "Elektronika va maishiy texnika", "Электроника и бытовая техника", "Electronics & appliances", "cpu",
     ["elektronika", "texnika", "электроника", "техника"],
     [A("brand", "Brend", "Бренд", "Brand", "text", True, True, True),
      A("model", "Model", "Модель", "Model", "text", key=True),
      A("specs", "Texnik xususiyatlar", "Технические характеристики", "Technical specifications", "text"),
      A("warranty_months", "Kafolat (oy)", "Гарантия (мес.)", "Warranty (months)", "number", filt=True),
      A("condition", "Holati", "Состояние", "Condition", "select", filt=True, opts=COND),
      A("power_w", "Quvvat (Vt)", "Мощность (Вт)", "Power (W)", "number")]),
    ("textiles", "Kiyim, poyabzal va to'qimachilik", "Одежда, обувь и текстиль", "Clothing, footwear & textiles", "shirt",
     ["kiyim", "poyabzal", "одежда", "обувь", "текстиль", "mato", "ткань"],
     [A("brand", "Brend", "Бренд", "Brand", "text", filt=True),
      A("size", "O'lcham", "Размер", "Size", "text", filt=True, key=True),
      A("color", "Rang", "Цвет", "Color", "text", filt=True),
      A("material", "Material", "Материал", "Material", "select", filt=True, key=True,
        opts=O(("cotton", "Paxta", "Хлопок"), ("polyester", "Poliester", "Полиэстер"), ("wool", "Jun", "Шерсть"),
               ("leather", "Charm", "Кожа"), ("silk", "Ipak", "Шёлк"), ("blend", "Aralash", "Смесовая"))),
      A("gender", "Jins / auditoriya", "Пол / аудитория", "Gender / audience", "select", filt=True,
        opts=O(("men", "Erkaklar", "Мужской"), ("women", "Ayollar", "Женский"), ("kids", "Bolalar", "Детский"), ("unisex", "Uniseks", "Унисекс")))]),
    ("cosmetics", "Kosmetika va parfyumeriya", "Косметика и парфюмерия", "Cosmetics & perfumes", "sparkles",
     ["kosmetika", "atir", "косметика", "парфюм"],
     [A("brand", "Brend", "Бренд", "Brand", "text", True, True, True),
      A("volume_ml", "Hajm (ml)", "Объём (мл)", "Volume (ml)", "number", key=True),
      A("skin_type", "Teri turi", "Тип кожи", "Skin type", "text"),
      A("expiration_date", "Yaroqlilik muddati", "Срок годности до", "Expiration date", "date"),
      A("certification", "Sertifikat", "Сертификат", "Certification", "text")]),
    ("construction", "Qurilish materiallari", "Строительные материалы", "Construction materials", "brick",
     ["qurilish", "строй", "строительн", "construction"],
     [A("material_type", "Material turi", "Тип материала", "Material type", "text", True, True, True),
      A("grade", "Marka / sinf", "Марка / класс", "Grade", "text", filt=True, key=True),
      A("dimensions", "O'lchamlari", "Размеры", "Dimensions", "text"),
      A("manufacturer", "Ishlab chiqaruvchi", "Производитель", "Manufacturer", "text", filt=True),
      A("standard", "Standart (GOST/O'zDSt)", "Стандарт (ГОСТ/O'zDSt)", "Standard", "text")]),
    ("industrial", "Sanoat mahsulotlari va xomashyo", "Промышленные товары и сырьё", "Industrial products & raw materials", "factory",
     ["sanoat", "xomashyo", "сырьё", "сырье", "промышлен"],
     [A("material_type", "Material turi", "Тип материала", "Material type", "text", filt=True, key=True),
      A("grade", "Marka", "Марка", "Grade", "text", filt=True, key=True),
      A("purity_pct", "Tozaligi (%)", "Чистота (%)", "Purity (%)", "number"),
      A("standard", "Standart", "Стандарт", "Standard", "text")]),
    ("furniture", "Mebel va uy jihozlari", "Мебель и товары для дома", "Furniture & home", "sofa",
     ["mebel", "мебель", "uy", "дом"],
     [A("material", "Material", "Материал", "Material", "text", filt=True),
      A("dimensions", "O'lchamlari (sm)", "Размеры (см)", "Dimensions (cm)", "text", key=True),
      A("color", "Rang", "Цвет", "Color", "text", filt=True),
      A("assembly_required", "Yig'ish kerak", "Требует сборки", "Assembly required", "boolean", filt=True)]),
    ("auto-parts", "Avtomobil ehtiyot qismlari", "Автозапчасти и аксессуары", "Automotive parts & accessories", "car",
     ["avto", "ehtiyot", "запчаст", "авто"],
     [A("part_number", "Detal raqami", "Номер детали", "Part number", "text", True, True, True),
      A("brand", "Brend", "Бренд", "Brand", "text", filt=True, key=True),
      A("vehicle_compatibility", "Mos avtomobillar", "Совместимость с авто", "Vehicle compatibility", "text", filt=True),
      A("model", "Model", "Модель", "Model", "text"),
      A("condition", "Holati", "Состояние", "Condition", "select", filt=True, opts=COND)]),
    ("office", "Ofis va kanselyariya tovarlari", "Офисные и канцелярские товары", "Office supplies & stationery", "paperclip",
     ["ofis", "kanselyar", "канцеляр", "офис"],
     [A("brand", "Brend", "Бренд", "Brand", "text", filt=True, key=True),
      A("format", "Format", "Формат", "Format", "text", filt=True, key=True),
      A("pack_count", "Qadoqdagi soni", "Кол-во в упаковке", "Items per pack", "number")]),
    ("agriculture", "Qishloq xo'jaligi mahsulotlari va texnikasi", "Сельхозпродукция и техника", "Agricultural products & equipment", "sprout",
     ["qishloq", "dehqon", "сельхоз", "агро", "ugit", "удобр"],
     [A("crop_or_type", "Ekin / tur", "Культура / тип", "Crop / type", "text", filt=True, key=True),
      A("grade", "Nav / sinf", "Сорт / класс", "Grade", "text", filt=True),
      A("harvest_year", "Hosil yili", "Год урожая", "Harvest year", "number"),
      A("condition", "Holati (texnika)", "Состояние (техника)", "Condition (equipment)", "select", opts=COND)]),
    ("medical", "Tibbiy va sog'liqni saqlash tovarlari", "Медицинские товары", "Medical & healthcare goods", "stethoscope",
     ["tibbiy", "медицин", "medical"],
     [A("registration_number", "Ro'yxatdan o'tish raqami", "Рег. удостоверение №", "Registration number", "text", True, key=True),
      A("manufacturer", "Ishlab chiqaruvchi", "Производитель", "Manufacturer", "text", filt=True),
      A("expiration_date", "Yaroqlilik muddati", "Срок годности до", "Expiration date", "date"),
      A("sterile", "Steril", "Стерильно", "Sterile", "boolean", filt=True)]),
    ("packaging", "Qadoqlash va ishlab chiqarish materiallari", "Упаковка и материалы для производства", "Packaging & manufacturing materials", "package",
     ["qadoq", "упаков", "packaging", "tara", "тара"],
     [A("material", "Material", "Материал", "Material", "select", filt=True, key=True,
        opts=O(("pet", "PET", "ПЭТ"), ("hdpe", "HDPE", "ПНД"), ("cardboard", "Karton", "Картон"), ("glass", "Shisha", "Стекло"),
               ("film", "Plyonka", "Плёнка"), ("paper", "Qog'oz", "Бумага"))),
      A("capacity", "Sig'imi / o'lchami", "Ёмкость / размер", "Capacity / size", "text", key=True),
      A("thickness_mic", "Qalinligi (mkm)", "Толщина (мкм)", "Thickness (µm)", "number")]),
    ("other", "Boshqa tovarlar", "Прочие товары", "Other products", "boxes", ["boshqa", "прочее"],
     [A("brand", "Brend", "Бренд", "Brand", "text", filt=True)]),
]

MEDICAL_NOTE = ("Medical goods may require state registration and licensing in Uzbekistan. TradeFlow lists commercial offers "
                "only and does not verify regulatory compliance; buyers must check registration documents.")

DATA_SOURCES = [
    # code, name, type, provenance, reliability, freshness, active, terms, notes
    ("supplier_submissions", "Supplier submissions (TradeFlow)", "supplier_submission", "supplier_declared", "0.6", 168, True, "permitted",
     "Offers published by registered suppliers. Supplier-declared asking prices, not transactions."),
    ("admin_manual_entry", "Market data admin — manual entry", "manual", "official_statistic", "0.8", 720, True, "permitted",
     "Observations entered by authorised administrators from documented sources (record the source URL)."),
    ("authorized_file_imports", "Authorised CSV/XLSX imports", "file_import", "supplier_declared", "0.6", 168, True, "permitted",
     "Price lists provided by suppliers or partners with permission to use them."),
]
# Candidate sources from the project brief + desk research (Nov 2026). NONE is integrated or enabled.
# (code, name, type, provenance, base_url, has_public_api, requires_auth, notes)
CANDIDATE_SOURCES = [
    ("cand_narxstat", "NarxStat — National Statistics Committee (candidate)", "official_statistics", "official_statistic",
     "https://narx.stat.uz", True, False,
     "Open price-statistics platform launched Nov 2026 (press reports): CPI, weekly average prices of essential food and "
     "fuel by region/district, CSV/JSON download and an API without registration. Retail/consumer prices, not B2B. "
     "TODO before enabling: read the official API docs (do not guess endpoints), confirm licence/attribution terms, "
     "map fields to products/regions, then configure an http_json connector and set terms to 'permitted'."),
    ("cand_narxtahlil", "narxtahlil.uz — Central Bank price monitoring (candidate)", "official_statistics", "official_statistic",
     "https://narxtahlil.uz", None, None,
     "Central Bank price-monitoring site (reported launch Apr 2026) based on statistics data. Check for an API or "
     "downloads and the terms of reuse before integrating."),
    ("cand_b2b_market_uz", "B2B Market Uzbekistan (candidate)", "marketplace", "marketplace_listed",
     "https://b2bmarket.uz", None, None,
     "Commercial B2B marketplace (OOO B2BMARKET, Tashkent). No public API confirmed. Automated collection only with "
     "written permission or a partner feed; otherwise use supplier submissions / authorised imports."),
    ("cand_uzxarid", "Uzxarid / UZEX e-procurement (candidate)", "marketplace", "marketplace_listed",
     None, None, None,
     "Name from the brief; likely refers to the UZEX public procurement system (xarid.uzex.uz) — confirm. Procurement "
     "contract prices are a different price kind (tender results); check terms and data rights first."),
    ("cand_uzex_yarmarka", "UZEX B2B trading — yarmarka.uzex.uz (candidate)", "marketplace", "marketplace_listed",
     "https://yarmarka.uzex.uz", None, None,
     "Commodity exchange B2B trading platform. Investigate published trade results, API availability and terms."),
    ("cand_b2b_savdo", "B2B Savdo (candidate)", "marketplace", "marketplace_listed", None, None, None,
     "Named in the brief; the platform could not be confirmed during desk research. Locate the official site first."),
    ("cand_made_in_uz", "Made in Uzbekistan (candidate)", "marketplace", "marketplace_listed", None, None, None,
     "Named in the brief; several catalogues use this name (e.g. the cooperation.uz domestic-manufacturer portal). "
     "Identify the intended source and review its terms."),
]

SETTING_DESCRIPTIONS = {
    "ranking.weights": "Weights for 'best overall offer' (must sum to 1)",
    "ranking.max_distance_km": "Distance at which the proximity score reaches 0",
    "freshness.default_hours": "Default age after which an offer is shown as stale",
    "matching.auto_accept_threshold": "Product match confidence accepted automatically",
    "matching.review_threshold": "Below auto-accept and above this => human review",
    "analytics.mover_threshold_pct": "Minimum % change for 'significant' price movement",
    "analytics.mover_window_days": "Window length (days) for price movement comparison",
    "analytics.anomaly_z_threshold": "Robust z-score threshold for price anomalies",
    "analytics.min_points_for_forecast": "Minimum weekly points before a forecast is shown",
    "analytics.min_points_for_isolation_forest": "Observations per product required for IsolationForest",
    "data_quality.weights": "Weights of the data quality score components",
}

PLANS = [("free_buyer", "Free (buyer)", "buyer", {"saved_items": 50, "quote_requests_month": 20}),
         ("supplier_basic", "Supplier Basic", "supplier", {"active_offers": 50, "featured_offers": 0}),
         ("supplier_pro", "Supplier Pro", "supplier", {"active_offers": 1000, "featured_offers": 10}),
         ("analytics_premium", "Premium Market Intelligence", "buyer", {"advanced_analytics": True, "exports": True}),
         ("enterprise", "Enterprise", "enterprise", {"api_access": True, "sso": True})]


def seed_reference(db: Session) -> None:
    perms = {}
    for code, desc in PERMISSIONS.items():
        p = db.scalar(select(Permission).where(Permission.code == code)) or Permission(code=code)
        p.description = desc
        db.add(p)
        perms[code] = p
    db.flush()
    for code, (uz, ru, en, selfreg, plist) in ROLES.items():
        r = db.scalar(select(Role).where(Role.code == code))
        if r is None:
            r = Role(code=code, name_uz=uz, name_ru=ru, name_en=en, is_self_registrable=selfreg)
            r.permissions = [perms[x] for x in plist]
            db.add(r)
    for i, (code, uz, ru, en, lat, lng, aliases) in enumerate(REGIONS):
        if not db.scalar(select(Region).where(Region.code == code)):
            db.add(Region(code=code, name_uz=uz, name_ru=ru, name_en=en, center_lat=Decimal(str(lat)),
                          center_lng=Decimal(str(lng)), aliases=aliases, sort_order=i))
    db.flush()
    tk = db.scalar(select(Region).where(Region.code == "UZ-TK"))
    if not db.scalar(select(District).where(District.region_id == tk.id)):
        for uz, ru in TASHKENT_DISTRICTS:
            db.add(District(region_id=tk.id, name_uz=uz, name_ru=ru))
    for code, uz, ru, en, sym, dim, f, aliases in UNITS:
        if not db.scalar(select(Unit).where(Unit.code == code)):
            db.add(Unit(code=code, name_uz=uz, name_ru=ru, name_en=en, symbol=sym, dimension=dim,
                        factor_to_base=Decimal(f) if f else None, aliases=aliases))
    db.flush()
    units = {u.code: u for u in db.scalars(select(Unit)).all()}
    for i, (slug, uz, ru, en, icon, kw, attrs) in enumerate(CATEGORIES):
        if db.scalar(select(Category).where(Category.slug == slug)):
            continue
        c = Category(slug=slug, name_uz=uz, name_ru=ru, name_en=en, icon=icon, keywords=kw, sort_order=i,
                     requires_compliance_note=slug == "medical", compliance_note=MEDICAL_NOTE if slug == "medical" else None,
                     freshness_hours=24 if slug == "food" else None)
        for j, a in enumerate(attrs):
            ca = CategoryAttribute(code=a["code"], name_uz=a["name_uz"], name_ru=a["name_ru"], name_en=a["name_en"],
                                   data_type=a["data_type"], is_required=a["is_required"], is_filterable=a["is_filterable"],
                                   is_matching_key=a["is_matching_key"], sort_order=j,
                                   unit_id=units[a["unit"]].id if a["unit"] else None)
            ca.options = [AttributeOption(value=v, label_uz=lu, label_ru=lr, sort_order=k) for k, (v, lu, lr) in enumerate(a["options"])]
            c.attributes.append(ca)
        db.add(c)
    for code, name, typ, prov, rel, fresh, active, terms, notes in DATA_SOURCES:
        if not db.scalar(select(DataSource).where(DataSource.code == code)):
            ds = DataSource(code=code, name=name, source_type=typ, default_provenance=prov, reliability_score=Decimal(rel),
                            freshness_hours=fresh, is_active=active, terms_status=terms, review_notes=notes)
            db.add(ds)
            db.flush()
            ctype = {"supplier_submission": "supplier_submission", "manual": "manual_entry", "file_import": "file_import"}[typ]
            db.add(DataConnector(data_source_id=ds.id, name=f"{name} connector", connector_type=ctype, is_enabled=True,
                                 config={"default_record_type": "observation"} if ctype == "file_import" else {}))
    for code, name, typ, prov, url, api_, auth, notes in CANDIDATE_SOURCES:
        if not db.scalar(select(DataSource).where(DataSource.code == code)):
            db.add(DataSource(code=code, name=name, source_type=typ, default_provenance=prov, base_url=url,
                              has_public_api=api_, requires_auth=auth, reliability_score=Decimal("0.5"),
                              freshness_hours=168 if typ == "official_statistics" else 72, is_active=False,
                              terms_status="pending_review" if url else "unknown",
                              review_notes=notes + " NOT integrated. See docs/DATA_SOURCES.md."))
    for key, val in FALLBACKS.items():
        if not db.get(PlatformSetting, key):
            db.add(PlatformSetting(key=key, value=val, description=SETTING_DESCRIPTIONS.get(key)))
    for code, name, aud, feats in PLANS:
        if not db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code)):
            db.add(SubscriptionPlan(code=code, name=name, audience=aud, features=feats))
    db.flush()

    # Fix-up: earlier builds used the special-use ".local" domain for demo accounts, which email validation rejects.
    for u in db.scalars(select(User).where(User.email.like("%@demo.tradeflow.local"))).all():
        u.email = u.email.replace("@demo.tradeflow.local", "@demo.example.com")
    db.flush()

    s = get_settings()
    if s.bootstrap_admin_password and not db.scalar(select(User).where(User.email == s.bootstrap_admin_email)):
        role = db.scalar(select(Role).where(Role.code == "super_admin"))
        u = User(email=s.bootstrap_admin_email, password_hash=hash_password(s.bootstrap_admin_password),
                 full_name="Platform Administrator", role_id=role.id, locale="uz")
        org = Organization(name="TradeFlow Platform", org_type="platform")
        db.add_all([u, org])
        db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=u.id, member_role="owner"))
    db.commit()
