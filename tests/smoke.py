"""Exercise the browser-facing routes on a running Compose stack."""

import json
import os
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

origin = os.getenv("APP_ORIGIN", "http://localhost:8088")
client = build_opener(HTTPCookieProcessor(CookieJar()))
other = build_opener(HTTPCookieProcessor(CookieJar()))


def request(path, status, *, method="GET", data=None, browser=client, source=origin):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Origin": source, "Content-Type": "application/json"}
    query = Request(f"{origin}{path}", method=method, data=body, headers=headers)
    try:
        response = browser.open(query, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        payload = response.read().decode()
        assert response.code == status, (path, response.code, payload)
        return payload, response.headers


def api(path, status, **options):
    payload, _headers = request(f"/api/{path}", status, **options)
    return json.loads(payload) if payload else None


assert "<title>Planroom" in request("/", 200)[0]
assert api("health/live", 200) == {"status": "ok"}
assert api("health/ready", 200) == {"status": "ready"}
assert "/api/plan" in api("openapi.json", 200)["paths"]
api("workspace", 401)
api("auth/demo", 403, method="POST", source="https://another-site.example")
credentials = {"email": f"smoke-{uuid.uuid4().hex}@example.org", "password": "a-long-sample-password"}
registration = {**credentials, "name": "Smoke Test"}
payload, headers = request("/api/auth/register", 201, method="POST", data=registration)
assert json.loads(payload) == {"name": "Smoke Test", "plan": None, "questionnaire": None}
cookie = headers["Set-Cookie"]
assert "HttpOnly" in cookie and "Path=/api" in cookie and "SameSite=lax" in cookie
assert ("; Secure" in cookie) == origin.startswith("https://")
api("auth/register", 409, method="POST", data=registration)
plan = {"title": "Cash reserve", "target": 10000, "saved": 4000, "monthly": 1000}
questionnaire = {"horizon": 2, "reaction": 1, "experience": 3}
api("plan", 422, method="PUT", data={**plan, "target": -100})
api("plan", 403, method="PUT", data=plan, source="https://another-site.example")
assert api("plan", 200, method="PUT", data=plan) == plan
api("questionnaire", 422, method="PUT", data={**questionnaire, "horizon": True})
assert api("questionnaire", 200, method="PUT", data=questionnaire) == questionnaire
assert api("auth/demo", 201, method="POST", browser=other)["plan"]["title"] == "Emergency fund"
assert api("workspace", 200, browser=other)["plan"] != plan
assert api("workspace", 200)["questionnaire"] == questionnaire
api("auth/logout", 204, method="POST")
api("workspace", 401)
api("auth/login", 401, method="POST", data={**credentials, "password": "incorrect-password"})
assert api("auth/login", 200, method="POST", data=credentials)["plan"] == plan
print("Planroom smoke checks passed.")
