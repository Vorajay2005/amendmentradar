"""Optional browser smoke test of the React UI (server must be running: make run).

Setup (not in requirements.txt): pip install playwright && playwright install chromium
Run: python scripts/e2e_smoke.py [http://localhost:8000]
"""
import asyncio, sys
from playwright.async_api import async_playwright
B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1366, "height": 650}); pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        # 1 demo example click -> results above the fold
        await pg.goto(B + "/analyze"); await pg.wait_for_timeout(800)
        await pg.get_by_role("button", name="Retrospective hit").click(); await pg.wait_for_url("**/results?nct=NCT03827850"); await pg.wait_for_timeout(2200)
        vh = 650
        for sel, name in [("text=Upper third", "risk band"), ("text=of the 25", "X of 25")]:
            bb = await pg.locator(sel).first.bounding_box(); ok(bb and bb["y"] + bb["height"] < vh, f"{name} visible without scrolling (y={bb['y']:.0f})")
        cards = pg.locator("a:has-text('started')") ; 
        links = pg.locator("ul.grid >> nth=0").locator("li")
        n = await links.count(); bbs = [await links.nth(i).bounding_box() for i in range(min(n,3))]
        ok(n >= 3 and all(x["y"] + x["height"] <= vh + 2 for x in bbs), f"top 3 similar cards fully above fold (bottoms {[round(x['y']+x['height']) for x in bbs]})")
        ok(await pg.locator("a[href^='https://clinicaltrials.gov/study/NCT']").count() >= 5, "similar trials link to ClinicalTrials.gov")
        # 2 invalid NCT validated client-side
        await pg.goto(B + "/analyze"); await pg.fill("#nct", "banana"); await pg.keyboard.press("Enter")
        ok(await pg.locator("#nct-err").is_visible(), "invalid NCT shows inline error, no navigation")
        # 3 not-found via live API (valid format, unlikely to exist)
        await pg.goto(B + "/results?nct=NCT00000001"); await pg.wait_for_timeout(2500)
        t = await pg.locator("[role=alert]").first.inner_text(); print("   not-found/other state:", t.replace("\n"," | ")[:140])
        ok("not found" in t.lower() or "can't reach" in t.lower() or "wrong" in t.lower(), "unknown NCT gives a friendly error state")
        # 4 manual form
        await pg.goto(B + "/analyze"); await pg.get_by_role("tab", name="Manual design").click()
        await pg.fill("#conds", ""); await pg.get_by_role("button", name="Analyze this design").click()
        ok(await pg.get_by_role("alert").filter(has_text="at least one condition").is_visible(), "manual form validates empty condition")
        await pg.fill("#conds", "asthma"); await pg.get_by_role("button", name="Analyze this design").click(); await pg.wait_for_url("**/results?manual=1"); await pg.wait_for_timeout(2200)
        ok(await pg.get_by_text("Manual design").first.is_visible() and await pg.locator("text=of the 25").count() > 0, "manual design produces results")
        # 5 not-yet-recruiting example
        await pg.goto(B + "/results?nct=NCT06964230"); await pg.wait_for_timeout(2500)
        ok(await pg.locator("text=Not yet recruiting").count() > 0, "not-yet-recruiting example shows its status")
        # 6 theme toggle persists
        await pg.get_by_role("button", name="Switch to dark theme").click(); await pg.reload(); await pg.wait_for_timeout(600)
        ok(await pg.evaluate("document.documentElement.classList.contains('dark')"), "dark theme persists after reload")
        # 7 deep link + SPA fallback
        r = await pg.goto(B + "/dashboard"); ok(r.status == 200, "deep link /dashboard served")
        # 8 API down -> friendly state
        await pg.route("**/api/analyze", lambda route: route.abort()); await pg.goto(B + "/results?nct=NCT03827850"); await pg.wait_for_timeout(1500)
        ok("reach" in (await pg.locator("[role=alert]").first.inner_text()).lower(), "server down gives friendly offline state with retry")
        # 9 mobile
        m = await b.new_context(viewport={"width": 375, "height": 812}); mp = await m.new_page()
        for path in ["/", "/analyze", "/results?nct=NCT03827850", "/dashboard", "/about"]:
            await mp.goto(B + path); await mp.wait_for_timeout(1800)
            ok(not await mp.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), f"375px no horizontal overflow {path}")
        ok(not errs, f"no uncaught JS errors {errs[:2]}")
        await b.close()
asyncio.run(main())
