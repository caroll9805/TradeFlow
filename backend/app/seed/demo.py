"""SIMULATED demo dataset.

Every record created here is flagged is_simulated=True, tied to the 'simulated_demo' data source
with provenance 'simulated', and supplier names are prefixed with [DEMO]. Nothing here is real
market information. Remove it any time via Admin → Demo data → Purge (or DELETE /api/admin/demo-data).
Demo suppliers are deliberately left unverified — verification must be done by an admin."""
import random
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Category,
    DataSource,
    ExchangeRate,
    Manufacturer,
    Offer,
    Organization,
    OrganizationMember,
    PriceObservation,
    Product,
    ProductAttributeValue,
    QuoteRequest,
    Region,
    Role,
    SearchEvent,
    Supplier,
    SupplierLocation,
    Unit,
    UnitConversion,
    User,
)
from app.models.base import utcnow
from app.services.pricing import normalize_price
from app.services.text import normalize_text

DEMO_PASSWORD = "Demo12345!"
DAYS = 120

# name, category, base unit, price per base unit (UZS, simulated), extra units {unit: base units per unit},
# search terms, attributes {code: value}, trend (% over period), origin
P = [
    ("Granulated sugar, 50 kg bag", "food", "kg", 12500, {"bag": 50, "t": 1000}, ["shakar", "сахар", "sugar"], {"net_weight": 50, "packaging": "bag"}, 14, "import"),
    ("Wheat flour, premium grade, 50 kg", "food", "kg", 6200, {"bag": 50, "t": 1000}, ["un", "мука", "flour", "bug'doy uni"], {"net_weight": 50, "packaging": "bag"}, 6, "domestic"),
    ("Sunflower oil, refined, 5 L", "food", "l", 21500, {"piece": 5}, ["kungaboqar yog'i", "yog'", "подсолнечное масло", "масло"], {"packaging": "bottle"}, -4, "domestic"),
    ("Rice Devzira, 1 kg", "food", "kg", 26000, {"bag": 25}, ["guruch", "рис", "devzira"], {"packaging": "bag"}, 9, "domestic"),
    ("Black tea, 100 g pack", "food", "piece", 14500, {"box": 24}, ["choy", "чай", "qora choy"], {"packaging": "box"}, 0, "import"),
    ("LED TV 43\" DemoTech DT-43F", "electronics", "piece", 3850000, {}, ["televizor", "телевизор", "tv"], {"brand": "DemoTech", "model": "DT-43F", "warranty_months": 12, "condition": "new"}, -7, "import"),
    ("Refrigerator 300 L Frostline FL-300", "electronics", "piece", 5200000, {}, ["muzlatgich", "холодильник"], {"brand": "Frostline", "model": "FL-300", "warranty_months": 24, "condition": "new"}, 3, "domestic"),
    ("Air conditioner 12000 BTU Breezo BZ-12", "electronics", "piece", 4550000, {}, ["konditsioner", "кондиционер"], {"brand": "Breezo", "model": "BZ-12", "warranty_months": 24, "condition": "new"}, 11, "domestic"),
    ("Smartphone 128 GB Nova N5", "electronics", "piece", 2650000, {}, ["smartfon", "смартфон", "telefon"], {"brand": "Nova", "model": "N5", "warranty_months": 12, "condition": "new"}, -9, "import"),
    ("Cotton fabric (coarse calico), 220 cm", "textiles", "m", 18500, {}, ["mato", "ткань", "bo'z", "бязь"], {"material": "cotton"}, 5, "domestic"),
    ("Men's leather shoes, size 42", "textiles", "piece", 380000, {"box": 10}, ["poyabzal", "обувь", "туфли"], {"material": "leather", "size": "42", "gender": "men"}, 0, "domestic"),
    ("Cotton T-shirt, unisex", "textiles", "piece", 46000, {"box": 50}, ["futbolka", "футболка"], {"material": "cotton", "gender": "unisex", "size": "M-XL"}, 2, "domestic"),
    ("Shampoo 400 ml Silka", "cosmetics", "piece", 32000, {"box": 12}, ["shampun", "шампунь"], {"brand": "Silka", "volume_ml": 400}, 4, "domestic"),
    ("Perfume 50 ml Aura Demo", "cosmetics", "piece", 255000, {}, ["atir", "духи", "парфюм"], {"brand": "Aura Demo", "volume_ml": 50}, 0, "import"),
    ("Hand cream 75 ml", "cosmetics", "piece", 18500, {"box": 24}, ["krem", "крем"], {"brand": "Silka", "volume_ml": 75}, 1, "domestic"),
    ("Portland cement M400, 50 kg", "construction", "kg", 1500, {"bag": 50, "t": 1000}, ["sement", "цемент", "cement", "portlandsement", "портландцемент"], {"material_type": "cement", "grade": "M400"}, 12, "domestic"),
    ("Portland cement M500, 50 kg", "construction", "kg", 1760, {"bag": 50, "t": 1000}, ["sement m500", "цемент м500", "cement"], {"material_type": "cement", "grade": "M500"}, 9, "domestic"),
    ("Rebar A500C, 12 mm", "construction", "kg", 9600, {"t": 1000}, ["armatura", "арматура", "rebar"], {"material_type": "rebar", "grade": "A500C", "dimensions": "12 mm"}, -6, "domestic"),
    ("Ceramic brick M100", "construction", "piece", 1300, {"pallet": 300}, ["g'isht", "gisht", "кирпич", "brick"], {"material_type": "brick", "grade": "M100"}, 7, "domestic"),
    ("Gypsum plasterboard 12.5 mm", "construction", "m2", 15500, {"piece": 3}, ["gipsokarton", "гипсокартон"], {"material_type": "plasterboard", "dimensions": "2500x1200x12.5"}, 0, "domestic"),
    ("HDPE polyethylene granules", "industrial", "kg", 16200, {"bag": 25, "t": 1000}, ["polietilen", "полиэтилен", "granula", "гранулы"], {"material_type": "HDPE", "grade": "film"}, 8, "domestic"),
    ("Caustic soda flakes 99%", "industrial", "kg", 9100, {"bag": 25, "t": 1000}, ["kaustik soda", "каустическая сода"], {"material_type": "NaOH", "purity_pct": 99}, -3, "import"),
    ("Copper wire 2.5 mm²", "industrial", "m", 6600, {}, ["mis sim", "медный провод", "kabel", "кабель"], {"material_type": "copper wire", "grade": "2.5 mm2"}, 10, "domestic"),
    ("Ergonomic office chair", "furniture", "piece", 950000, {}, ["stul", "кресло", "стул"], {"material": "mesh/steel", "assembly_required": True}, 0, "import"),
    ("Wardrobe, 2-door, 180 cm", "furniture", "piece", 2100000, {}, ["shkaf", "шкаф"], {"material": "LDSP", "dimensions": "180x90x55", "assembly_required": True}, 4, "domestic"),
    ("Dining table 120x80", "furniture", "piece", 1300000, {}, ["stol", "стол"], {"material": "wood", "dimensions": "120x80x75", "assembly_required": False}, 0, "domestic"),
    ("Front brake pads set (Cobalt / Lacetti)", "auto-parts", "set", 185000, {}, ["tormoz kolodka", "тормозные колодки"], {"part_number": "DEMO-BP-1201", "vehicle_compatibility": "Chevrolet Cobalt, Lacetti", "condition": "new"}, 5, "import"),
    ("Engine oil 5W-30, 4 L", "auto-parts", "l", 70000, {"piece": 4}, ["motor moyi", "моторное масло"], {"part_number": "DEMO-OIL-5W30", "condition": "new"}, 6, "import"),
    ("Car battery 60 Ah", "auto-parts", "piece", 960000, {}, ["akkumulyator", "аккумулятор"], {"part_number": "DEMO-BAT-60", "condition": "new"}, -2, "domestic"),
    ("A4 office paper 80 g/m², 500 sheets", "office", "pack", 56000, {"box": 5}, ["qog'oz", "бумага", "a4"], {"format": "A4", "pack_count": 500}, 3, "import"),
    ("Ballpoint pen, blue", "office", "piece", 1500, {"box": 50}, ["ruchka", "ручка"], {"format": "0.7 mm"}, 0, "import"),
    ("Potatoes, food grade", "agriculture", "kg", 4600, {"t": 1000, "bag": 30}, ["kartoshka", "картофель"], {"crop_or_type": "potato", "grade": "1"}, -18, "domestic"),
    ("Onion, yellow", "agriculture", "kg", 3100, {"t": 1000, "bag": 25}, ["piyoz", "лук"], {"crop_or_type": "onion", "grade": "1"}, 22, "domestic"),
    ("Ammonium nitrate fertilizer", "agriculture", "kg", 3800, {"bag": 50, "t": 1000}, ["ammiakli selitra", "селитра", "o'g'it", "удобрение"], {"crop_or_type": "fertilizer"}, 4, "domestic"),
    ("Drip irrigation tape 16 mm", "agriculture", "m", 720, {}, ["tomchilatib sug'orish", "капельная лента"], {"crop_or_type": "irrigation"}, 0, "domestic"),
    ("Medical face masks, 3-ply", "medical", "piece", 620, {"box": 50}, ["niqob", "маска"], {"registration_number": "DEMO-REG-0001", "sterile": False}, -5, "domestic"),
    ("Nitrile examination gloves", "medical", "piece", 900, {"box": 100}, ["qo'lqop", "перчатки"], {"registration_number": "DEMO-REG-0002", "sterile": False}, 2, "import"),
    ("Disposable syringe 5 ml", "medical", "piece", 820, {"box": 100}, ["shprits", "шприц"], {"registration_number": "DEMO-REG-0003", "sterile": True}, 0, "domestic"),
    ("PET preform 28 g", "packaging", "piece", 650, {"box": 1000}, ["preforma", "преформа"], {"material": "pet", "capacity": "28 g"}, 7, "domestic"),
    ("Corrugated box 40x30x30", "packaging", "piece", 7600, {"pallet": 200}, ["karton quti", "гофрокороб", "коробка"], {"material": "cardboard", "capacity": "40x30x30"}, 3, "domestic"),
    ("Stretch film 23 µm, 500 mm", "packaging", "kg", 26500, {"piece": 2}, ["strech plyonka", "стрейч плёнка"], {"material": "film", "thickness_mic": 23}, 5, "domestic"),
    ("Laundry detergent powder 3 kg", "other", "kg", 15200, {"piece": 3}, ["kir yuvish kukuni", "стиральный порошок"], {"brand": "Tozа Demo"}, 2, "domestic"),
]

# Fictional supplier names; [DEMO] prefix makes them unmistakable.
S = [
    ("Toshkent Qurilish Savdo", "UZ-TK", "wholesaler", ["construction", "industrial"]),
    ("Chilonzor Oziq-Ovqat Ulgurji", "UZ-TK", "wholesaler", ["food", "other"]),
    ("Capital Electronics Import", "UZ-TK", "importer", ["electronics", "office"]),
    ("Sergeli Avto Detal", "UZ-TK", "distributor", ["auto-parts"]),
    ("Yunusobod Mebel Fabrikasi", "UZ-TK", "manufacturer", ["furniture"]),
    ("MedTa'minot Tashkent", "UZ-TK", "distributor", ["medical"]),
    ("Angren Sement Distribyutor", "UZ-TO", "distributor", ["construction"]),
    ("Chirchiq Kimyo Savdo", "UZ-TO", "wholesaler", ["industrial", "agriculture"]),
    ("Olmaliq Metall Ta'minot", "UZ-TO", "wholesaler", ["construction", "industrial"]),
    ("Samarqand Don Mahsulotlari", "UZ-SA", "manufacturer", ["food", "agriculture"]),
    ("Registon Tekstil", "UZ-SA", "manufacturer", ["textiles"]),
    ("Samarqand Qurilish Bozori", "UZ-SA", "wholesaler", ["construction"]),
    ("Buxoro Paxta Mato", "UZ-BU", "manufacturer", ["textiles"]),
    ("Buxoro Oziq Savdo", "UZ-BU", "wholesaler", ["food", "other"]),
    ("Andijon Avto Komponent", "UZ-AN", "manufacturer", ["auto-parts"]),
    ("Asaka Elektro Savdo", "UZ-AN", "distributor", ["electronics"]),
    ("Farg'ona Kosmetika", "UZ-FA", "manufacturer", ["cosmetics"]),
    ("Qo'qon Qadoq Plast", "UZ-FA", "manufacturer", ["packaging", "industrial"]),
    ("Namangan Shirinlik va Oziq", "UZ-NG", "wholesaler", ["food"]),
    ("Namangan Mebel Uyi", "UZ-NG", "manufacturer", ["furniture"]),
    ("Jizzax Agro Ta'minot", "UZ-JI", "wholesaler", ["agriculture", "food"]),
    ("Qarshi Qurilish Materiallari", "UZ-QA", "wholesaler", ["construction"]),
    ("Termiz Savdo Markazi", "UZ-SU", "wholesaler", ["food", "office", "other"]),
    ("Navoiy Sanoat Xomashyo", "UZ-NW", "manufacturer", ["industrial", "construction"]),
    ("Urganch Elektronika", "UZ-XO", "retail", ["electronics", "cosmetics"]),
    ("Xorazm Agro Fermer", "UZ-XO", "manufacturer", ["agriculture"]),
    ("Guliston Paxta Tola", "UZ-SI", "manufacturer", ["textiles", "agriculture"]),
    ("Nukus Universal Ta'minot", "UZ-QR", "wholesaler", ["food", "construction", "medical"]),
    ("Fergana Pharm Distribution", "UZ-FA", "distributor", ["medical", "cosmetics"]),
    ("Office Pro Tashkent", "UZ-TK", "distributor", ["office", "packaging"]),
]

# Simulated regional price level (multiplier) — arbitrary, for demo only.
REGION_LEVEL = {"UZ-TK": 1.0, "UZ-TO": 0.97, "UZ-SA": 0.98, "UZ-BU": 1.02, "UZ-AN": 0.99, "UZ-FA": 0.98, "UZ-NG": 1.0,
                "UZ-JI": 0.99, "UZ-QA": 1.03, "UZ-SU": 1.06, "UZ-NW": 1.01, "UZ-XO": 1.07, "UZ-SI": 0.99, "UZ-QR": 1.09}


def q2(x: float) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def nice_price(x: float) -> Decimal:
    if x >= 100000:
        return q2(round(x / 1000) * 1000)
    if x >= 1000:
        return q2(round(x / 50) * 50)
    return q2(round(x, 2))


def seed_demo(db: Session, seed: int = 42) -> dict:
    if db.scalar(select(DataSource).where(DataSource.code == "simulated_demo")):
        return {"status": "already_seeded"}
    rnd = random.Random(seed)
    now = utcnow()
    ds = DataSource(code="simulated_demo", name="SIMULATED demo dataset", source_type="simulated",
                    default_provenance="simulated", reliability_score=Decimal("0.5"), freshness_hours=168,
                    is_active=True, terms_status="permitted", is_simulated=True,
                    review_notes="Synthetic data generated by app/seed/demo.py for demonstrations. Not real market data.")
    db.add(ds)
    db.add(ExchangeRate(currency="USD", rate_to_uzs=Decimal("12800"), as_of=now - timedelta(days=DAYS + 5),
                        source="SIMULATED demo rate — replace with the official Central Bank of Uzbekistan rate"))
    db.flush()
    regions = {r.code: r for r in db.scalars(select(Region)).all()}
    units = {u.code: u for u in db.scalars(select(Unit)).all()}
    cats = {c.slug: c for c in db.scalars(select(Category)).unique().all()}
    mfr = Manufacturer(name="[DEMO] Generic Manufacturer", country_code="UZ", is_simulated=True)
    db.add(mfr)

    # --- demo accounts (credentials documented in README; demo only)
    roles = {r.code: r for r in db.scalars(select(Role)).all()}
    accounts = {}
    for email, name, role, org_name, org_type in [
        ("buyer@demo.example.com", "Demo Buyer", "buyer", "[DEMO] Buyer Company LLC", "buyer"),
        ("supplier@demo.example.com", "Demo Supplier", "supplier", "[DEMO] Toshkent Qurilish Savdo", "supplier"),
        ("data@demo.example.com", "Demo Data Admin", "market_data_admin", "[DEMO] TradeFlow Data Team", "platform"),
        ("admin@demo.example.com", "Demo Super Admin", "super_admin", "[DEMO] TradeFlow Platform", "platform"),
    ]:
        if db.scalar(select(User).where(User.email == email)):
            continue
        u = User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD), role_id=roles[role].id, locale="uz")
        org = Organization(name=org_name, org_type=org_type, is_simulated=True, region_id=regions["UZ-TK"].id)
        db.add_all([u, org])
        db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=u.id))
        accounts[role] = (u, org)

    # --- suppliers
    suppliers: list[Supplier] = []
    for i, (name, rcode, stype, cslugs) in enumerate(S):
        org_id = accounts["supplier"][1].id if (i == 0 and "supplier" in accounts) else None
        if org_id is None:
            org = Organization(name=f"[DEMO] {name}", org_type="manufacturer" if stype == "manufacturer" else "supplier",
                               is_simulated=True, region_id=regions[rcode].id)
            db.add(org)
            db.flush()
            org_id = org.id
        s = Supplier(organization_id=org_id, name=f"[DEMO] {name}", supplier_type=stype, region_id=regions[rcode].id,
                     description="Simulated supplier profile for demonstration purposes.",
                     verification_status="pending" if i % 7 == 3 else "unverified", data_source_id=ds.id,
                     phone=None, email=None, is_simulated=True)
        s.categories = [cats[c] for c in cslugs]
        s.locations = [SupplierLocation(kind="warehouse", name="Main warehouse", region_id=regions[rcode].id)]
        db.add(s)
        suppliers.append(s)
    db.flush()
    # A few simulated ratings make the reliability criterion visible (clearly demo).
    for s in suppliers:
        if rnd.random() < 0.6:
            s.rating_avg = q2(rnd.uniform(3.2, 4.9))
            s.rating_count = rnd.randint(2, 30)

    # --- products, conversions, offers, history
    n_offers = n_obs = 0
    products = []
    for name, cslug, base, price, extra_units, terms, attrs, trend, origin in P:
        cat = cats[cslug]
        prod = Product(name=name, normalized_name=normalize_text(name), category_id=cat.id, base_unit_id=units[base].id,
                       search_terms=terms, origin_type=origin, country_of_origin="UZ" if origin == "domestic" else None,
                       brand=attrs.get("brand"), model=attrs.get("model"), manufacturer_id=None, status="active",
                       description="Simulated catalog entry for demonstration.", is_simulated=True)
        db.add(prod)
        db.flush()
        defs = {a.code: a for a in cat.attributes}
        for code, val in attrs.items():
            a = defs.get(code)
            if not a:
                continue
            pav = ProductAttributeValue(product_id=prod.id, attribute_id=a.id)
            if a.data_type == "number":
                pav.value_number = Decimal(str(val))
            elif a.data_type == "boolean":
                pav.value_bool = bool(val)
            elif a.data_type == "multiselect":
                pav.value_json = [val]
            else:
                pav.value_text = str(val)
            db.add(pav)
        for ucode, factor in extra_units.items():
            if units[ucode].dimension == "package" or units[ucode].dimension != units[base].dimension:
                db.add(UnitConversion(product_id=prod.id, from_unit_id=units[ucode].id, to_unit_id=units[base].id,
                                      factor=Decimal(str(factor))))
        db.flush()
        db.refresh(prod)
        products.append(prod)

        cands = [s for s in suppliers if cat in s.categories]
        chosen = rnd.sample(cands, k=min(len(cands), rnd.randint(3, 6)))
        # one product gets a stale offer, one an anomaly
        for s in chosen:
            region = s.region
            level = REGION_LEVEL[region.code] * rnd.uniform(0.92, 1.1)
            offer_units = [base] + [u for u in extra_units if rnd.random() < 0.6]
            ucode = rnd.choice(offer_units)
            factor = Decimal(1) if ucode == base else Decimal(str(extra_units[ucode]))
            currency = "USD" if (cslug == "electronics" and rnd.random() < 0.3) else "UZS"
            ptype = "retail" if (s.supplier_type == "retail" or rnd.random() < 0.12) else "wholesale"
            if ptype == "retail":
                level *= 1.12
            stale = rnd.random() < 0.12
            last_day = rnd.randint(8, 20) if stale else rnd.randint(0, 3)
            offer = Offer(supplier_id=s.id, product_id=prod.id, region_id=region.id, price_type=ptype,
                          original_price=Decimal(1), original_currency=currency, unit_id=units[ucode].id,
                          price_uzs=Decimal(1), data_source_id=ds.id, provenance_kind="simulated", is_simulated=True,
                          original_product_name=name, verification_status="unverified",
                          moq=Decimal(rnd.choice([1, 1, 5, 10, 20, 50])) if ucode != "t" else Decimal(rnd.choice([1, 5])),
                          available_qty=Decimal(rnd.choice([20, 50, 100, 300, 800, 2000])) if rnd.random() < 0.8 else None,
                          delivery_available=rnd.random() < 0.65)
            if offer.delivery_available:
                offer.delivery_cost_uzs = q2(rnd.choice([0, 50000, 100000, 150000, 250000, 400000])) if rnd.random() < 0.8 else None
                offer.delivery_regions = [] if rnd.random() < 0.5 else [rid for rid in rnd.sample(
                    [r.id for r in regions.values()], k=rnd.randint(2, 8))] + [region.id]
            db.add(offer)
            db.flush()
            # history
            obs_days = sorted({rnd.randint(last_day, DAYS) for _ in range(rnd.randint(6, 14))} | {last_day}, reverse=True)
            last_price = None
            for d in obs_days:
                t = (DAYS - d) / DAYS
                base_px = price * level * (1 + trend / 100 * t) * rnd.uniform(0.985, 1.015)
                if rnd.random() < 0.015:  # rare simulated anomaly
                    base_px *= rnd.choice([1.7, 0.55])
                unit_px_uzs = base_px * float(factor)
                original = nice_price(unit_px_uzs / 12800 if currency == "USD" else unit_px_uzs)
                at = now - timedelta(days=d, hours=rnd.randint(0, 20))
                rate = Decimal("12800") if currency == "USD" else None
                p_uzs = q2(float(original) * 12800) if currency == "USD" else original
                per_base, f = normalize_price(db, prod, units[ucode], p_uzs)
                db.add(PriceObservation(
                    product_id=prod.id, supplier_id=s.id, offer_id=offer.id, original_product_name=name,
                    original_price=original, original_currency=currency, original_unit_text=ucode, unit_id=units[ucode].id,
                    exchange_rate=rate, price_uzs=p_uzs, normalized_price_uzs=per_base,
                    normalized_unit_id=prod.base_unit_id if per_base is not None else None, region_id=region.id,
                    price_type=ptype, provenance_kind="simulated", data_source_id=ds.id, collection_method="seed",
                    observed_at=at, collected_at=at, verification_status="unverified", quality_score=Decimal("0.6"),
                    quality_flags=["simulated"], is_simulated=True))
                n_obs += 1
                last_price = (original, p_uzs, per_base, f, at, rate)
            original, p_uzs, per_base, f, at, rate = last_price
            offer.original_price, offer.price_uzs, offer.price_per_base_unit_uzs = original, p_uzs, per_base
            offer.units_per_offer_unit, offer.price_updated_at = f, at
            offer.exchange_rate, offer.exchange_rate_at = rate, (now - timedelta(days=DAYS + 5)) if rate else None
            offer.valid_until = now + timedelta(days=rnd.choice([14, 30, 60])) if rnd.random() < 0.7 else None
            n_offers += 1
        db.flush()

    # simulated activity signals (search interest / quote requests) — labelled via the data they attach to
    if "buyer" in accounts:
        bu, borg = accounts["buyer"]
        for prod in rnd.sample(products, k=8):
            for _ in range(rnd.randint(1, 12)):
                db.add(SearchEvent(query=f"demo:{prod.name}", product_id=prod.id, category_id=prod.category_id,
                                   created_at=now - timedelta(days=rnd.randint(0, 29))))
        cement = next(p for p in products if p.name.startswith("Portland cement M400"))
        sup = next(s for s in suppliers if s.name.endswith("Toshkent Qurilish Savdo"))
        db.add(QuoteRequest(buyer_organization_id=borg.id, requested_by_id=bu.id, product_id=cement.id, supplier_id=sup.id,
                            quantity=Decimal(200), unit_id=units["bag"].id, delivery_region_id=regions["UZ-TK"].id,
                            message="[DEMO] Please quote 200 bags delivered to Chilonzor."))
    db.commit()
    return {"status": "seeded", "products": len(products), "suppliers": len(suppliers), "offers": n_offers,
            "observations": n_obs}
