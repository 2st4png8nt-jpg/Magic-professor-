"""
Magic Professor — the learning agent.

Two ways it learns, both spread across every CPU core:

1. Controlled experiments: change ONE thing about a deck (land count, curve,
   removal count...) and play thousands of games against a varied field of
   opponents to measure exactly how much that one thing matters.

2. Evolution (genetic algorithm): breed a population of decks. Each generation,
   every deck plays the field, the best decks so far ("hall of fame") and its
   peers. Winners reproduce with small mutations (swap a few cards); losers die.
   The field keeps getting tougher, so the decks have to keep getting better.

Run:  python3 learn.py            (writes results/results.json)
"""
import json, os, random, sys, time
from multiprocessing import Pool, cpu_count
from engine import CARDS, COST, match

CORES = cpu_count()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# ---- the field: archetypes a deck must beat (40-card versions) ----
FIELD40 = {
    "aggro":    {"L": 16, "C1": 5, "C2": 8, "C3": 6, "C4": 2, "R2": 3},
    "midrange": {"L": 17, "C2": 4, "C3": 5, "C4": 4, "C5": 2, "F3": 2, "R2": 3, "R4": 2, "D3": 1},
    "control":  {"L": 18, "C3": 2, "C4": 3, "C5": 3, "C6": 3, "R2": 4, "R4": 4, "D3": 3},
    "flyers":   {"L": 16, "C2": 6, "F3": 8, "C3": 3, "C4": 2, "R2": 4, "D3": 1},
    "ramp":     {"L": 16, "M2": 5, "C2": 3, "C3": 3, "C5": 4, "C6": 5, "R4": 3, "D3": 1},
    "goodstuff":{"L": 17, "C2": 5, "C3": 6, "C4": 4, "C5": 2, "R2": 3, "R4": 2, "D3": 1},
    "tribal":   {"L": 16, "C1": 3, "C2": 7, "C3": 4, "P3": 4, "AR": 2, "R2": 4},
    "combo":    {"L": 16, "K1": 4, "K2": 4, "T2": 4, "C2": 4, "C3": 4, "R2": 4},
}


def scale(deck, size):
    """Scale a 40-card list to `size` cards, keeping proportions."""
    f = size / 40
    out = {c: round(n * f) for c, n in deck.items()}
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
    return out


def build(lands, size, mix):
    """lands + spells distributed by weight `mix` (largest-remainder rounding)."""
    spells = size - lands
    tot = sum(mix.values())
    raw = {c: spells * w / tot for c, w in mix.items()}
    out = {c: int(v) for c, v in raw.items()}
    left = spells - sum(out.values())
    for c in sorted(raw, key=lambda c: raw[c] - out[c], reverse=True)[:left]:
        out[c] += 1
    out["L"] = lands
    return {c: n for c, n in out.items() if n}


BASE_MIX = {"C2": 5, "C3": 6, "C4": 4, "C5": 2, "F3": 2, "R2": 3, "R4": 2, "D3": 1}


# ---------------- parallel evaluation ----------------
def _job(args):
    deck, opp, games, seed, kw = args
    return match(deck, opp, games, seed, **kw)


def avg(rows):
    """Average a list of result dicts; nested dicts (won_by/lost_to) averaged per key."""
    out = {}
    for key, v in rows[0].items():
        if isinstance(v, dict):
            keys = set().union(*(r[key] for r in rows))
            out[key] = {kk: round(sum(r[key].get(kk, 0) for r in rows) / len(rows), 4) for kk in keys}
        else:
            out[key] = round(sum(r[key] for r in rows) / len(rows), 4)
    return out


def vs_field(pool, decks, field, games, kw=None, seed=0):
    """Average win rate of each deck in `decks` against every deck in `field`."""
    kw = kw or {}
    jobs = [(d, o, games, seed + i * 1000 + j, kw)
            for i, d in enumerate(decks) for j, o in enumerate(field)]
    res = pool.map(_job, jobs, chunksize=max(1, len(jobs) // (CORES * 4)))
    out = []
    k = len(field)
    for i in range(len(decks)):
        chunk = res[i * k:(i + 1) * k]
        out.append(avg(chunk))
    return out


def sweep(pool, name, label, xs, make, field, games, kw=None):
    t = time.time()
    rs = vs_field(pool, [make(x) for x in xs], field, games, kw)
    rows = [{"x": x, **r} for x, r in zip(xs, rs)]
    best = max(rows, key=lambda r: r["win"])
    print(f"[{name}] {label}: best x={best['x']} win={best['win']:.3f} ({time.time()-t:.0f}s)", flush=True)
    return {"name": name, "label": label, "rows": rows, "best": best["x"]}


def experiments(pool, games):
    f40 = list(FIELD40.values())
    f60 = [scale(d, 60) for d in f40]
    f100 = [scale(d, 100) for d in f40]
    E = []
    E.append(sweep(pool, "lands40", "Lands in a 40-card deck", list(range(12, 22)),
                   lambda L: build(L, 40, BASE_MIX), f40, games))
    E.append(sweep(pool, "lands60", "Lands in a 60-card deck", list(range(18, 32)),
                   lambda L: build(L, 60, BASE_MIX), f60, games))
    E.append(sweep(pool, "lands100", "Lands in a 100-card, 40-life deck", list(range(30, 48, 2)),
                   lambda L: build(L, 100, BASE_MIX), f100, games, {"life": 40}))

    curves = {
        "1.9 (very low)": {"C1": 5, "C2": 9, "C3": 5, "R2": 4},
        "2.5 (low)":      {"C1": 2, "C2": 7, "C3": 6, "C4": 3, "R2": 3, "R4": 1, "F3": 1},
        "3.0 (medium)":   BASE_MIX,
        "3.6 (high)":     {"C3": 4, "C4": 5, "C5": 4, "C6": 3, "R2": 2, "R4": 3, "D3": 2},
        "4.2 (very high)":{"C4": 4, "C5": 6, "C6": 6, "R4": 5, "D3": 2},
    }
    # each curve tested at its own best land count, so it's a fair fight
    rows = []
    for nm, mix in curves.items():
        sub = vs_field(pool, [build(L, 40, mix) for L in range(14, 21)], f40, games // 2)
        L = 14 + max(range(len(sub)), key=lambda i: sub[i]["win"])
        r = vs_field(pool, [build(L, 40, mix)], f40, games)[0]
        spells = build(L, 40, mix)
        mv = sum(COST[c] * n for c, n in spells.items() if c != "L") / (40 - L)
        rows.append({"x": nm, "lands": L, "avg_mv": round(mv, 2), **r})
        print(f"[curve] {nm}: lands={L} win={r['win']:.3f}", flush=True)
    E.append({"name": "curve", "label": "Mana curve (avg mana value), each at its best land count",
              "rows": rows, "best": max(rows, key=lambda r: r["win"])["x"]})

    def swap(add, remove_from, n):
        d = build(17, 40, BASE_MIX)
        for _ in range(n):
            src = max((c for c in remove_from if d.get(c, 0) > 0), key=lambda c: d[c])
            d[src] -= 1
            d[add] = d.get(add, 0) + 1
        return {c: v for c, v in d.items() if v}

    base_removal = build(17, 40, {k: v for k, v in BASE_MIX.items() if k not in ("R2", "R4")})
    def removal(n):
        d = dict(base_removal)
        for i in range(n):
            src = max((c for c in ("C2", "C3", "C4") if d.get(c, 0) > 0), key=lambda c: d[c])
            d[src] -= 1
            k = "R2" if i % 2 == 0 else "R4"
            d[k] = d.get(k, 0) + 1
        return {c: v for c, v in d.items() if v}
    E.append(sweep(pool, "removal", "Removal spells (replacing creatures)", list(range(0, 13)),
                   removal, f40, games))
    E.append(sweep(pool, "draw", "Draw-two spells (replacing creatures)", list(range(0, 9)),
                   lambda n: swap("D3", ("C2", "C3", "C4"), n), f40, games))
    E.append(sweep(pool, "flyers", "Evasive creatures (flyers replacing 3-drops)", list(range(0, 11)),
                   lambda n: swap("F3", ("C3", "C2", "C4"), n), f40, games))

    def ramp(n, cut_lands):
        d = build(17, 40, BASE_MIX)
        for i in range(n):
            if cut_lands and i % 2 == 0:
                d["L"] -= 1
            else:
                src = max(("C2", "C3"), key=lambda c: d.get(c, 0))
                d[src] -= 1
            d["M2"] = d.get("M2", 0) + 1
        return {c: v for c, v in d.items() if v}
    E.append(sweep(pool, "ramp", "Ramp spells (half replace lands, half 2-3 drops)", list(range(0, 9)),
                   lambda n: ramp(n, True), f40, games))

    base = build(17, 40, BASE_MIX)
    mull = vs_field(pool, [base], f40, games * 2, {"mulligan": True})[0]
    nomull = vs_field(pool, [base], f40, games * 2, {"mulligan": False})[0]
    play = vs_field(pool, [base], f40, games * 2, {"a_first": True})[0]
    drw = vs_field(pool, [base], f40, games * 2, {"a_first": False})[0]
    mono = vs_field(pool, [base], f40, games * 2, {"colors": 1})[0]
    duo = vs_field(pool, [base], f40, games * 2, {"colors": 2})[0]
    E.append({"name": "colors", "label": "One color vs two colors (same cards)",
              "rows": [{"x": "mono-color", **mono}, {"x": "two colors", **duo}]})
    print(f"[colors] mono {mono['win']:.3f} vs two {duo['win']:.3f}", flush=True)
    E.append({"name": "mulligan", "label": "Mulligan bad hands vs keep every 7",
              "rows": [{"x": "mulligan 0-1 or 6-7 landers", **mull}, {"x": "keep every hand", **nomull}]})
    E.append({"name": "playdraw", "label": "Going first vs going second",
              "rows": [{"x": "on the play", **play}, {"x": "on the draw", **drw}]})
    print(f"[mulligan] {mull['win']:.3f} vs {nomull['win']:.3f}; [play/draw] {play['win']:.3f} vs {drw['win']:.3f}", flush=True)

    # ---- synergy: lords need bodies to pump ----
    creature_base = {"L": 16, "C1": 3, "C2": 8, "C3": 7, "C4": 2, "R2": 4}
    control_base = {"L": 17, "C2": 2, "C3": 2, "C4": 3, "C5": 3, "C6": 3, "R2": 4, "R4": 4, "D3": 2}

    def add_n(base, card, n, cut):
        d = dict(base)
        for _ in range(n):
            src = max((c for c in cut if d.get(c, 0) > 0), key=lambda c: d[c])
            d[src] -= 1
            d[card] = d.get(card, 0) + 1
        return {c: v for c, v in d.items() if v}
    E.append(sweep(pool, "lords_wide", "Lords in a creature-heavy deck (24 creatures)", list(range(0, 9)),
                   lambda n: add_n(creature_base, "P3", n, ("C3", "C2", "C4")), f40, games))
    E.append(sweep(pool, "lords_control", "Lords in a removal-heavy deck (13 creatures)", list(range(0, 9)),
                   lambda n: add_n(control_base, "P3", n, ("C4", "C5", "C3", "C6")), f40, games))
    E.append(sweep(pool, "aristocrats", "Aristocrats (death-payoff) in a creature-heavy deck", list(range(0, 9)),
                   lambda n: add_n(creature_base, "AR", n, ("C3", "C2", "C4")), f40, games))

    # ---- combo: how many pieces, how many tutors ----
    rows = []
    for k in (1, 2, 3, 4):
        for t in (0, 2, 4):
            d = {"L": 16, "K1": k, "K2": k, "T2": t, "R2": 4}
            fill = 40 - sum(d.values())
            d["C2"], d["C3"] = fill // 2, fill - fill // 2
            r = vs_field(pool, [d], f40, games)[0]
            rows.append({"x": f"{k} of each piece, {t} tutors", "pieces": k, "tutors": t, **r})
            print(f"[combo] pieces={k} tutors={t} win={r['win']:.3f}", flush=True)
    E.append({"name": "combo", "label": "Combo deck: copies of each piece x tutors",
              "rows": rows, "best": max(rows, key=lambda r: r["win"])["x"]})

    # ---- interaction vs combo: how much removal does it take to beat combo? ----
    def removal_vs_combo(n):
        d = {"L": 17, "C2": 6, "C3": 6, "C4": 4, "C5": 3, "F3": 4}
        for i in range(n):
            src = max(("C2", "C3", "C4", "C5", "F3"), key=lambda c: d[c])
            d[src] -= 1
            k = "R2" if i % 2 == 0 else "R4"
            d[k] = d.get(k, 0) + 1
        return d
    E.append(sweep(pool, "anti_combo", "Your removal count vs a combo deck", list(range(0, 13, 2)),
                   removal_vs_combo, [FIELD40["combo"]], games * 2))

    # how good is each field archetype vs everything else (meta snapshot)
    names = list(FIELD40)
    rs = vs_field(pool, f40, f40, games)
    E.append({"name": "meta", "label": "Benchmark archetypes vs the whole field",
              "rows": [{"x": n, **r} for n, r in zip(names, rs)]})
    return E


# ---------------- evolution ----------------
SPELLS = [c for c in CARDS if c != "L"]


# Archetypes = which cards a deck may use, plus minimums that define its plan.
ARCHETYPES = {
    "aggro":    {"cards": ["L", "C1", "C2", "C3", "C4", "F3", "R2", "P3", "AR"], "min": {}},
    "midrange": {"cards": ["L", "C2", "C3", "C4", "C5", "C6", "F3", "R2", "R4", "D3", "M2"], "min": {}},
    "control":  {"cards": ["L", "C4", "C5", "C6", "F3", "R2", "R4", "D3", "M2"], "min": {"R2": 3, "R4": 3}},
    "combo":    {"cards": ["L", "C2", "C3", "R2", "R4", "D3", "M2", "K1", "K2", "T2"], "min": {"K1": 2, "K2": 2}},
}
ALL = {"cards": CARDS, "min": {}}


def legalize(d, rng, size, arch):
    allowed = arch["cards"]
    d = {c: v for c, v in d.items() if c in allowed and v > 0}
    for c, m in arch["min"].items():
        d[c] = max(d.get(c, 0), m)
    total = sum(d.values())
    while total != size:
        c = rng.choice(allowed)
        if total > size and d.get(c, 0) > arch["min"].get(c, 0):
            d[c] -= 1; total -= 1
        elif total < size:
            d[c] = d.get(c, 0) + 1; total += 1
    return {c: v for c, v in d.items() if v}


def random_deck(rng, size, arch=ALL):
    lands = rng.randint(int(size * .3), int(size * .5))
    mix = {c: rng.random() for c in arch["cards"] if c != "L"}
    return legalize(build(lands, size, mix), rng, size, arch)


def mutate(deck, rng, size, arch=ALL):
    d = dict(deck)
    for _ in range(rng.randint(1, 3)):
        src = rng.choice([c for c in d if d[c] > 0])
        dst = rng.choice([c for c in arch["cards"] if c != src])
        d[src] -= 1
        d[dst] = d.get(dst, 0) + 1
    return legalize(d, rng, size, arch)


def crossover(a, b, rng, size, arch=ALL):
    child = {c: (a.get(c, 0) if rng.random() < .5 else b.get(c, 0)) for c in arch["cards"]}
    return legalize(child, rng, size, arch)


def evolve(pool, size, field, gens, pop_n, games, seed, life=20, arch=ALL):
    rng = random.Random(seed)
    pop = [random_deck(rng, size, arch) for _ in range(pop_n)]
    hof, history = [], []
    kw = {"life": life}
    for g in range(gens):
        opponents = field + hof[-4:] + rng.sample(pop, 4)
        scores = [r["win"] for r in vs_field(pool, pop, opponents, games, kw, seed=g * 99991)]
        ranked = sorted(zip(scores, range(len(pop))), reverse=True)
        best = pop[ranked[0][1]]
        hof.append(best)
        lands = sum(pop[i].get("L", 0) for _, i in ranked[:10]) / 10
        avg_mv = sum(COST[c] * n for c, n in best.items()) / max(1, size - best.get("L", 0))
        history.append({"gen": g, "best_score": round(ranked[0][0], 4),
                        "top10_lands": round(lands, 2), "best": best, "best_avg_mv": round(avg_mv, 2)})
        print(f"  gen {g:3d}  best {ranked[0][0]:.3f}  lands(top10) {lands:.1f}  {best}", flush=True)
        elite = [pop[i] for _, i in ranked[:pop_n // 4]]
        children = list(elite)
        while len(children) < pop_n:
            a, b = rng.sample(elite, 2)
            child = crossover(a, b, rng, size, arch) if rng.random() < .5 else dict(a)
            children.append(mutate(child, rng, size, arch))
        pop = children
    # final, careful evaluation of the last few champions vs the original field
    finals = hof[-8:]
    fr = vs_field(pool, finals, field, games * 10, kw, seed=12345)
    champ_i = max(range(len(finals)), key=lambda i: fr[i]["win"])
    return {"size": size, "life": life, "history": history,
            "champion": finals[champ_i], "champion_vs_field": fr[champ_i]}


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    G = 400 if quick else 3000
    t0 = time.time()
    with Pool(CORES) as pool:
        print(f"Using {CORES} cores", flush=True)
        result = {"cores": CORES, "games_per_point_per_opponent": G}
        result["experiments"] = experiments(pool, G)
        json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        f40 = list(FIELD40.values())
        gens, popn, eg = (6, 16, 60) if quick else (60, 48, 200)
        print("Evolving 40-card decks...", flush=True)
        result["evolve40"] = evolve(pool, 40, f40, gens, popn, eg, 1)
        json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        print("Evolving 60-card decks...", flush=True)
        result["evolve60"] = evolve(pool, 60, [scale(d, 60) for d in f40], gens, popn, eg, 2)
        json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        result["archetypes"] = {}
        ag, ap, aeg = (4, 12, 40) if quick else (30, 32, 150)
        for i, (name, arch) in enumerate(ARCHETYPES.items()):
            print(f"Evolving best {name} deck...", flush=True)
            result["archetypes"][name] = evolve(pool, 40, f40, ag, ap, aeg, 10 + i, arch=arch)
            json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        result["seconds"] = round(time.time() - t0)
        json.dump(result, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(f"done in {time.time()-t0:.0f}s", flush=True)
