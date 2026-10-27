"""Design one card: generate, validate, critique, refine, select, export.

1. analyse the content and load the brand spec
2. every permitted strategy yields its variants for every permitted field
3. each variant is built; one that cannot fit, or breaks a brand rule, is
   rejected with its reason
4. survivors are rendered small and scored
5. the best few are refined by local search over their parameters
6. the winner is rendered at export size and checked once more
"""

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from social_cards.brand import Brand
from social_cards.composition import Composition
from social_cards.content import Card, analyse
from social_cards.critique import Critic, Score
from social_cards.layouts import STRATEGIES, Context, DoesNotFitError, Strategy
from social_cards.render import export_png, render
from social_cards.validate import Violation, validate

PREVIEW_SCALE = 0.25
REFINE_TOP = 4
REFINE_ROUNDS = 2


class NoValidDesignError(RuntimeError):
    """No candidate passed the brand and geometry checks."""


@dataclass
class Candidate:
    strategy: Strategy
    comp: Composition
    score: Score | None = None


@dataclass
class Result:
    card: Card
    format: str
    chosen: Candidate
    considered: int
    rejected: list[tuple[str, str]] = field(default_factory=list)
    ranking: list[Candidate] = field(default_factory=list)
    image: Image.Image | None = None

    def report(self) -> str:
        lines = [
            f"{self.card.id} [{self.format}] → {self.chosen.comp.key}  {self.chosen.score}"
        ]
        if self.chosen.score.notes:
            lines.append(
                f"    notes: {', '.join(sorted(set(self.chosen.score.notes)))}"
            )
        lines.append(
            f"    {self.considered} valid candidates, {len(self.rejected)} rejected"
        )
        return "\n".join(lines)


def _build(
    ctx: Context, strategy: Strategy, params: dict, brand: Brand, rejected: list
) -> Composition | None:
    try:
        comp = strategy.build(ctx, params)
    except DoesNotFitError as err:
        rejected.append((f"{strategy.name}{params}", f"does not fit: {err}"))
        return None
    violations: list[Violation] = validate(comp, brand, ctx.card)
    if violations:
        rejected.append((comp.key, "; ".join(map(str, violations))))
        return None
    return comp


def _score(
    cands: list[Candidate], brand: Brand, card: Card, history: list[Composition]
) -> None:
    best_sizes: dict[str, float] = {}
    for c in cands:
        size = c.comp.text("headline").size
        best_sizes[c.comp.strategy] = max(size, best_sizes.get(c.comp.strategy, 0.0))
    critic = Critic(brand, card, best_sizes, history)
    for c in cands:
        c.score = critic.score(c.comp, render(c.comp, brand, scale=PREVIEW_SCALE))


def design(
    card: Card, fmt_name: str, brand: Brand, history: list[Composition] | None = None
) -> Result:
    history = history or []
    fmt = brand.format(fmt_name)
    ctx = Context(brand, fmt, card, analyse(card))
    category = brand.category(card.category)
    rejected: list[tuple[str, str]] = []
    pool: dict[str, Candidate] = {}

    for name in category["strategies"]:
        strategy = STRATEGIES[name]
        if not strategy.applicable(ctx):
            continue
        allowed = brand.raw["strategy_fields"].get(name)
        fields = [f for f in category["fields"] if allowed is None or f in allowed]
        if not fields:
            continue
        for params in strategy.variants(ctx, fields):
            comp = _build(ctx, strategy, params, brand, rejected)
            if comp is not None:
                pool.setdefault(comp.key, Candidate(strategy, comp))
    if not pool:
        reasons = "\n  ".join(f"{k}: {r}" for k, r in rejected[:12])
        raise NoValidDesignError(
            f"{card.id} [{fmt_name}]: no candidate passed validation\n  {reasons}"
        )

    cands = list(pool.values())
    _score(cands, brand, card, history)

    for _ in range(REFINE_ROUNDS):
        cands.sort(key=lambda c: c.score.total, reverse=True)
        fresh = []
        for best in cands[:REFINE_TOP]:
            for params in best.strategy.neighbours(ctx, best.comp.params):
                comp = _build(ctx, best.strategy, params, brand, rejected)
                if comp is not None and comp.key not in pool:
                    cand = Candidate(best.strategy, comp)
                    pool[comp.key] = cand
                    fresh.append(cand)
        if not fresh:
            break
        cands = list(pool.values())
        _score(cands, brand, card, history)

    cands.sort(key=lambda c: c.score.total, reverse=True)
    return Result(
        card=card,
        format=fmt_name,
        chosen=cands[0],
        considered=len(cands),
        rejected=rejected,
        ranking=cands,
    )


def export(result: Result, brand: Brand, path: Path) -> Path:
    comp = result.chosen.comp
    image = render(comp, brand)
    expected = (
        comp.fmt.width * comp.fmt.export_scale,
        comp.fmt.height * comp.fmt.export_scale,
    )
    if image.size != expected:
        raise NoValidDesignError(
            f"{result.card.id}: rendered {image.size}, expected {expected}"
        )
    export_png(image, path)
    result.image = image
    return path
