"""Read-only Asana client.

What this file guarantees, in one place:

- It only ever sends GET. There is no code path for any other method.
- It only ever talks to https://app.asana.com/api/1.0 (or, for the tests,
  a loopback address). Any other address is refused when the client is built.
- It never follows a redirect, so the token cannot be carried to another host.
- Every object id that goes into a path is checked to be digits only.
- The token is asked for at call time and is never logged, returned or put
  into an error message.

Standard library only. Python 3.8 or later.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://app.asana.com/api/1.0"
USER_AGENT = "own-asana/1.0 (read-only)"
GID_RE = re.compile(r"^[0-9]{1,31}$")
LOOPBACK_RE = re.compile(r"^http://127\.0\.0\.1:[0-9]{1,5}$")
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_RETRY_AFTER_SECONDS = 5


class AsanaError(Exception):
    """A failure talking to Asana. `kind` is a short code; `message` is safe to show."""

    def __init__(self, kind, message, status=None, retry_after=None):
        Exception.__init__(self, message)
        self.kind = kind
        self.message = message
        self.status = status
        self.retry_after = retry_after


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect. urllib then raises HTTPError for the 3xx."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_gid(value, what="id"):
    """Return the id as a string of digits, or raise."""
    text = str(value).strip() if value is not None else ""
    if not GID_RE.match(text):
        raise AsanaError("bad_argument", "The %s must be a number from Asana (digits only)." % what)
    return text


class AsanaClient(object):
    def __init__(self, token_provider, base_url=API_BASE, timeout=20, sleep=time.sleep):
        if base_url != API_BASE and not LOOPBACK_RE.match(base_url or ""):
            raise ValueError("own-asana talks to app.asana.com only")
        self._token_provider = token_provider
        self._base = base_url
        self._timeout = timeout
        self._sleep = sleep
        handlers = [_NoRedirect()]
        if base_url != API_BASE:
            # Tests only: a loopback fake server, never through a proxy.
            handlers.append(urllib.request.ProxyHandler({}))
        self._opener = urllib.request.build_opener(*handlers)

    # ---- the one place a request is made -------------------------------

    def _get(self, path, params=None, _retried=False):
        token = self._token_provider()
        if not token:
            raise AsanaError("no_token", "No Asana token is stored on this computer.")
        query = urllib.parse.urlencode(
            [(k, v) for k, v in sorted((params or {}).items()) if v is not None]
        )
        url = self._base + path + ("?" + query if query else "")
        request = urllib.request.Request(url, method="GET")
        request.add_header("Authorization", "Bearer " + token)
        request.add_header("Accept", "application/json")
        request.add_header("User-Agent", USER_AGENT)
        try:
            response = self._opener.open(request, timeout=self._timeout)
            try:
                raw = response.read(MAX_BODY_BYTES + 1)
            finally:
                response.close()
        except urllib.error.HTTPError as err:
            status = err.code
            detail = _asana_message(_read_quietly(err))
            retry_after = _retry_after(err.headers)
            err.close()
            if status == 429 and not _retried and retry_after is not None \
                    and retry_after <= MAX_RETRY_AFTER_SECONDS:
                self._sleep(retry_after)
                return self._get(path, params, _retried=True)
            raise _error_for_status(status, detail, retry_after)
        except urllib.error.URLError as err:
            reason = getattr(err, "reason", None)
            if "CERTIFICATE_VERIFY_FAILED" in str(reason):
                raise AsanaError("tls", "This computer could not check Asana's security certificate.")
            raise AsanaError("network", "Could not reach Asana. Check the internet connection.")
        except (OSError, ValueError):
            raise AsanaError("network", "Could not reach Asana. Check the internet connection.")
        if len(raw) > MAX_BODY_BYTES:
            raise AsanaError("too_large", "Asana's answer was too large. Ask for fewer items.")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise AsanaError("bad_response", "Asana sent an answer this tool could not read.")
        if not isinstance(body, dict) or "data" not in body:
            raise AsanaError("bad_response", "Asana sent an answer this tool could not read.")
        next_page = body.get("next_page") or {}
        return body["data"], (next_page.get("offset") if isinstance(next_page, dict) else None)

    # ---- the reads this tool offers --------------------------------------

    def me(self):
        data, _ = self._get("/users/me", {"opt_fields": "name,email,workspaces.name"})
        return data

    def workspace_projects(self, workspace_gid, archived=False, limit=50, offset=None):
        return self._get(
            "/workspaces/%s/projects" % check_gid(workspace_gid, "workspace id"),
            {
                "archived": "true" if archived else "false",
                "limit": _limit(limit),
                "offset": offset,
                "opt_fields": "name,archived,due_on,owner.name,permalink_url",
            },
        )

    def project(self, project_gid):
        data, _ = self._get(
            "/projects/%s" % check_gid(project_gid, "project id"),
            {
                "opt_fields": "name,archived,notes,due_on,start_on,owner.name,"
                              "permalink_url,workspace.gid,workspace.name"
            },
        )
        return data

    def project_sections(self, project_gid):
        data, _ = self._get(
            "/projects/%s/sections" % check_gid(project_gid, "project id"),
            {"limit": 100, "opt_fields": "name"},
        )
        return data

    def project_tasks(self, project_gid, include_completed=False, limit=50, offset=None):
        return self._get(
            "/projects/%s/tasks" % check_gid(project_gid, "project id"),
            {
                "completed_since": None if include_completed else "now",
                "limit": _limit(limit),
                "offset": offset,
                "opt_fields": "name,completed,due_on,assignee.name,"
                              "memberships.section.name,permalink_url",
            },
        )

    def my_tasks(self, workspace_gid, include_completed=False, limit=50, offset=None):
        return self._get(
            "/tasks",
            {
                "assignee": "me",
                "workspace": check_gid(workspace_gid, "workspace id"),
                "completed_since": None if include_completed else "now",
                "limit": _limit(limit),
                "offset": offset,
                "opt_fields": "name,completed,due_on,projects.name,permalink_url",
            },
        )

    def task(self, task_gid):
        data, _ = self._get(
            "/tasks/%s" % check_gid(task_gid, "task id"),
            {
                "opt_fields": "name,notes,completed,completed_at,due_on,due_at,start_on,"
                              "assignee.name,projects.name,memberships.section.name,"
                              "parent.name,tags.name,num_subtasks,permalink_url,"
                              "workspace.gid,created_at,modified_at,"
                              "custom_fields.name,custom_fields.display_value"
            },
        )
        return data

    def task_subtasks(self, task_gid):
        data, _ = self._get(
            "/tasks/%s/subtasks" % check_gid(task_gid, "task id"),
            {"limit": 100, "opt_fields": "name,completed,due_on,assignee.name"},
        )
        return data

    def task_stories(self, task_gid, limit=100):
        data, _ = self._get(
            "/tasks/%s/stories" % check_gid(task_gid, "task id"),
            {
                "limit": _limit(limit),
                "opt_fields": "resource_subtype,text,created_at,created_by.name",
            },
        )
        return data

    def search_tasks(self, workspace_gid, text, include_completed=False, limit=25):
        data, _ = self._get(
            "/workspaces/%s/tasks/search" % check_gid(workspace_gid, "workspace id"),
            {
                "text": text,
                "completed": None if include_completed else "false",
                "limit": _limit(limit),
                "opt_fields": "name,completed,due_on,assignee.name,projects.name,permalink_url",
            },
        )
        return data


def _limit(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 50
    return max(1, min(100, number))


def _read_quietly(err):
    try:
        return err.read(64 * 1024)
    except Exception:
        return b""


def _asana_message(raw):
    """The first error message in Asana's error body, shortened. Never the request."""
    try:
        body = json.loads(raw.decode("utf-8"))
        message = body["errors"][0]["message"]
        return str(message)[:300]
    except Exception:
        return ""


def _retry_after(headers):
    try:
        return max(0, int(float(headers.get("Retry-After"))))
    except (TypeError, ValueError, AttributeError):
        return None


def _error_for_status(status, detail, retry_after):
    if status == 401:
        return AsanaError(
            "unauthorized",
            "Asana refused the stored token. It may have been removed in Asana.",
            status,
        )
    if status == 402:
        return AsanaError(
            "payment_required",
            "Asana offers this only on a paid plan.",
            status,
        )
    if status in (403, 404):
        return AsanaError(
            "not_found",
            "Asana has no such item, or this account cannot see it.",
            status,
        )
    if status == 429:
        wait = " Try again in %d seconds." % retry_after if retry_after else " Try again shortly."
        return AsanaError("rate_limited", "Asana asked this tool to slow down." + wait,
                          status, retry_after)
    if 300 <= status < 400:
        return AsanaError(
            "unexpected_redirect",
            "Asana tried to send this request somewhere else. It was not followed.",
            status,
        )
    if status >= 500:
        return AsanaError("asana_unavailable", "Asana is having trouble right now.", status)
    message = "Asana did not accept the request."
    if detail:
        message += " Asana said: " + detail
    return AsanaError("bad_request", message, status)
