"""Midea Cloud API client for boiler control."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import random
import string
import time
from datetime import UTC, datetime
from typing import Any

import requests

from .const import (
    API_URL,
    APP_ID,
    APP_KEY,
    HMAC_KEY,
    IOT_KEY,
)

_LOGGER = logging.getLogger(__name__)


class MideaCloudError(Exception):
    """Midea cloud API error."""


class MideaCloudClient:
    """Midea SmartHome cloud API client."""

    def __init__(
        self,
        email: str,
        password: str,
        uid: str | None = None,
        access_token: str | None = None,
        token_pwd: str | None = None,
        token_expiry: float | None = None,
    ) -> None:
        """Initialize the client."""
        self._email = email
        self._password = password
        self._device_id = hashlib.md5(email.encode()).hexdigest()
        self._auth_base = base64.b64encode(
            f"{APP_KEY}:{IOT_KEY}".encode()
        ).decode()
        self._uid = uid
        self._access_token = access_token
        self._token_pwd = token_pwd
        self._token_expiry = token_expiry
        self._login_id: str | None = None

    @property
    def uid(self) -> str | None:
        """Return the current uid."""
        return self._uid

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def token_pwd(self) -> str | None:
        """Return the refresh token (tokenPwd)."""
        return self._token_pwd

    @property
    def token_expiry(self) -> float | None:
        """Return the access token expiry timestamp (ms epoch)."""
        return self._token_expiry

    def has_session(self) -> bool:
        """Return True if a cached session exists."""
        return self._uid is not None and self._access_token is not None

    def token_needs_refresh(self) -> bool:
        """Return True if the access token is expired or about to expire."""
        if not self._token_expiry:
            return True
        now_ms = time.time() * 1000
        return now_ms >= (self._token_expiry - 60_000)

    def _make_sign(self, data_json: str, random_str: str) -> str:
        """Create HMAC-SHA256 signature."""
        msg = IOT_KEY + data_json + random_str
        return hmac.new(
            HMAC_KEY.encode("ascii"), msg.encode("ascii"), hashlib.sha256
        ).hexdigest()

    def _make_general_data(self) -> dict[str, Any]:
        """Create general request data fields."""
        return {
            "src": APP_ID,
            "format": "2",
            "stamp": datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
            "platformId": "1",
            "deviceId": self._device_id,
            "reqId": "".join(random.choices("0123456789abcdef", k=32)),
            "uid": self._uid,
            "clientType": "1",
            "appId": APP_ID,
            "language": "en_US",
        }

    def _api_request(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send an API request to Midea cloud."""
        url = API_URL + endpoint

        if not data.get("reqId"):
            data["reqId"] = "".join(random.choices("0123456789abcdef", k=32))
        if not data.get("stamp"):
            data["stamp"] = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

        body_json = json.dumps(data)
        random_str = str(int(time.time()))
        sign = self._make_sign(body_json, random_str)

        headers = {
            "content-type": "application/json; charset=utf-8",
            "secretVersion": "1",
            "sign": sign,
            "random": random_str,
            "x-recipe-app": APP_ID,
            "authorization": f"Basic {self._auth_base}",
        }
        if self._access_token:
            headers["accessToken"] = self._access_token
        if self._uid:
            headers["uid"] = self._uid

        resp = requests.post(url, data=body_json, headers=headers, timeout=15)
        result = resp.json()

        code = str(result.get("code", ""))
        if code != "0":
            msg = result.get("msg", "Unknown error")
            _LOGGER.error("Midea API error on %s: code=%s msg=%s", endpoint, code, msg)
            if code in ("1306", "3106", "3144"):
                _LOGGER.info("Session error %s, attempting token refresh", code)
                if self.refresh_token():
                    return self._api_request(endpoint, data)
                _LOGGER.info("Token refresh failed, performing full login")
                self._access_token = None
                self._uid = None
                self.login()
                return self._api_request(endpoint, data)
            raise MideaCloudError(f"API error {code}: {msg}")

        return result

    def login(self) -> None:
        """Authenticate to Midea cloud."""
        # Step 1: Get login ID
        data = self._make_general_data()
        data["loginAccount"] = self._email
        resp = self._api_request("/v1/user/login/id/get", data)
        self._login_id = resp["data"]["loginId"]

        # Step 2: Login with credentials
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        md5_pwd = hashlib.md5(
            hashlib.md5(self._password.encode()).hexdigest().encode()
        ).hexdigest()
        sha256_pwd = hashlib.sha256(self._password.encode()).hexdigest()
        iampwd = hashlib.sha256(
            (self._login_id + md5_pwd + APP_KEY).encode()
        ).hexdigest()
        password_hash = hashlib.sha256(
            (self._login_id + sha256_pwd + APP_KEY).encode()
        ).hexdigest()

        iot_data = self._make_general_data()
        iot_data.pop("uid")
        iot_data.update(
            {
                "iampwd": iampwd,
                "loginAccount": self._email,
                "password": password_hash,
                "stamp": stamp,
            }
        )
        login_data = {
            "iotData": iot_data,
            "data": {
                "appKey": APP_KEY,
                "deviceId": self._device_id,
                "platform": "2",
            },
            "stamp": stamp,
        }
        resp = self._api_request("/mj/user/login", login_data)
        self._uid = resp["data"]["uid"]
        self._access_token = resp["data"]["mdata"]["accessToken"]
        token_info = resp["data"]["mdata"].get("tokenPwdInfo", {})
        self._token_pwd = token_info.get("tokenPwd")
        self._token_expiry = token_info.get("expiredDate")
        _LOGGER.info("Midea cloud login successful, uid=%s", self._uid)

    def refresh_token(self) -> bool:
        """Refresh the access token using tokenPwd (autoLogin).

        Returns True if refresh succeeded.
        """
        if not self._token_pwd or not self._uid:
            return False

        data = self._make_general_data()
        data["data"] = {
            "rule": 1,
            "platform": 10,
            "appKey": APP_KEY,
            "deviceId": self._device_id,
            "deviceName": "Home Assistant",
            "loginType": 1,
            "clientData": {},
            "iotAppid": APP_ID,
            "uid": self._uid,
            "tokenPwd": self._token_pwd,
        }
        resp = self._api_request("/mj/user/autoLogin", data)
        new_token = resp.get("data", {}).get("accessToken")
        new_expiry = resp.get("data", {}).get("expired")
        if new_token:
            self._access_token = new_token
            self._token_expiry = new_expiry
            _LOGGER.info("Midea token refreshed, expires=%s", new_expiry)
            return True
        return False

    def get_status(self, appliance_code: str) -> dict[str, Any]:
        """Get device status."""
        if not self._access_token:
            self.login()

        data = self._make_general_data()
        data["applianceCode"] = appliance_code
        resp = self._api_request("/v1/device/status/lua/get", data)
        return resp.get("data", {})

    def send_command(
        self, appliance_code: str, control: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a control command to the device."""
        if not self._access_token:
            self.login()

        data = self._make_general_data()
        data["applianceCode"] = appliance_code
        data["command"] = {
            "control": control,
            "controlChannel": "COMMON_LUA",
        }
        resp = self._api_request("/v1/device/lua/control", data)
        return resp.get("data", {}).get("status", {})

    def list_appliances(self) -> list[dict[str, Any]]:
        """List all appliances on the account."""
        if not self._access_token:
            self.login()

        data = self._make_general_data()
        resp = self._api_request("/v1/appliance/user/list/get", data)
        appliances = resp.get("data", {}).get("list", [])
        # Normalize: the API returns "id" not "applianceCode"
        for app in appliances:
            if "applianceCode" not in app and "id" in app:
                app["applianceCode"] = app["id"]
        return appliances
