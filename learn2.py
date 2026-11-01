"""
Magic Professor — round 2: check real-world deck-building advice per format.

Uses engine2.py (mana sinks, bombs, card-advantage creatures, counterspells,
board wipes, tokens + sac outlets, a commander, free mulligan, format life
totals) and format deck rules (4-copy limit in 60-card, singleton combo pieces
in Brawl/Commander).

Formats tested (the ones Jon plays):
  draft40   Limited, 40 cards, 20 life
  con60     Constructed, 60 cards, 20 life, max 4 copies of a named card
  brawl     Arena Brawl: 99 + commander, 25 life, free first mulligan, singleton
  sbrawl    Standard Brawl: 59 + commander, 25 life, free first mulligan, singleton
  cmdr1v1   Commander rules (99 + commander, 40 life) played 1v1

Expert advice it is checked against is in REAL_ADVICE below (sources in LESSONS.md).

Run:  python3 learn2.py   [--quick]      -> results/results2.json
"""
import json, os, random, sys, time
from multiprocessing import Pool, cpu_count
from engine2 import CARDS, COST, match
from learn import scale, build

CORES = cpu_count()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

REAL_ADVICE = {
    "draft40": "17 lands default; 16 if few cards above 3 mana; 18 for high curve / mana sinks (Draftsim, Karsten)",
    "con60": "about 24 lands (40%); aggro 20-22, control 26-28; Karsten: 19.59 + 1.90 x avg MV - 0.28 per cheap draw/ramp",
    "brawl": "Commander-style template: 36-38 lands, 8-12 ramp, 10-12 draw, 8-10 removal, 2-3 wipes",
    "sbrawl": "sample Standard Brawl lists run 24-26 lands",
    "cmdr1v1": "36-38 lands; Karsten 99-card: 31.42 + 3.13 x avg MV - 0.28 per cheap draw/ramp",
}

FORMATS = {
    "draft40": {"size": 40, "kw": {"life": 20}},
    "con60":   {"size": 60, "kw": {"life": 20}},
    "brawl":   {"size": 99, "kw": {"life": 25, "commander": True, "free_mull": True, "max_turns": 40}},
    "sbrawl":  {"size": 59, "kw": {"life": 25, "commander": True, "free_mull": True, "max_turns": 40}},
    "cmdr1v1": {"size": 99, "kw": {"life": 40, "commander": True, "max_turns": 45}},
}

# copy caps on cards that stand for ONE named card (generic C2 etc. stand for many)
CAPS = {
    "draft40": {},
    "con60": {"K1": 4, "K2": 4, "B5": 4, "T2": 4},
    "brawl": {"K1": 1, "K2": 1, "T2": 5, "SO": 6, "B5": 8},
    "sbrawl": {"K1": 1, "K2": 1, "T2": 3, "SO": 4, "B5": 5},
    "cmdr1v1": {"K1": 1, "K2": 1, "T2": 5, "SO": 6, "B5": 8},
}

FIELD40 = {
    "aggro":       {"L": 16, "C1": 3, "C2": 7, "C3": 5, "C4": 2, "V3": 1, "R2": 3, "TK": 1, "F3": 2},
    "midrange":    {"L": 17, "C2": 4, "C3": 3, "V3": 2, "C4": 3, "C5": 2, "B5": 1, "S3": 2, "F3": 2, "R2": 2, "R4": 2},
    "control":     {"L": 17, "C2": 2, "S3": 2, "V3": 2, "C4": 2, "C5": 2, "C6": 2, "B5": 1, "R2": 3, "R4": 3, "X2": 2, "W4": 1, "D3": 1},
    "flyers":      {"L": 16, "C2": 6, "F3": 7, "V3": 2, "C3": 2, "C4": 1, "R2": 4, "B5": 1, "X2": 1},
    "ramp":        {"L": 17, "M2": 4, "C2": 3, "S3": 2, "C5": 3, "C6": 4, "B5": 2, "R4": 3, "D3": 1, "V3": 1},
    "aristocrats": {"L": 16, "C1": 2, "C2": 4, "TK": 4, "SO": 2, "AR": 4, "V3": 2, "C3": 2, "R2": 4},
    "tribal":      {"L": 16, "C1": 3, "C2": 7, "C3": 4, "P3": 4, "TK": 2, "R2": 3, "V3": 1},
    "combo":       {"L": 16, "K1": 4, "K2": 4, "T2": 3, "C2": 4, "V3": 2, "X2": 2, "R2": 3, "C3": 2},
}
FIELD99 = {
    "template":    {"L": 37, "M2": 10, "D3": 5, "V3": 6, "R2": 5, "R4": 4, "W4": 2, "C2": 6, "C3": 6, "C4": 5, "C5": 4, "C6": 3, "B5": 3, "S3": 3},
    "aggro":       {"L": 33, "M2": 4, "C1": 8, "C2": 14, "C3": 12, "C4": 6, "F3": 6, "V3": 4, "R2": 6, "TK": 4, "B5": 2},
    "control":     {"L": 38, "M2": 8, "D3": 6, "V3": 5, "R2": 6, "R4": 6, "W4": 4, "X2": 6, "C4": 4, "C5": 4, "C6": 4, "B5": 4, "S3": 4},
    "ramp":        {"L": 38, "M2": 14, "C2": 4, "C3": 4, "C5": 8, "C6": 10, "B5": 5, "R4": 5, "D3": 4, "V3": 4, "S3": 3},
    "aristocrats": {"L": 35, "M2": 6, "C1": 4, "C2": 8, "TK": 10, "SO": 5, "AR": 8, "V3": 6, "R2": 6, "R4": 3, "C3": 4, "D3": 4},
    "combo":       {"L": 36, "K1": 1, "K2": 1, "T2": 5, "M2": 8, "D3": 6, "V3": 6, "X2": 4, "R2": 6, "R4": 4, "C2": 8, "C3": 8, "C4": 6},
}


def cap(deck, fmt, filler="C2"):
    d = dict(deck)
    for c, m in CAPS[fmt].items():
        if d.get(c, 0) > m:
            d[filler] = d.get(filler, 0) + d[c] - m
            d[c] = m
    return {c: v for c, v in d.items() if v}


def field_for(fmt):
    size = FORMATS[fmt]["size"]
    if size in (40, 60):
        return {k: cap(scale(v, size), fmt) for k, v in FIELD40.items()}
    if size == 99:
        return {k: cap(v, fmt) for k, v in FIELD99.items()}
    return {k: cap(_scale_any(v, 99, size), fmt) for k, v in FIELD99.items()}


def _scale_any(deck, src, size):
    f = size / src
    out = {c: max(0, round(n * f)) for c, n in deck.items()}
    diff = size - sum(out.values())
    order = sorted(deck, key=lambda c: -deck[c])
    i = 0
    while diff:
        c = order[i % len(order)]
        step = 1 if diff > 0 else -1
        if out[c] + step >= 0:
            out[c] += step
            diff -= step
        i += 1
    return {c: v for c, v in out.items() if v}


def mv(deck):
    spells = {c: n for c, n in deck.items() if c != "L"}
    return sum(COST[c] * n for c, n in spells.items()) / max(1, sum(spells.values()))


def swap_in(base, card, n, cut):
    """Add n copies of `card`, cutting one at a time from the largest of `cut`."""
    d = dict(base)
    for _ in range(n):
        opts = [c for c in cut if d.get(c, 0) > 0]
        if not opts:
            break
        src = max(opts, key=lambda c: d[c])
        d[src] -= 1
        d[card] = d.get(card, 0) + 1
    return {c: v for c, v in d.items() if v}


def set_count(base, card, n, cut):
    """Set `card` to exactly n copies, filling/cutting from `cut` creatures."""
    d = dict(base)
    cur = d.get(card, 0)
    if n > cur:
        return swap_in(d, card, n - cur, cut)
    d[card] = n
    for i in range(cur - n):
        f = cut[i % len(cut)]
        d[f] = d.get(f, 0) + 1
    return {c: v for c, v in d.items() if v}


def set_lands(base, n, cut=("C2", "C3", "C4", "C5")):
    return set_count(base, "L", n, list(cut))


# ---------------- parallel evaluation ----------------
def _job(args):
    deck, opp, games, seed, kw = args
    return match(deck, opp, games, seed, **kw)


def avg(rows):
    out = {}
    for key, v in rows[0].items():
        if isinstance(v, dict):
            keys = set().union(*(r[key] for r in rows))
            out[key] = {kk: round(sum(r[key].get(kk, 0) for r in rows) / len(rows), 4) for kk in keys}
        else:
            out[key] = round(sum(r[key] for r in rows) / len(rows), 4)
    return out


def vs_field(pool, decks, field, games, kw, seed=0):
    jobs = [(d, o, games, seed + i * 1000 + j, kw)
            for i, d in enumerate(decks) for j, o in enumerate(field)]
    res = pool.map(_job, jobs, chunksize=max(1, len(jobs) // (CORES * 8)))
    k = len(field)
    return [avg(res[i * k:(i + 1) * k]) for i in range(len(decks))]


def sweep(pool, fmt, name, label, xs, make, games, field=None):
    t = time.time()
    F = field or list(field_for(fmt).values())
    decks = [make(x) for x in xs]
    rs = vs_field(pool, decks, F, games, FORMATS[fmt]["kw"])
    rows = [{"x": x, "avg_mv": round(mv(d), 2), **r} for x, d, r in zip(xs, decks, rs)]
    best = max(rows, key=lambda r: r["win"])
    print(f"[{fmt}:{name}] {label}: best={best['x']} win={best['win']:.3f} ({time.time()-t:.0f}s)", flush=True)
    return {"format": fmt, "name": name, "label": label, "rows": rows, "best": best["x"]}


CREATURES = ["C2", "C3", "C4", "C5"]


def experiments(pool, G, GB, save):
    E = []
    # ================= Draft 40 =================
    base40 = {"L": 17, "C2": 5, "C3": 3, "V3": 2, "C4": 3, "C5": 2, "B5": 1, "S3": 1, "F3": 2, "R2": 2, "R4": 2}
    E.append(sweep(pool, "draft40", "lands", "Lands in a typical draft deck (with sinks + a bomb)",
                   list(range(14, 21)), lambda L: set_lands(base40, L), G))
    E.append(sweep(pool, "draft40", "lands_nosinks", "Same deck with mana sinks and bomb replaced by vanilla creatures",
                   list(range(14, 21)),
                   lambda L: set_lands(swap_in(swap_in(base40, "C3", 1, ["S3"]), "C5", 1, ["B5"]), L), G))
    curves = {
        "low (aggro)": {"C1": 3, "C2": 8, "C3": 5, "V3": 2, "C4": 2, "F3": 2, "R2": 3},
        "medium": {"C2": 5, "C3": 3, "V3": 2, "C4": 3, "C5": 2, "B5": 1, "S3": 1, "F3": 2, "R2": 2, "R4": 2},
        "high (big)": {"C2": 3, "S3": 2, "V3": 2, "C4": 3, "C5": 3, "C6": 3, "B5": 2, "R4": 3, "D3": 1, "R2": 1},
    }
    grid = []
    for cname, mix in curves.items():
        r = sweep(pool, "draft40", f"curve_{cname}", f"Lands for a {cname} curve",
                  list(range(14, 21)), lambda L, mix=mix: build(L, 40, mix), G)
        grid.append(r)
        E.append(r)
    save(E)
    # creature count: replace creatures with removal/draw
    def creat(n):
        spells = {"R2": 3, "R4": 3, "D3": 2, "X2": 2, "W4": 1, "TK": 1}
        cre = {"C2": 5, "C3": 3, "V3": 2, "C4": 3, "C5": 2, "B5": 1, "S3": 1, "F3": 2, "C1": 1}
        cs = build(0, n, cre); cs.pop("L", None)
        ss = build(0, 23 - n, spells); ss.pop("L", None)
        d = {"L": 17}
        for k, v in list(cs.items()) + list(ss.items()):
            d[k] = d.get(k, 0) + v
        return d
    E.append(sweep(pool, "draft40", "creatures", "Creature count (of 23 spells, rest = removal/draw/interaction)",
                   list(range(9, 21)), creat, G))
    E.append(sweep(pool, "draft40", "twodrops", "Two-drops in a 17-land draft deck",
                   list(range(0, 11)), lambda n: set_count(base40, "C2", n, ["C4", "C3", "C5"]), G))
    E.append(sweep(pool, "draft40", "bombs", "Bombs (B5) in a draft deck",
                   list(range(0, 5)), lambda n: set_count(base40, "B5", n, ["C3", "C4", "C2"]), G))
    aristo = {"L": 16, "C1": 2, "C2": 6, "C3": 4, "V3": 2, "C4": 2, "R2": 4, "F3": 2, "TK": 2}
    E.append(sweep(pool, "draft40", "aristo_no_enablers", "Aristocrat payoffs, no tokens or sac outlet",
                   list(range(0, 7)), lambda n: swap_in(swap_in(aristo, "C2", 2, ["TK"]), "AR", n, ["C3", "C2", "C4"]), G))
    E.append(sweep(pool, "draft40", "aristo_enablers", "Aristocrat payoffs with 4 token makers + 2 sac outlets",
                   list(range(0, 7)),
                   lambda n: swap_in(swap_in(swap_in(aristo, "TK", 2, ["C3", "C4"]), "SO", 2, ["C2"]), "AR", n, ["C3", "C2", "C1"]), G))
    E.append(sweep(pool, "draft40", "lords_tokens", "Lords in a go-wide token deck",
                   list(range(0, 7)), lambda n: swap_in(swap_in(aristo, "TK", 2, ["C3", "C4"]), "P3", n, ["C3", "C2", "C1"]), G))
    save(E)

    # ================= Constructed 60 =================
    arch60 = {
        "aggro (MV ~2)": {"C1": 10, "C2": 14, "C3": 6, "F3": 4, "R2": 6, "TK": 2},
        "midrange (MV ~3)": {"C2": 8, "C3": 4, "V3": 6, "C4": 6, "C5": 3, "B5": 3, "R2": 4, "R4": 3, "S3": 2},
        "control (MV ~3.5)": {"C2": 2, "V3": 4, "C5": 2, "C6": 3, "B5": 4, "R2": 6, "R4": 5, "X2": 6, "W4": 3, "D3": 4, "S3": 2},
    }
    fit = []
    for aname, mix in arch60.items():
        r = sweep(pool, "con60", f"lands_{aname.split()[0]}", f"Lands for a 60-card {aname} deck",
                  list(range(18, 31)), lambda L, mix=mix: cap(build(L, 60, mix), "con60"), G)
        cheap = sum(n for c, n in build(24, 60, mix).items() if c in ("M2",))
        fit.append({"deck": aname, "best": r["best"], "avg_mv": r["rows"][0]["avg_mv"],
                    "karsten": round(19.59 + 1.90 * r["rows"][0]["avg_mv"] - 0.28 * cheap, 1)})
        E.append(r)
    E.append({"format": "con60", "name": "karsten_check", "label": "Best land count vs Karsten's formula",
              "rows": fit, "best": None})
    save(E)
    rows = []
    for k in (2, 3, 4):
        for t in (0, 2, 4):
            d = {"L": 23, "K1": k, "K2": k, "T2": t, "X2": 4, "R2": 6, "V3": 6}
            fill = 60 - sum(d.values())
            d["C2"], d["C3"] = fill // 2, fill - fill // 2
            r = vs_field(pool, [d], list(field_for("con60").values()), G, FORMATS["con60"]["kw"])[0]
            rows.append({"x": f"{k} of each piece, {t} tutors", "pieces": k, "tutors": t, **r})
            print(f"[con60:combo] pieces={k} tutors={t} win={r['win']:.3f}", flush=True)
    E.append({"format": "con60", "name": "combo", "label": "60-card combo (4-copy limit): pieces x tutors",
              "rows": rows, "best": max(rows, key=lambda r: r["win"])["x"]})
    combo60 = field_for("con60")["combo"]
    mid60 = cap(build(24, 60, arch60["midrange (MV ~3)"]), "con60")
    E.append(sweep(pool, "con60", "counters_vs_combo", "Counterspells in midrange vs a combo deck",
                   list(range(0, 9, 2)), lambda n: set_count(mid60, "X2", n, ["C2", "C3", "C4"]), G * 2, [combo60]))
    E.append(sweep(pool, "con60", "removal_vs_combo", "Removal in midrange vs a combo deck",
                   list(range(0, 13, 2)), lambda n: set_count(set_count(mid60, "R4", 0, ["C4"]), "R2", n, ["C2", "C3", "C4"]),
                   G * 2, [combo60]))
    E.append(sweep(pool, "con60", "counters_vs_field", "Counterspells in midrange vs the whole field",
                   list(range(0, 9, 2)), lambda n: set_count(mid60, "X2", n, ["C2", "C3", "C4"]), G))
    save(E)

    # ================= Brawl (99 + commander, 25 life) =================
    tpl = FIELD99["template"]
    E.append(sweep(pool, "brawl", "lands", "Lands (template deck, 10 ramp)",
                   list(range(30, 45, 2)), lambda L: set_lands(tpl, L, CREATURES), GB))
    E.append(sweep(pool, "brawl", "lands_noramp", "Lands with ramp replaced by creatures",
                   list(range(30, 45, 2)), lambda L: set_lands(set_count(tpl, "M2", 0, CREATURES), L, CREATURES), GB))
    E.append(sweep(pool, "brawl", "ramp", "Ramp spells (37 lands)",
                   list(range(0, 17, 2)), lambda n: set_count(tpl, "M2", n, CREATURES), GB))
    E.append(sweep(pool, "brawl", "draw", "Card draw: draw spells + value creatures (37 lands)",
                   list(range(0, 17, 2)),
                   lambda n: set_count(set_count(tpl, "D3", n // 2, CREATURES), "V3", n - n // 2, CREATURES), GB))
    E.append(sweep(pool, "brawl", "removal", "Targeted removal (37 lands)",
                   list(range(0, 17, 2)),
                   lambda n: set_count(set_count(tpl, "R2", n // 2, CREATURES), "R4", n - n // 2, CREATURES), GB))
    E.append(sweep(pool, "brawl", "wipes", "Board wipes (37 lands)",
                   list(range(0, 7)), lambda n: set_count(tpl, "W4", n, CREATURES), GB))
    save(E)
    # ================= Standard Brawl and Commander 1v1 land counts =================
    tpl59 = _scale_any(tpl, 99, 59)
    E.append(sweep(pool, "sbrawl", "lands", "Lands in Standard Brawl (59 + commander)",
                   list(range(18, 29)), lambda L: set_lands(tpl59, L, CREATURES), GB))
    E.append(sweep(pool, "cmdr1v1", "lands", "Lands in Commander rules, 1v1 at 40 life",
                   list(range(30, 45, 2)), lambda L: set_lands(tpl, L, CREATURES), GB))
    save(E)

    # ================= meta per format =================
    for fmt in ("draft40", "con60", "brawl"):
        fd = field_for(fmt)
        rs = vs_field(pool, list(fd.values()), list(fd.values()), GB, FORMATS[fmt]["kw"])
        rows = [{"x": k, **r} for k, r in zip(fd, rs)]
        print(f"[{fmt}:meta] " + " ".join(f"{r['x']}={r['win']:.2f}" for r in rows), flush=True)
        E.append({"format": fmt, "name": "meta", "label": f"{fmt}: archetypes vs each other",
                  "rows": rows, "best": max(rows, key=lambda r: r["win"])["x"]})
    save(E)
    return E


# ---------------- evolution with format rules ----------------
def legalize(d, rng, size, fmt, allowed):
    d = {c: v for c, v in d.items() if c in allowed and v > 0}
    for c, m in CAPS[fmt].items():
        if d.get(c, 0) > m:
            d[c] = m
    total = sum(d.values())
    while total != size:
        c = rng.choice(allowed)
        if total > size and d.get(c, 0) > 0:
            d[c] -= 1; total -= 1
        elif total < size and d.get(c, 0) < CAPS[fmt].get(c, 999):
            d[c] = d.get(c, 0) + 1; total += 1
    return {c: v for c, v in d.items() if v}


def evolve(pool, fmt, gens, pop_n, games, seed):
    size, kw = FORMATS[fmt]["size"], FORMATS[fmt]["kw"]
    allowed = CARDS
    rng = random.Random(seed)
    field = list(field_for(fmt).values())
    pop = []
    for _ in range(pop_n):
        lands = rng.randint(int(size * .3), int(size * .5))
        mix = {c: rng.random() for c in allowed if c != "L"}
        pop.append(legalize(build(lands, size, mix), rng, size, fmt, allowed))
    hof, history = [], []
    for g in range(gens):
        opps = field + hof[-3:] + rng.sample(pop, 3)
        scores = [r["win"] for r in vs_field(pool, pop, opps, games, kw, seed=g * 7919)]
        ranked = sorted(zip(scores, range(len(pop))), reverse=True)
        best = pop[ranked[0][1]]
        hof.append(best)
        history.append({"gen": g, "best_score": round(ranked[0][0], 4), "best": best,
                        "top10_lands": round(sum(pop[i].get("L", 0) for _, i in ranked[:10]) / 10, 2)})
        print(f"  [{fmt}] gen {g:2d} best {ranked[0][0]:.3f} {best}", flush=True)
        elite = [pop[i] for _, i in ranked[:pop_n // 4]]
        kids = list(elite)
        while len(kids) < pop_n:
            a, b = rng.sample(elite, 2)
            child = {c: (a.get(c, 0) if rng.random() < .5 else b.get(c, 0)) for c in allowed} if rng.random() < .5 else dict(a)
            for _ in range(rng.randint(1, 3 if size <= 60 else 6)):
                src = rng.choice([c for c in child if child[c] > 0])
                child[src] -= 1
                dst = rng.choice(allowed)
                child[dst] = child.get(dst, 0) + 1
            kids.append(legalize(child, rng, size, fmt, allowed))
        pop = kids
    finals = hof[-6:]
    fr = vs_field(pool, finals, field, games * 8, kw, seed=4242)
    i = max(range(len(finals)), key=lambda i: fr[i]["win"])
    return {"format": fmt, "history": history, "champion": finals[i], "champion_vs_field": fr[i],
            "champion_avg_mv": round(mv(finals[i]), 2)}


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    G, GB = (150, 80) if quick else (2500, 1200)
    t0 = time.time()
    result = {"cores": CORES, "games_draft_con": G, "games_brawl": GB, "real_advice": REAL_ADVICE}
    path = os.path.join(OUT, "results2-quick.json" if quick else "results2.json")

    def save(E):
        result["experiments"] = E
        json.dump(result, open(path, "w"), indent=1)

    with Pool(CORES) as pool:
        print(f"Using {CORES} cores", flush=True)
        save(experiments(pool, G, GB, save))
        result["evolution"] = {}
        eg, ep, egames = (3, 8, 30) if quick else (20, 32, 120)
        for i, fmt in enumerate(("draft40", "con60", "brawl")):
            print(f"Evolving best {fmt} deck...", flush=True)
            result["evolution"][fmt] = evolve(pool, fmt, eg, ep, egames if fmt != "brawl" else egames // 2, 50 + i)
            json.dump(result, open(path, "w"), indent=1)
    result["seconds"] = round(time.time() - t0)
    json.dump(result, open(path, "w"), indent=1)
    print(f"done in {result['seconds']}s", flush=True)
