"""Asana client: the reads, and the changes, that own-asana offers.

What this file guarantees, in one place:

- It only ever talks to https://app.asana.com/api/1.0 (or, for the tests,
  a loopback address). Any other address is refused when the client is built.
- It never follows a redirect, so the token cannot be carried to another host.
- One function sends every request. It sends GET to look, and POST, PUT or
  DELETE to change. Any other method is refused there.
- Every object id that goes into a path is checked to be digits only.
- A change is never sent twice by this file, except once more when Asana
  answered "slow down" (429), which means the first try was not carried out.
- The token is asked for at call time and is never logged, returned or put
  into an error message.

What it does NOT decide: which items may be changed. The server (server.py)
looks every item up first and refuses anything outside the one workspace
chosen in Set up. This file only carries out a change it is handed.

Standard library only. Python 3.8 or later.
"""

import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://app.asana.com/api/1.0"
USER_AGENT = "own-asana/1.3"
GID_RE = re.compile(r"^[0-9]{1,31}$")
LOOPBACK_RE = re.compile(r"^http://127\.0\.0\.1:[0-9]{1,5}$")
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_RETRY_AFTER_SECONDS = 5
METHODS = ("GET", "POST", "PUT", "DELETE")

TASK_SUMMARY = ("name,completed,due_on,due_at,start_on,assignee.name,parent.name,"
                "projects.name,permalink_url")
PROJECT_SUMMARY = "name,archived,notes,due_on,start_on,owner.name,permalink_url"


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
    text = value.strip() if isinstance(value, str) else ""
    if isinstance(value, int) and not isinstance(value, bool):
        text = str(value)
    if not GID_RE.match(text):
        raise AsanaError("bad_argument", "The %s must be one number from Asana (digits only)." % what)
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

    def _request(self, method, path, params=None, data=None, _retried=False):
        if method not in METHODS:
            raise ValueError("own-asana sends GET, POST, PUT and DELETE only")
        changing = method != "GET"
        token = self._token_provider()
        if not token:
            raise AsanaError("no_token", "No Asana token is stored on this computer.")
        query = urllib.parse.urlencode(
            [(k, v) for k, v in sorted((params or {}).items()) if v is not None]
        )
        url = self._base + path + ("?" + query if query else "")
        body = None
        if changing and method != "DELETE":
            body = json.dumps({"data": data or {}}).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", "Bearer " + token)
        request.add_header("Accept", "application/json")
        request.add_header("User-Agent", USER_AGENT)
        if body is not None:
            request.add_header("Content-Type", "application/json")
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
                return self._request(method, path, params, data, _retried=True)
            raise _error_for_status(status, detail, retry_after, changing)
        except urllib.error.URLError as err:
            reason = getattr(err, "reason", None)
            if "CERTIFICATE_VERIFY_FAILED" in str(reason):
                raise AsanaError("tls", "This computer could not check Asana's security "
                                        "certificate. Nothing was sent.")
            raise _no_answer(changing)
        except (OSError, ValueError, http.client.HTTPException):
            # The connection broke, or the answer was cut short or was not HTTP at all.
            raise _no_answer(changing)
        if len(raw) > MAX_BODY_BYTES:
            raise AsanaError("too_large", "Asana's answer was too large. Ask for fewer items.")
        try:
            answer = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _unreadable(changing)
        if not isinstance(answer, dict) or "data" not in answer:
            raise _unreadable(changing)
        next_page = answer.get("next_page") or {}
        return answer["data"], (next_page.get("offset") if isinstance(next_page, dict) else None)

    def _get(self, path, params=None):
        return self._request("GET", path, params)

    def _change(self, method, path, data=None, opt_fields=None):
        answer, _ = self._request(method, path, {"opt_fields": opt_fields}, data)
        return answer

    # ---- looking ---------------------------------------------------------

    def me(self):
        data, _ = self._get("/users/me", {"opt_fields": "name,email,workspaces.name"})
        return data

    def workspace(self, workspace_gid):
        data, _ = self._get("/workspaces/%s" % check_gid(workspace_gid, "workspace id"),
                            {"opt_fields": "name,is_organization"})
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

    def workspace_users(self, workspace_gid, offset=None):
        return self._get("/workspaces/%s/users" % check_gid(workspace_gid, "workspace id"),
                         {"offset": offset, "opt_fields": "name,email"})

    def workspace_teams(self, workspace_gid, limit=50, offset=None):
        return self._get("/workspaces/%s/teams" % check_gid(workspace_gid, "workspace id"),
                         {"limit": _limit(limit), "offset": offset, "opt_fields": "name"})

    def workspace_tags(self, workspace_gid, limit=50, offset=None):
        return self._get("/workspaces/%s/tags" % check_gid(workspace_gid, "workspace id"),
                         {"limit": _limit(limit), "offset": offset, "opt_fields": "name,color"})

    def user(self, user_gid):
        data, _ = self._get("/users/%s" % check_gid(user_gid, "person's id"),
                            {"opt_fields": "name,workspaces"})
        return data

    def team(self, team_gid):
        data, _ = self._get("/teams/%s" % check_gid(team_gid, "team id"),
                            {"opt_fields": "name,organization"})
        return data

    def tag(self, tag_gid):
        data, _ = self._get("/tags/%s" % check_gid(tag_gid, "tag id"),
                            {"opt_fields": "name,workspace"})
        return data

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

    def section(self, section_gid):
        data, _ = self._get("/sections/%s" % check_gid(section_gid, "section id"),
                            {"opt_fields": "name,project.name"})
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
                              "parent.name,tags.name,followers.name,num_subtasks,permalink_url,"
                              "workspace.gid,created_at,modified_at,"
                              "custom_fields.name,custom_fields.display_value"
            },
        )
        return data

    def task_brief(self, task_gid, what="task id"):
        """Just enough to check a task before changing it: its name and its workspace."""
        data, _ = self._get("/tasks/%s" % check_gid(task_gid, what),
                            {"opt_fields": "name,completed,num_subtasks,workspace"})
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

    # ---- changing: tasks ---------------------------------------------------
    # Each of these changes ONE item. The server has already checked that every
    # id handed in here belongs to the chosen workspace.

    def create_task(self, fields):
        return self._change("POST", "/tasks", fields, TASK_SUMMARY)

    def create_subtask(self, parent_gid, fields):
        return self._change("POST", "/tasks/%s/subtasks" % check_gid(parent_gid, "parent task id"),
                            fields, TASK_SUMMARY)

    def update_task(self, task_gid, fields):
        return self._change("PUT", "/tasks/%s" % check_gid(task_gid, "task id"),
                            fields, TASK_SUMMARY)

    def delete_task(self, task_gid):
        return self._change("DELETE", "/tasks/%s" % check_gid(task_gid, "task id"))

    def duplicate_task(self, task_gid, name, include):
        return self._change("POST", "/tasks/%s/duplicate" % check_gid(task_gid, "task id"),
                            {"name": name, "include": ",".join(include)},
                            "status,new_task.name")

    def add_task_to_project(self, task_gid, project_gid, section_gid=None):
        data = {"project": check_gid(project_gid, "project id")}
        if section_gid is not None:
            data["section"] = check_gid(section_gid, "section id")
        return self._change("POST", "/tasks/%s/addProject" % check_gid(task_gid, "task id"), data)

    def remove_task_from_project(self, task_gid, project_gid):
        return self._change("POST", "/tasks/%s/removeProject" % check_gid(task_gid, "task id"),
                            {"project": check_gid(project_gid, "project id")})

    def add_task_to_section(self, section_gid, task_gid):
        return self._change("POST", "/sections/%s/addTask" % check_gid(section_gid, "section id"),
                            {"task": check_gid(task_gid, "task id")})

    def set_task_parent(self, task_gid, parent_gid):
        parent = None if parent_gid is None else check_gid(parent_gid, "parent task id")
        return self._change("POST", "/tasks/%s/setParent" % check_gid(task_gid, "task id"),
                            {"parent": parent}, TASK_SUMMARY)

    def add_comment(self, task_gid, text):
        return self._change("POST", "/tasks/%s/stories" % check_gid(task_gid, "task id"),
                            {"text": text}, "text,created_at,created_by.name")

    def add_followers(self, task_gid, user_ids):
        return self._change("POST", "/tasks/%s/addFollowers" % check_gid(task_gid, "task id"),
                            {"followers": [_user(u) for u in user_ids]}, "name,followers.name")

    def remove_followers(self, task_gid, user_ids):
        return self._change("POST", "/tasks/%s/removeFollowers" % check_gid(task_gid, "task id"),
                            {"followers": [_user(u) for u in user_ids]}, "name,followers.name")

    def add_tag(self, task_gid, tag_gid):
        return self._change("POST", "/tasks/%s/addTag" % check_gid(task_gid, "task id"),
                            {"tag": check_gid(tag_gid, "tag id")})

    def remove_tag(self, task_gid, tag_gid):
        return self._change("POST", "/tasks/%s/removeTag" % check_gid(task_gid, "task id"),
                            {"tag": check_gid(tag_gid, "tag id")})

    def create_tag(self, workspace_gid, name):
        return self._change("POST", "/workspaces/%s/tags" % check_gid(workspace_gid, "workspace id"),
                            {"name": name}, "name")

    # ---- changing: projects and sections -----------------------------------

    def create_project(self, fields):
        return self._change("POST", "/projects", fields, PROJECT_SUMMARY)

    def update_project(self, project_gid, fields):
        return self._change("PUT", "/projects/%s" % check_gid(project_gid, "project id"),
                            fields, PROJECT_SUMMARY)

    def delete_project(self, project_gid):
        return self._change("DELETE", "/projects/%s" % check_gid(project_gid, "project id"))

    def duplicate_project(self, project_gid, name, include):
        return self._change("POST", "/projects/%s/duplicate" % check_gid(project_gid, "project id"),
                            {"name": name, "include": ",".join(include)},
                            "status,new_project.name")

    def add_project_members(self, project_gid, user_ids):
        return self._change("POST", "/projects/%s/addMembers" % check_gid(project_gid, "project id"),
                            {"members": ",".join(_user(u) for u in user_ids)},
                            "name,members.name")

    def remove_project_members(self, project_gid, user_ids):
        return self._change("POST",
                            "/projects/%s/removeMembers" % check_gid(project_gid, "project id"),
                            {"members": ",".join(_user(u) for u in user_ids)},
                            "name,members.name")

    def create_section(self, project_gid, name):
        return self._change("POST", "/projects/%s/sections" % check_gid(project_gid, "project id"),
                            {"name": name}, "name")

    def rename_section(self, section_gid, name):
        return self._change("PUT", "/sections/%s" % check_gid(section_gid, "section id"),
                            {"name": name}, "name")

    def move_section(self, project_gid, section_gid, before_gid=None, after_gid=None):
        data = {"section": check_gid(section_gid, "section id")}
        if before_gid is not None:
            data["before_section"] = check_gid(before_gid, "section id")
        if after_gid is not None:
            data["after_section"] = check_gid(after_gid, "section id")
        return self._change("POST",
                            "/projects/%s/sections/insert" % check_gid(project_gid, "project id"),
                            data)

    def delete_section(self, section_gid):
        return self._change("DELETE", "/sections/%s" % check_gid(section_gid, "section id"))


def _user(value):
    """A person, as Asana takes one here: the word me, or a person's id."""
    return "me" if value == "me" else check_gid(value, "person's id")


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


def _no_answer(changing):
    if changing:
        return AsanaError(
            "no_answer",
            "Asana did not answer, so it is not known whether the change was made. "
            "Read the item again before trying again, so it is not done twice.")
    return AsanaError("network", "Could not reach Asana. Check the internet connection.")


def _unreadable(changing):
    if changing:
        return AsanaError(
            "bad_response",
            "Asana sent an answer this tool could not read, so it is not known whether the "
            "change was made. Read the item again before trying again.")
    return AsanaError("bad_response", "Asana sent an answer this tool could not read.")


def _error_for_status(status, detail, retry_after, changing=False):
    nothing = " Nothing was changed." if changing else ""
    if status == 401:
        return AsanaError(
            "unauthorized",
            "Asana refused the stored token. It may have been removed in Asana." + nothing,
            status,
        )
    if status == 402:
        return AsanaError(
            "payment_required",
            "Asana offers this only on a paid plan." + nothing,
            status,
        )
    if status in (403, 404):
        if changing:
            return AsanaError(
                "not_found",
                "Asana has no such item, or this account is not allowed to change it."
                + nothing, status)
        return AsanaError(
            "not_found",
            "Asana has no such item, or this account cannot see it.",
            status,
        )
    if status == 429:
        wait = " Try again in %d seconds." % retry_after if retry_after else " Try again shortly."
        return AsanaError("rate_limited", "Asana asked this tool to slow down." + nothing + wait,
                          status, retry_after)
    if 300 <= status < 400:
        return AsanaError(
            "unexpected_redirect",
            "Asana tried to send this request somewhere else. It was not followed." + nothing,
            status,
        )
    if status >= 500:
        if changing:
            return AsanaError(
                "asana_unavailable",
                "Asana is having trouble right now, so it is not known whether the change was "
                "made. Read the item again before trying again.", status)
        return AsanaError("asana_unavailable", "Asana is having trouble right now.", status)
    message = "Asana did not accept the request." + nothing
    if detail:
        message += " Asana said: " + detail
    return AsanaError("bad_request", message, status)
