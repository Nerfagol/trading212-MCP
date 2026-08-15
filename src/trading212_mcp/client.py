"""Small, allowlisted, GET-only client for the Trading 212 Public API."""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self, cast
from urllib.parse import parse_qsl, urlsplit

import httpx

from trading212_mcp.config import Settings

JsonObject = dict[str, Any]
JsonList = list[JsonObject]
Page = dict[str, Any]


class Trading212Error(RuntimeError):
    """Base class for safe, model-readable Trading 212 errors."""


class AuthenticationError(Trading212Error):
    """The key pair was rejected or belongs to another environment."""


class PermissionDeniedError(Trading212Error):
    """The key lacks a required read permission."""


class RequestTimeoutError(Trading212Error):
    """Trading 212 did not complete the request within the timeout."""


class RateLimitError(Trading212Error):
    """The Trading 212 account-level rate limit was reached."""

    def __init__(self, reset_at: int | None) -> None:
        self.reset_at = reset_at
        message = "Trading 212 rate limit exceeded"
        if reset_at is not None:
            message += f"; reset at {reset_at}"
        super().__init__(message)


class Trading212APIError(Trading212Error):
    """Trading 212 returned a non-success response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Trading 212 API returned status {status_code}")


class Trading212NetworkError(Trading212Error):
    """The Trading 212 API could not be reached."""


class MalformedResponseError(Trading212Error):
    """A success response did not match the documented top-level shape."""


_ACCOUNT_PATH = "/api/v0/equity/account/summary"
_POSITIONS_PATH = "/api/v0/equity/positions"
_ORDERS_PATH = "/api/v0/equity/orders"
_ORDER_HISTORY_PATH = "/api/v0/equity/history/orders"
_TRANSACTIONS_PATH = "/api/v0/equity/history/transactions"
_DIVIDENDS_PATH = "/api/v0/equity/history/dividends"

_READ_ONLY_PATHS = frozenset(
    {
        _ACCOUNT_PATH,
        _POSITIONS_PATH,
        _ORDERS_PATH,
        _ORDER_HISTORY_PATH,
        _TRANSACTIONS_PATH,
        _DIVIDENDS_PATH,
    }
)

_PAGINATION_QUERY_KEYS = {
    _ORDER_HISTORY_PATH: frozenset({"limit", "cursor", "ticker"}),
    _TRANSACTIONS_PATH: frozenset({"limit", "cursor", "time"}),
    _DIVIDENDS_PATH: frozenset({"limit", "cursor", "ticker"}),
}


class Trading212Client:
    """Async Trading 212 client whose network surface is fixed to GET endpoints."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_origin = httpx.URL(settings.base_url).copy_with(path="/")
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth(settings.api_key, settings.api_secret),
            base_url=api_origin,
            headers={"Accept": "application/json", "User-Agent": "trading212-mcp/0.1.0"},
            timeout=httpx.Timeout(10.0, connect=5.0, pool=5.0),
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._http.aclose()

    async def get_account(self) -> JsonObject:
        """Retrieve the account summary and validate its documented core shape."""
        payload = await self._get_json(_ACCOUNT_PATH)
        if not self._is_account(payload):
            raise MalformedResponseError("Trading 212 returned a malformed response")
        return cast(JsonObject, payload)

    async def get_cash(self) -> JsonObject:
        """Return only cash metrics and currency from the account summary."""
        account = await self.get_account()
        cash = cast(JsonObject, account["cash"])
        return {
            "currency": account["currency"],
            "availableToTrade": cash["availableToTrade"],
            "reservedForOrders": cash["reservedForOrders"],
            "inPies": cash["inPies"],
        }

    async def get_positions(self, ticker: str | None = None) -> JsonList:
        """Retrieve all open positions, optionally filtered by an exact ticker."""
        params = {"ticker": ticker} if ticker is not None else None
        return await self._get_collection(_POSITIONS_PATH, params=params)

    async def get_orders(self) -> JsonList:
        """Retrieve all current pending orders."""
        return await self._get_collection(_ORDERS_PATH)

    async def get_order_history(
        self,
        *,
        limit: int = 20,
        ticker: str | None = None,
        next_page_path: str | None = None,
    ) -> Page:
        """Retrieve one page of historical orders."""
        params: dict[str, str | int] = {"limit": limit}
        if ticker is not None:
            params["ticker"] = ticker
        return await self._get_page(
            _ORDER_HISTORY_PATH,
            limit=limit,
            params=params,
            next_page_path=next_page_path,
        )

    async def get_transactions(
        self,
        *,
        limit: int = 20,
        next_page_path: str | None = None,
    ) -> Page:
        """Retrieve one page of cash transactions."""
        return await self._get_page(
            _TRANSACTIONS_PATH,
            limit=limit,
            params={"limit": limit},
            next_page_path=next_page_path,
        )

    async def get_dividends(
        self,
        *,
        limit: int = 20,
        ticker: str | None = None,
        next_page_path: str | None = None,
    ) -> Page:
        """Retrieve one page of paid dividends."""
        params: dict[str, str | int] = {"limit": limit}
        if ticker is not None:
            params["ticker"] = ticker
        return await self._get_page(
            _DIVIDENDS_PATH,
            limit=limit,
            params=params,
            next_page_path=next_page_path,
        )

    async def _get_collection(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> JsonList:
        payload = await self._get_json(path, params=params)
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise MalformedResponseError("Trading 212 returned a malformed response")
        return cast(JsonList, payload)

    async def _get_page(
        self,
        expected_path: str,
        *,
        limit: int,
        params: Mapping[str, str | int],
        next_page_path: str | None,
    ) -> Page:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")

        if next_page_path is None:
            payload = await self._get_json(expected_path, params=params)
        else:
            self._validate_next_page_path(next_page_path, expected_path)
            payload = await self._get_json(next_page_path)

        if not isinstance(payload, dict):
            raise MalformedResponseError("Trading 212 returned a malformed response")
        items = payload.get("items")
        next_path = payload.get("nextPagePath")
        if (
            not isinstance(items, list)
            or not all(isinstance(item, dict) for item in items)
            or (next_path is not None and not isinstance(next_path, str))
        ):
            raise MalformedResponseError("Trading 212 returned a malformed response")
        if isinstance(next_path, str):
            self._validate_next_page_path(next_path, expected_path)
        return {"items": items, "next_page_path": next_path}

    async def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> object:
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.path not in _READ_ONLY_PATHS:
            raise ValueError("Path is not in the read-only allowlist")

        try:
            response = await self._http.get(path, params=params)
        except httpx.TimeoutException:
            raise RequestTimeoutError("Trading 212 API request timed out") from None
        except httpx.RequestError:
            raise Trading212NetworkError("Unable to reach the Trading 212 API") from None

        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError:
            raise MalformedResponseError("Trading 212 returned a malformed response") from None

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status == 401:
            raise AuthenticationError(
                "Trading 212 authentication failed; verify credentials and environment"
            )
        if status == 403:
            raise PermissionDeniedError("Trading 212 API permission denied")
        if status == 408:
            raise RequestTimeoutError("Trading 212 API request timed out")
        if status == 429:
            raw_reset = response.headers.get("x-ratelimit-reset", "")
            reset_at = int(raw_reset) if raw_reset.isdecimal() else None
            raise RateLimitError(reset_at)
        raise Trading212APIError(status)

    @staticmethod
    def _validate_next_page_path(next_page_path: str, expected_path: str) -> None:
        parsed = urlsplit(next_page_path)
        if (
            not next_page_path
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or parsed.path != expected_path
        ):
            raise ValueError("Invalid next_page_path")
        try:
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise ValueError("Invalid next_page_path") from None
        keys = [key for key, _ in pairs]
        allowed_keys = _PAGINATION_QUERY_KEYS[expected_path]
        if not pairs or len(keys) != len(set(keys)) or not set(keys) <= allowed_keys:
            raise ValueError("Invalid next_page_path")

    @staticmethod
    def _is_account(payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        cash = payload.get("cash")
        investments = payload.get("investments")
        return (
            isinstance(payload.get("id"), int)
            and not isinstance(payload.get("id"), bool)
            and isinstance(payload.get("currency"), str)
            and Trading212Client._is_number(payload.get("totalValue"))
            and isinstance(cash, dict)
            and all(
                Trading212Client._is_number(cash.get(field))
                for field in ("availableToTrade", "reservedForOrders", "inPies")
            )
            and isinstance(investments, dict)
            and all(
                Trading212Client._is_number(investments.get(field))
                for field in (
                    "currentValue",
                    "totalCost",
                    "realizedProfitLoss",
                    "unrealizedProfitLoss",
                )
            )
        )

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, int | float) and not isinstance(value, bool)
