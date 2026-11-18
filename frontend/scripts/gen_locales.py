"""Regenerate src/locales/{en,ru,uz}.ts from scripts/i18n_strings.py so the three languages
always share exactly the same keys. Usage: python scripts/gen_locales.py"""
import json
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from i18n_strings import S  # noqa: E402

out = here.parent / "src" / "locales"
for i, lang in enumerate(["en", "ru", "uz"]):
    d = {k: v[i] for k, v in S.items()}
    (out / f"{lang}.ts").write_text(
        f"// {lang.upper()} translations. Keys are shared across uz / ru / en (generated from one table to stay in sync).\n"
        "const dict: Record<string, string> = " + json.dumps(d, ensure_ascii=False, indent=2) + ";\nexport default dict;\n",
        encoding="utf-8",
    )
print(f"{len(S)} keys written")
