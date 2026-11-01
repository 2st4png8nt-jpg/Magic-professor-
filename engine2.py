"""
Magic Professor engine v2 — "taught" with real deck-building knowledge.

v1 (engine.py) left out things real players say decide how a deck should be
built. v2 adds them, so the agent can check expert advice instead of
rediscovering a toy game:

  Real-game piece            Why experts say it matters           Card code
  -------------------------  -----------------------------------  ---------
  Mana sinks                 extra lands are not dead draws         S3
  Bombs (rare power cards)   reward reaching 5+ mana                B5
  Card-advantage creatures   a body AND a card                      V3
  Counterspells (held mana)  interaction on the opponent's turn     X2
  Board wipes                Commander templates run 2-3            W4
  Tokens + sacrifice outlet  the enablers aristocrats really need   TK, SO
  A commander                always-available engine, +2 tax       CM
  Free first mulligan        Brawl / Arena rule                     (option)
  Format life totals         20 / 25 (Brawl) / 40 (Commander)       (option)
  Copy limits                4-of (60), singleton (Brawl/Cmdr)      (deck rules, learn2.py)

v1 codes still work: L, C1..C6, F3, R2, R4, D3, M2, P3, AR, K1, K2, T2.
New codes:
  S3  3-mana 2/3; at end of your turn, spend each spare 3 mana for a +1/+1 counter
  B5  5-mana 4/4 flyer; when it enters, destroy an enemy creature with toughness <= 3
  V3  3-mana 2/2; when it enters, draw a card
  X2  2-mana counterspell: counter a spell with mana value 3+ (needs 2 open mana)
  W4  4-mana board wipe: destroy all creatures
  TK  3-mana: create two 1/1 tokens
  AR  (changed in v2) Blood Artist-style: whenever ANY creature dies, the
      opponent loses 1 and you gain 1
  SO  2-mana 1/2: sacrifice another creature (used to dodge removal/blocks, and
      to cash in tokens with aristocrats for lethal)
  CM  the commander: 4-mana 3/3, at the start of your turn draw a card while it
      is on the battlefield. Lives in the command zone; costs 2 more per earlier cast.
"""
import random

CARDS = ["L", "C1", "C2", "C3", "C4", "C5", "C6", "F3", "R2", "R4", "D3", "M2",
         "P3", "AR", "K1", "K2", "T2", "S3", "B5", "V3", "X2", "W4", "TK", "SO"]
STATS = {"C1": (2, 1), "C2": (3, 2), "C3": (3, 3), "C4": (4, 3),
         "C5": (4, 5), "C6": (5, 5), "F3": (2, 2),
         "P3": (2, 2), "AR": (1, 2), "K1": (1, 3), "K2": (1, 3),
         "S3": (2, 3), "B5": (4, 4), "V3": (2, 2), "SO": (1, 2), "T1": (1, 1), "CM": (3, 3)}
COST = {"L": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6,
        "F3": 3, "R2": 2, "R4": 4, "D3": 3, "M2": 2,
        "P3": 3, "AR": 2, "K1": 3, "K2": 3, "T2": 2,
        "S3": 3, "B5": 5, "V3": 3, "X2": 2, "W4": 4, "TK": 3, "SO": 2, "CM": 4}
FLYING = {"F3", "B5"}
NONPERM = {"R2", "R4", "D3", "M2", "T2", "X2", "W4", "TK"}


class Creature:
    __slots__ = ("code", "base_p", "base_t", "power", "tough", "flying", "sick")

    def __init__(self, code):
        self.code = code
        self.base_p, self.base_t = STATS[code]
        self.power, self.tough = self.base_p, self.base_t
        self.flying = code in FLYING
        self.sick = True

    def value(self):
        v = self.power + self.tough + (2 if self.flying else 0)
        if self.code in ("K1", "K2"):
            v += 8
        elif self.code in ("P3", "AR", "CM", "SO"):
            v += 3
        elif self.code == "T1":
            v -= 1
        return v


def refresh(board):
    lords = sum(c.code == "P3" for c in board)
    for c in board:
        b = lords - (c.code == "P3")
        c.power, c.tough = c.base_p + b, c.base_t + b


def kill(owner, creature, enemy):
    owner.board.remove(creature)
    if creature.code == "CM":
        owner.cmd_home = True
    # Blood Artist-style: each aristocrat triggers when ANY creature dies,
    # draining the other player 1 and gaining its controller 1.
    for p, q in ((owner, enemy), (enemy, owner)):
        n = sum(c.code == "AR" for c in p.board)
        if n:
            q.life -= n
            p.life += n
            p.dealt["drain"] += n
    refresh(owner.board)


def pips(code):
    return 2 if COST[code] >= 4 else 1


class Player:
    def __init__(self, deck_counts, rng, mulligan=True, life=20, colors=2,
                 commander=False, free_mull=False):
        letters = "ab"[:colors]
        self.library = []
        for c, n in deck_counts.items():
            for i in range(n):
                self.library.append(c + letters[i % colors])
        rng.shuffle(self.library)
        self.rng = rng
        self.hand, self.board = [], []
        self.lands = {"a": 0, "b": 0}
        self.life = life
        self.land_drop = False
        self.decked = False
        self.open_mana = 0
        self.commander = commander
        self.cmd_home = commander
        self.cmd_casts = 0
        self.stats = {"mulls": 0, "screw": False, "flood": False, "stuck": 0}
        self.dealt = {"ground": 0, "flyers": 0, "drain": 0}
        self._opening_hand(mulligan, free_mull)

    @property
    def n_lands(self):
        return self.lands["a"] + self.lands["b"]

    def hand_lands(self):
        return [c for c in self.hand if c[0] == "L"]

    def _opening_hand(self, mulligan, free_mull):
        n_mull = 0
        while True:
            self.library += self.hand
            self.hand = []
            self.rng.shuffle(self.library)
            self.draw(7)
            lands = len(self.hand_lands())
            if not mulligan or 2 <= lands <= 5 or n_mull >= 2:
                break
            n_mull += 1
        bottom = max(0, n_mull - (1 if free_mull else 0))
        for _ in range(bottom):
            hl = self.hand_lands()
            spells = [c for c in self.hand if c[0] != "L"]
            pick = hl[0] if (len(hl) > 3 or not spells) else max(spells, key=lambda c: COST[c[:-1]])
            self.hand.remove(pick)
            self.library.insert(0, pick)
        self.stats["mulls"] = n_mull

    def draw(self, n=1):
        for _ in range(n):
            if not self.library:
                self.decked = True
                return
            self.hand.append(self.library.pop())

    def can_cast(self, card, mana):
        code, col = card[:-1], card[-1]
        return COST[code] <= mana and self.lands[col] >= pips(code)

    def cmd_cost(self):
        return COST["CM"] + 2 * self.cmd_casts

    def want_color(self):
        need = {"a": 0, "b": 0}
        for c in self.hand:
            if c[0] != "L":
                need[c[-1]] += 1
        return max("ab", key=lambda k: need[k] / (self.lands[k] + 1))

    def fetch_land(self):
        want = self.want_color()
        lands = [c for c in self.library if c[0] == "L"]
        if not lands:
            return False
        pick = next((c for c in lands if c[-1] == want), lands[0])
        self.library.remove(pick)
        self.lands[pick[-1]] += 1
        self.rng.shuffle(self.library)
        return True

    def has(self, code):
        return any(c.code == code for c in self.board)

    def tutor(self):
        wants = []
        for a, b in (("K1", "K2"), ("K2", "K1")):
            if self.has(a) or any(c[:-1] == a for c in self.hand):
                wants.append(b)
        wants += ["K1", "B5", "W4", "P3", "C6", "C5", "V3", "C4", "F3", "C3"]
        for w in wants:
            if w in ("K1", "K2") and (self.has(w) or any(c[:-1] == w for c in self.hand)):
                continue
            pick = next((c for c in self.library if c[:-1] == w), None)
            if pick:
                self.library.remove(pick)
                self.hand.append(pick)
                self.rng.shuffle(self.library)
                return


def try_counter(caster, opp, code):
    """Opponent may counter a spell of mana value 3+ with X2 and 2 open mana."""
    if COST.get(code, 0) < 3 or opp.open_mana < 2:
        return False
    x = next((c for c in opp.hand if c[:-1] == "X2" and opp.lands[c[-1]] >= 1), None)
    if not x:
        return False
    opp.hand.remove(x)
    opp.open_mana -= 2
    return True


def _best_target(board, max_tough):
    cands = [c for c in board if c.tough <= max_tough]
    return max(cands, key=Creature.value) if cands else None


def _use_removal(me, opp, mana, order, picky):
    for code, cap in order:
        while True:
            cards = [c for c in me.hand if c[:-1] == code and me.can_cast(c, mana)]
            if not cards:
                break
            tgt = _best_target(opp.board, cap)
            if tgt is None or (picky and code == "R4" and tgt.value() < 6
                               and any(c[:-1] == "R2" for c in me.hand)):
                break
            me.hand.remove(cards[0])
            mana -= COST[code]
            if try_counter(me, opp, code):
                continue
            kill(opp, tgt, me)
    return mana


def board_value(p):
    return sum(c.value() for c in p.board)


def resolve(me, opp, code):
    if code in STATS:
        me.board.append(Creature(code))
        refresh(me.board)
        if code == "V3":
            me.draw(1)
        elif code == "B5":
            t = _best_target(opp.board, 3)
            if t:
                kill(opp, t, me)
    elif code == "T2":
        me.tutor()
    elif code == "D3":
        me.draw(2)
    elif code == "M2":
        me.fetch_land()
    elif code == "TK":
        me.board += [Creature("T1"), Creature("T1")]
        refresh(me.board)
    elif code == "W4":
        for c in list(opp.board):
            kill(opp, c, me)
        for c in list(me.board):
            kill(me, c, opp)


def main_phase(me, opp):
    hl = me.hand_lands()
    if hl and not me.land_drop:
        want = me.want_color()
        land = next((c for c in hl if c[-1] == want), hl[0])
        me.hand.remove(land)
        me.lands[land[-1]] += 1
        me.land_drop = True
    mana = me.n_lands

    # board wipe when clearly behind on board
    if board_value(opp) >= board_value(me) + 8 and len(opp.board) >= 2:
        w = next((c for c in me.hand if c[:-1] == "W4" and me.can_cast(c, mana)), None)
        if w:
            me.hand.remove(w)
            mana -= 4
            if not try_counter(me, opp, "W4"):
                resolve(me, opp, "W4")

    mana = _use_removal(me, opp, mana, (("R4", 99), ("R2", 3)), picky=True)

    # hold counterspell mana once we have 4+ lands
    hold = 2 if (me.n_lands >= 4 and any(c[:-1] == "X2" for c in me.hand)) else 0

    while True:
        spend = mana - hold
        castable = [c for c in me.hand if c[0] != "L" and c[:-1] not in ("R2", "R4", "X2", "W4")
                    and me.can_cast(c, spend)]
        cmd_ok = me.cmd_home and spend >= me.cmd_cost() and me.n_lands >= 2
        if not castable and not cmd_ok:
            break

        def prio(c):
            code = c[:-1]
            other = {"K1": "K2", "K2": "K1"}.get(code)
            combo_now = other and (me.has(other) or (any(h[:-1] == other for h in me.hand)
                                                     and spend >= 6))
            need_piece = code == "T2" and not (me.has("K1") and me.has("K2"))
            return (bool(combo_now), code == "M2" and me.n_lands <= 5, need_piece,
                    code in ("B5", "P3"), code in STATS and code not in ("K1", "K2"), COST[code])
        castable.sort(key=prio, reverse=True)
        if cmd_ok and (not castable or not prio(castable[0])[0]):
            me.cmd_home = False
            mana -= me.cmd_cost()
            me.cmd_casts += 1
            if try_counter(me, opp, "CM"):
                me.cmd_home = True
            else:
                resolve(me, opp, "CM")
            continue
        card = castable[0]
        code = card[:-1]
        me.hand.remove(card)
        mana -= COST[code]
        if try_counter(me, opp, code):
            continue
        resolve(me, opp, code)

    mana = _use_removal(me, opp, mana, (("R2", 3), ("R4", 99)), picky=False)

    # mana sinks: spend what we are not holding
    spare = mana - hold
    for c in me.board:
        if c.code == "S3":
            while spare >= 3:
                c.base_p += 1
                c.base_t += 1
                spare -= 3
    refresh(me.board)
    me.open_mana = hold if (hold and mana >= hold) else 0

    # aristocrats: sacrifice tokens for lethal drain
    if any(c.code == "SO" for c in me.board):
        ars = sum(c.code == "AR" for c in me.board)
        fodder = [c for c in me.board if c.code not in ("SO", "AR", "CM")]
        if ars and len(fodder) * ars >= opp.life:
            for c in fodder:
                kill(me, c, opp)

    if any(c[0] != "L" and COST[c[:-1]] <= me.n_lands and not me.can_cast(c, 99)
           for c in me.hand):
        me.stats["stuck"] += 1


def combat(att, dfn):
    ready = [c for c in att.board if not c.sick and c.code not in ("K1", "K2")]
    if not ready:
        return
    blockers = list(dfn.board)
    total_power = sum(c.power for c in ready)
    alpha = total_power >= dfn.life or len(ready) > len(blockers) + 2
    attackers = []
    for c in ready:
        can_block = [b for b in blockers if c.flying <= b.flying]
        bad = any(b.power >= c.tough and b.tough > c.power for b in can_block)
        if alpha or not bad:
            attackers.append(c)
    if not attackers:
        return
    incoming = sum(a.power for a in attackers)
    attackers.sort(key=lambda a: a.power, reverse=True)
    unblocked = []
    for a in attackers:
        legal = [b for b in blockers if a.flying <= b.flying]
        eat = [b for b in legal if b.tough > a.power and b.power >= a.tough]
        trade = [b for b in legal if b.power >= a.tough and b.value() <= a.value()]
        wall = [b for b in legal if b.tough > a.power]
        choice = None
        if eat:
            choice = min(eat, key=Creature.value)
        elif trade:
            choice = min(trade, key=Creature.value)
        elif wall:
            choice = min(wall, key=Creature.value)
        elif incoming >= dfn.life and legal:
            choice = min(legal, key=Creature.value)
        if choice is None:
            unblocked.append(a)
            continue
        blockers.remove(choice)
        incoming -= a.power
        if choice.power >= a.tough:
            kill(att, a, dfn)
        if a.power >= choice.tough and choice in dfn.board:
            kill(dfn, choice, att)
    for a in unblocked:
        dfn.life -= a.power
        att.dealt["flyers" if a.flying else "ground"] += a.power


def _reason(p):
    d = p.dealt
    return max(d, key=d.get) if any(d.values()) else "ground"


def play_game(deck_a, deck_b, rng, a_first=True, mulligan=True, life=20, colors=2,
              commander=False, free_mull=False, max_turns=30):
    p = [Player(deck_a, rng, mulligan, life, colors, commander, free_mull),
         Player(deck_b, rng, mulligan, life, 2, commander, free_mull)]
    order = [0, 1] if a_first else [1, 0]
    for turn in range(1, max_turns + 1):
        for i in order:
            me, opp = p[i], p[1 - i]
            if not (turn == 1 and i == order[0]):
                me.draw()
            if me.has("CM"):
                me.draw()
            if me.decked:
                return 1 - i, turn, p[0].stats, p[1].stats, "decking"
            me.land_drop = False
            me.open_mana = 0
            if me.has("K1") and me.has("K2"):
                return i, turn, p[0].stats, p[1].stats, "combo"
            for c in me.board:
                c.sick = False
            combat(me, opp)
            if opp.life <= 0:
                return i, turn, p[0].stats, p[1].stats, _reason(me)
            main_phase(me, opp)
            if opp.life <= 0:
                return i, turn, p[0].stats, p[1].stats, "drain"
            if me.life <= 0:
                return 1 - i, turn, p[0].stats, p[1].stats, _reason(opp)
            if turn == 4:
                me.stats["screw"] = me.n_lands <= 2
                me.stats["flood"] = len(me.hand_lands()) >= 3
    w = (0 if p[0].life > p[1].life else 1) if p[0].life != p[1].life else rng.randint(0, 1)
    return w, max_turns, p[0].stats, p[1].stats, "timeout"


def match(deck_a, deck_b, games, seed, mulligan=True, life=20, a_first=None, colors=2,
          commander=False, free_mull=False, max_turns=30):
    rng = random.Random(seed)
    wins = turns = screw = flood = stuck = 0
    won, lost = {}, {}
    for g in range(games):
        first = (g % 2 == 0) if a_first is None else a_first
        w, t, sa, _, how = play_game(deck_a, deck_b, rng, first, mulligan, life, colors,
                                     commander, free_mull, max_turns)
        wins += (w == 0)
        bucket = won if w == 0 else lost
        bucket[how] = bucket.get(how, 0) + 1
        turns += t
        screw += sa["screw"]
        flood += sa["flood"]
        stuck += sa["stuck"] > 0
    return {"win": wins / games, "turns": turns / games,
            "screw": screw / games, "flood": flood / games, "color_stuck": stuck / games,
            "won_by": {k: v / games for k, v in won.items()},
            "lost_to": {k: v / games for k, v in lost.items()}}
