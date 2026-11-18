import { describe, expect, it } from "vitest";
import { fmtNum, fmtPct, fmtUZS, toNum } from "@/lib/format";
import { ApiError, qs } from "@/lib/api";
import en from "@/locales/en";
import ru from "@/locales/ru";
import uz from "@/locales/uz";
import { translate } from "@/lib/i18n";

describe("format", () => {
  it("formats numbers and UZS with grouping", () => {
    expect(fmtNum(1500000, "en")).toBe("1 500 000");
    expect(fmtUZS("75000.00", "ru")).toBe("75 000 сум");
    expect(fmtUZS(null)).toBe("—");
    expect(toNum("abc")).toBeNull();
    expect(fmtPct(12.345)).toBe("+12.3%");
    expect(fmtPct(-3)).toBe("-3.0%");
  });
});

describe("api helpers", () => {
  it("builds query strings without empty values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: false, e: null })).toBe("?a=1&d=false");
    expect(qs({})).toBe("");
  });
  it("turns FastAPI validation errors into readable messages", () => {
    const e = new ApiError(422, [{ loc: ["body", "price"], msg: "must be greater than 0" }]);
    expect(e.message).toBe("price: must be greater than 0");
  });
});

describe("i18n", () => {
  it("has identical keys in uz, ru and en", () => {
    const k = (d: Record<string, string>) => Object.keys(d).sort();
    expect(k(uz)).toEqual(k(en));
    expect(k(ru)).toEqual(k(en));
    expect(Object.values(uz).every((v) => v.length > 0)).toBe(true);
  });
  it("interpolates variables and falls back to the key", () => {
    expect(translate("en", "catalog.offersN", { n: 3 })).toBe("3 offers");
    expect(translate("ru", "missing.key")).toBe("missing.key");
  });
});
