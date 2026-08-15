from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from trading212_mcp.client import (
    AuthenticationError,
    MalformedResponseError,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    Trading212APIError,
    Trading212Client,
    Trading212NetworkError,
)
from trading212_mcp.config import Environment, Settings

ACCOUNT = {
    "id": 12345678,
    "currency": "GBP",
    "totalValue": 15250.75,
    "cash": {"availableToTrade": 2500.5, "reservedForOrders": 150.0, "inPies": 500.0},
    "investments": {
        "currentValue": 12100.25,
        "totalCost": 10500.0,
        "realizedProfitLoss": 850.5,
        "unrealizedProfitLoss": 1600.25,
    },
}

POSITION = {
    "instrument": {
        "ticker": "AAPL_US_EQ",
        "name": "Apple Inc",
        "isin": "US0378331005",
        "currency": "USD",
    },
    "quantity": 15.5,
    "quantityAvailableForTrading": 12.5,
    "quantityInPies": 3.0,
    "currentPrice": 185.5,
    "averagePricePaid": 170.25,
    "createdAt": "2024-01-10T09:15:00Z",
    "walletImpact": {
        "currency": "GBP",
        "totalCost": 2089.45,
        "currentValue": 2275.1,
        "unrealizedProfitLoss": 185.65,
        "fxImpact": 12.3,
    },
}

ORDER = {
    "id": 123456789,
    "type": "LIMIT",
    "ticker": "AAPL_US_EQ",
    "instrument": POSITION["instrument"],
    "quantity": 5.0,
    "filledQuantity": 0.0,
    "status": "NEW",
    "side": "BUY",
    "strategy": "QUANTITY",
    "initiatedFrom": "API",
    "extendedHours": False,
    "createdAt": "2024-01-15T10:30:00Z",
    "currency": "GBP",
    "limitPrice": 150.0,
    "timeInForce": "DAY",
}

DIVIDEND = {
    "ticker": "AAPL_US_EQ",
    "instrument": POSITION["instrument"],
    "type": "ORDINARY",
    "amount": 12.5,
    "amountInEuro": 14.7,
    "currency": "GBP",
    "tickerCurrency": "USD",
    "grossAmountPerShare": 0.24,
    "quantity": 65.5,
    "paidOn": "2024-02-15T00:00:00Z",
    "reference": "DIV-123456",
}

TRANSACTION = {
    "type": "DEPOSIT",
    "amount": 1000.0,
    "currency": "GBP",
    "dateTime": "2024-01-10T14:30:00Z",
    "reference": "TXN-123456",
}


def settings(environment: Environment = Environment.DEMO) -> Settings:
    return Settings(api_key="api-key", api_secret="api-secret", environment=environment)


def transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment", "host"),
    [(Environment.DEMO, "demo.trading212.com"), (Environment.LIVE, "live.trading212.com")],
)
async def test_account_request_uses_basic_auth_get_timeout_and_selected_environment(
    environment: Environment,
    host: str,
) -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["url"] = request.url
        observed["authorization"] = request.headers.get("Authorization")
        observed["timeout"] = request.extensions.get("timeout")
        return httpx.Response(200, json=ACCOUNT)

    async with Trading212Client(settings(environment), transport=transport(handler)) as client:
        result = await client.get_account()

    expected_token = base64.b64encode(b"api-key:api-secret").decode("ascii")
    assert result == ACCOUNT
    assert observed["method"] == "GET"
    assert observed["url"] == httpx.URL(f"https://{host}/api/v0/equity/account/summary")
    assert observed["authorization"] == f"Basic {expected_token}"
    assert observed["timeout"] == {
        "connect": 5.0,
        "read": 10.0,
        "write": 10.0,
        "pool": 5.0,
    }


@pytest.mark.asyncio
async def test_cash_is_a_minimal_projection_of_account_summary() -> None:
    async with Trading212Client(
        settings(), transport=transport(lambda _: httpx.Response(200, json=ACCOUNT))
    ) as client:
        result = await client.get_cash()

    assert result == {
        "currency": "GBP",
        "availableToTrade": 2500.5,
        "reservedForOrders": 150.0,
        "inPies": 500.0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_path", "payload"),
    [
        ("get_positions", "/api/v0/equity/positions", [POSITION]),
        ("get_orders", "/api/v0/equity/orders", [ORDER]),
    ],
)
async def test_collection_methods_use_only_documented_get_endpoints(
    method_name: str,
    expected_path: str,
    payload: list[dict[str, object]],
) -> None:
    observed_method = ""
    observed_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_method, observed_path
        observed_method = request.method
        observed_path = request.url.path
        return httpx.Response(200, json=payload)

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        result = await getattr(client, method_name)()

    assert result == payload
    assert observed_method == "GET"
    assert observed_path == expected_path


@pytest.mark.asyncio
async def test_positions_passes_exact_ticker_filter() -> None:
    observed_query = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_query
        observed_query = request.url.query
        return httpx.Response(200, json=[POSITION])

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        result = await client.get_positions(ticker="AAPL_US_EQ")

    assert result == [POSITION]
    assert observed_query == b"ticker=AAPL_US_EQ"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_path", "item", "ticker"),
    [
        ("get_order_history", "/api/v0/equity/history/orders", {"order": ORDER}, "AAPL_US_EQ"),
        ("get_transactions", "/api/v0/equity/history/transactions", TRANSACTION, None),
        ("get_dividends", "/api/v0/equity/history/dividends", DIVIDEND, "AAPL_US_EQ"),
    ],
)
async def test_history_methods_return_a_bounded_page_and_next_path(
    method_name: str,
    expected_path: str,
    item: dict[str, object],
    ticker: str | None,
) -> None:
    observed_url = httpx.URL("https://example.invalid")
    next_path = f"{expected_path}?limit=2&cursor=1705326600000"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_url
        observed_url = request.url
        return httpx.Response(200, json={"items": [item], "nextPagePath": next_path})

    kwargs: dict[str, object] = {"limit": 2}
    if ticker is not None:
        kwargs["ticker"] = ticker
    async with Trading212Client(settings(), transport=transport(handler)) as client:
        result = await getattr(client, method_name)(**kwargs)

    assert result == {"items": [item], "next_page_path": next_path}
    assert observed_url.path == expected_path
    assert observed_url.params["limit"] == "2"
    if ticker is not None:
        assert observed_url.params["ticker"] == ticker


@pytest.mark.asyncio
async def test_next_page_path_is_followed_without_rebuilding_its_cursor() -> None:
    observed_url = httpx.URL("https://example.invalid")
    next_path = (
        "/api/v0/equity/history/transactions?limit=2&cursor=opaque-cursor"
        "&time=2024-01-10T14%3A30%3A00Z"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_url
        observed_url = request.url
        return httpx.Response(200, json={"items": [TRANSACTION], "nextPagePath": None})

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        result = await client.get_transactions(next_page_path=next_path)

    assert result == {"items": [TRANSACTION], "next_page_path": None}
    assert observed_url == httpx.URL(f"https://demo.trading212.com{next_path}")


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 51])
async def test_history_page_size_is_limited_to_official_bounds(limit: int) -> None:
    async with Trading212Client(
        settings(), transport=transport(lambda _: httpx.Response(500))
    ) as client:
        with pytest.raises(ValueError, match="limit must be between 1 and 50"):
            await client.get_transactions(limit=limit)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "next_path",
    [
        "https://attacker.example/api/v0/equity/history/transactions?limit=20",
        "//attacker.example/api/v0/equity/history/transactions?limit=20",
        "/api/v0/equity/orders?limit=20",
        "/api/v0/equity/history/dividends?limit=20",
        "/api/v0/equity/history/transactions?unknown=value",
        "/api/v0/equity/history/transactions?limit=20#fragment",
    ],
)
async def test_transactions_reject_untrusted_pagination_paths(next_path: str) -> None:
    async with Trading212Client(
        settings(), transport=transport(lambda _: httpx.Response(500))
    ) as client:
        with pytest.raises(ValueError, match="Invalid next_page_path"):
            await client.get_transactions(next_page_path=next_path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exception_type", "message"),
    [
        (401, AuthenticationError, "authentication failed"),
        (403, PermissionDeniedError, "permission denied"),
        (408, RequestTimeoutError, "timed out"),
        (400, Trading212APIError, "status 400"),
        (500, Trading212APIError, "status 500"),
    ],
)
async def test_http_failures_are_sanitized(
    status: int,
    exception_type: type[Exception],
    message: str,
) -> None:
    secret_body = "api-key api-secret Authorization: Basic sensitive"
    async with Trading212Client(
        settings(),
        transport=transport(lambda _: httpx.Response(status, text=secret_body)),
    ) as client:
        with pytest.raises(exception_type) as captured:
            await client.get_account()

    rendered = str(captured.value)
    assert message in rendered
    assert secret_body not in rendered
    assert "api-key" not in rendered
    assert "api-secret" not in rendered
    assert "Authorization" not in rendered


@pytest.mark.asyncio
async def test_rate_limit_error_exposes_only_safe_reset_metadata_and_does_not_retry() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            text="secret response body",
            headers={"x-ratelimit-reset": "1760000000"},
        )

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        with pytest.raises(RateLimitError) as captured:
            await client.get_account()

    assert calls == 1
    assert captured.value.reset_at == 1760000000
    assert str(captured.value) == "Trading 212 rate limit exceeded; reset at 1760000000"


@pytest.mark.asyncio
async def test_network_error_does_not_echo_request_or_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("api-key api-secret", request=request)

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        with pytest.raises(Trading212NetworkError) as captured:
            await client.get_account()

    assert str(captured.value) == "Unable to reach the Trading 212 API"


@pytest.mark.asyncio
async def test_httpx_timeout_maps_to_sanitized_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("api-key api-secret", request=request)

    async with Trading212Client(settings(), transport=transport(handler)) as client:
        with pytest.raises(RequestTimeoutError) as captured:
            await client.get_account()

    assert str(captured.value) == "Trading 212 API request timed out"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "payload"),
    [
        ("get_account", []),
        ("get_account", {"currency": "GBP"}),
        ("get_positions", {}),
        ("get_orders", {"orders": []}),
        ("get_transactions", []),
        ("get_transactions", {"items": {}, "nextPagePath": None}),
        ("get_transactions", {"items": [], "nextPagePath": 123}),
    ],
)
async def test_malformed_success_payloads_are_rejected(
    method_name: str,
    payload: object,
) -> None:
    async with Trading212Client(
        settings(), transport=transport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(MalformedResponseError, match="malformed response"):
            await getattr(client, method_name)()
