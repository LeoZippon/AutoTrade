"""The client↔server route contract.

A live 404 once reached production behind a wholly green suite: `app.js` called
`/api/trading/{env}/executions` while the server registered `/deals`, and
because `api()` throws inside `Promise.all`, the whole 模拟 route died. Nothing
compared the two sides.

This module generalises that check rather than pinning the one instance: every
API path the SPA can request is parsed out of `app.js` and matched against the
routes `create_app()` actually registers, and the payload keys the SPA reads
are asserted against a real response.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autotrade.webui.server import create_app

APP_JS = Path(__file__).resolve().parents[2] / "src/autotrade/webui/static/app.js"
# `api(`…`)`, `new EventSource(`…`)`, and bare "/api/…" string literals.
_TEMPLATE_CALL = re.compile(r"(?:api|EventSource)\(\s*`")
_PLAIN_LITERAL = re.compile(r'"(/api/[^"]*)"')
# `const base = `/api/…`;` then `api(base)` / `api(`${base}/orders`)`.
_CONST_TEMPLATE = re.compile(r"const\s+(\w+)\s*=\s*`(/api/[^`]*)`")
_BARE_CALL = re.compile(r"(?:api|EventSource)\(\s*(\w+)\s*[,)]")
_INTERPOLATION = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


def _template_literals(source: str) -> list[tuple[int, str]]:
    """Every template literal passed to api()/EventSource, backtick-balanced.

    A literal may nest another template inside `${ … }` (the orders route
    does), so a naive regex to the next backtick truncates it."""
    literals: list[tuple[int, str]] = []
    for match in _TEMPLATE_CALL.finditer(source):
        start = match.start()
        index = match.end()
        depth = 0
        buffer: list[str] = []
        while index < len(source):
            char = source[index]
            if char == "\\":
                buffer.append(source[index : index + 2])
                index += 2
                continue
            if char == "`" and depth == 0:
                break
            if source.startswith("${", index):
                depth += 1
                buffer.append("${")
                index += 2
                continue
            if char == "}" and depth:
                depth -= 1
                buffer.append("}")
                index += 1
                continue
            buffer.append(char)
            index += 1
        literals.append((start, "".join(buffer)))
    return literals


def _normalize(path: str) -> str:
    """A comparable path shape: parameters collapsed, query string removed.

    Interpolations collapse FIRST: a `${query ? "&" : "?"}` separator contains
    a literal `?`, so splitting on `?` before collapsing truncates the path."""
    previous = None
    while previous != path:  # nested ${ … ${ … } … }
        previous = path
        path = _INTERPOLATION.sub("{}", path)
    path = re.sub(r"\{[^{}]*\}", "{}", path)
    # A placeholder glued to a path segment (`…/equity{}`, `…/deals{}`,
    # `…/stream{}{}offset={}`) is an interpolated query string, not a path
    # parameter: the path ends where it starts.
    path = re.sub(r"(?<=[^/]){\}.*$", "", path)
    path = path.split("?", 1)[0].split("#", 1)[0]
    return path.rstrip("/") or "/"


def client_api_paths() -> set[str]:
    source = APP_JS.read_text(encoding="utf-8")
    # A route may be assembled in a local `const base = `/api/…`` and then
    # requested bare or extended. The same local name is reused in different
    # functions, so a binding is resolved by lexical scope — the nearest one
    # ABOVE the call site — not by cross-product, which would invent routes.
    bindings: list[tuple[int, str, str]] = [
        (match.start(), match.group(1), match.group(2))
        for match in _CONST_TEMPLATE.finditer(source)
    ]

    def resolve(position: int, name: str) -> str | None:
        nearest = [value for start, bound, value in bindings if bound == name and start < position]
        return nearest[-1] if nearest else None

    paths: set[str] = set()
    for position, literal in _template_literals(source):
        resolved = literal
        for _start, name, _value in bindings:
            token = "${" + name + "}"
            if token in resolved:
                value = resolve(position, name)
                if value is not None:
                    resolved = resolved.replace(token, value)
        normalized = _normalize(resolved)
        if normalized.startswith("/api/"):
            paths.add(normalized)
    for match in _BARE_CALL.finditer(source):
        value = resolve(match.start(), match.group(1))
        if value is not None:
            paths.add(_normalize(value))
    for literal in _PLAIN_LITERAL.findall(source):
        paths.add(_normalize(literal))
    return paths


def server_api_paths() -> set[str]:
    app = create_app(Path("."))
    return {
        _normalize(route.path)
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/")
    }


def test_the_extractor_finds_the_routes_the_console_really_calls():
    """A parser that silently found nothing would make the check vacuous."""
    paths = client_api_paths()
    assert len(paths) >= 20, sorted(paths)
    for expected in (
        "/api/experiments",
        "/api/experiments/{}",
        "/api/experiments/{}/control",
        "/api/experiments/{}/trace/stream",
        "/api/trading/{}/deals",
        "/api/parameter-schema",
        # Assembled from a local `const base`, not written inline.
        "/api/experiments/{}/analysis/{}/{}",
        "/api/experiments/{}/folds/{}/{}/orders",
    ):
        assert expected in paths, sorted(paths)


def test_every_api_path_the_console_calls_is_a_registered_route():
    missing = sorted(client_api_paths() - server_api_paths())
    assert missing == [], (
        "app.js calls API paths the server does not register (a live 404): "
        f"{missing}"
    )


def test_the_route_check_fails_on_a_renamed_route():
    """The mutation: the exact C1 defect must be detectable."""
    server = server_api_paths()
    # `/deals` was once called `/executions` on the client only.
    assert "/api/trading/{}/deals" in server
    assert "/api/trading/{}/executions" not in server
    assert sorted({"/api/trading/{}/executions"} - server) == ["/api/trading/{}/executions"]


def test_paper_bundle_serves_the_key_names_the_console_reads(tmp_path: Path):
    """A status-only smoke test would have missed `payload.executions`: the
    SPA reads named keys, so the contract is the key names."""
    root = tmp_path / "data/trading/paper"
    root.mkdir(parents=True)
    (root / "orders_20260102.jsonl").write_text(
        json.dumps(
            {
                "event_id": "o1",
                "symbol": "000001.SZ",
                "action": "buy",
                "quantity": 100,
                "execute_at": "2026-01-02T09:30:00+08:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "executions_20260102.jsonl").write_text(
        json.dumps(
            {
                "event_id": "e1",
                "symbol": "000001.SZ",
                "action": "buy",
                "quantity": 100,
                "execute_at": "2026-01-02T09:30:00+08:00",
                "matched_at": "2026-01-02T09:30:00+08:00",
                "status": "filled",
                "price": 10.25,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))

    # The five requests the Paper page issues together; api() throws inside
    # Promise.all, so ONE 404 blanks the whole route.
    for route in ("snapshot", "orders", "deals", "series", "health"):
        response = client.get(f"/api/trading/paper/{route}")
        assert response.status_code == 200, route

    orders = client.get("/api/trading/paper/orders").json()
    assert "orders" in orders and orders["count"] == 1
    assert {"env", "trade_date", "available_dates", "state", "skipped_lines"} <= orders.keys()

    deals = client.get("/api/trading/paper/deals").json()
    assert "deals" in deals, "the SPA reads payload.deals, not payload.executions"
    assert "executions" not in deals
    assert deals["deals"][0]["status"] == "filled"

    roster = client.get("/api/trading/environments").json()["environments"][0]
    for key in ("env", "label", "state", "trade_date", "order_count", "deal_count",
                "skipped_lines", "stale_threshold_seconds", "snapshot"):
        assert key in roster, key
    assert "execution_count" not in roster, "the SPA reads summary.deal_count"

    series = client.get("/api/trading/paper/series").json()
    assert "series" in series and "state" in series


@pytest.mark.parametrize("route", ["orders", "deals", "series", "snapshot", "health"])
def test_the_paper_routes_the_console_reads_are_named_on_both_sides(route: str):
    assert f"/api/trading/{{}}/{route}" in client_api_paths()
    assert f"/api/trading/{{}}/{route}" in server_api_paths()
