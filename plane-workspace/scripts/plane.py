#!/usr/bin/env python3
"""Small, dependency-free CLI for a self-hosted Plane workspace."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://plane.tdagroup.co"
DEFAULT_WORKSPACE = "dev"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ISSUE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*-\d+$")
PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3, "none": 4, "": 4}


class PlaneError(RuntimeError):
    pass


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def entity_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw = value.get("id")
        return str(raw) if raw else None
    return None


def entity_ids(value: Any) -> list[str]:
    return [item_id for item in as_list(value) if (item_id := entity_id(item))]


def entity_name(value: Any) -> str | None:
    if isinstance(value, dict):
        for field in ("name", "display_name", "email", "slug"):
            if value.get(field):
                return str(value[field])
    return None


def plain_to_html(value: str) -> str:
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", value.strip()):
        paragraphs.append(f"<p>{html.escape(paragraph).replace(chr(10), '<br>')}</p>")
    return "".join(paragraphs)


class PlaneClient:
    def __init__(self, base_url: str, workspace: str, api_key: str, dry_run: bool = False):
        base = base_url.rstrip("/")
        workspace_suffix = f"/{workspace}"
        if base.endswith(workspace_suffix):
            base = base[: -len(workspace_suffix)]
        self.api_root = base if base.endswith("/api/v1") else f"{base}/api/v1"
        self.workspace = workspace
        self.api_key = api_key
        self.dry_run = dry_run

    def request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        method = method.upper()
        query = {key: value for key, value in (params or {}).items() if value is not None}
        url = f"{self.api_root}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"

        if self.dry_run and method in WRITE_METHODS:
            return {"dry_run": True, "method": method, "url": url, "body": data}

        body = json.dumps(data).encode() if data is not None else None
        headers = {
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
            "X-API-Key": self.api_key,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urlopen(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
                    raw = response.read()
                    if not raw:
                        return {"ok": True, "status": response.status}
                    return json.loads(raw.decode())
            except HTTPError as error:
                response_body = error.read().decode(errors="replace")
                if error.code in {429, 502, 503, 504} and attempt < 3:
                    time.sleep(2**attempt)
                    last_error = error
                    continue
                try:
                    detail = json.loads(response_body)
                except json.JSONDecodeError:
                    detail = response_body[:1000]
                raise PlaneError(f"Plane API {error.code} for {method} {url}: {detail}") from None
            except URLError as error:
                last_error = error
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
        raise PlaneError(f"Plane API request failed: {last_error}")

    def list_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query = dict(params or {})
        seen_cursors: set[str] = set()
        while True:
            payload = self.request("GET", path, params=query)
            if isinstance(payload, list):
                return payload
            if not isinstance(payload, dict):
                raise PlaneError(f"Unexpected list response for {path}: {type(payload).__name__}")
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise PlaneError(f"Unexpected results response for {path}")
            items.extend(item for item in results if isinstance(item, dict))
            cursor = payload.get("next_cursor")
            if not cursor or cursor in seen_cursors or payload.get("next_page_results") is False:
                break
            seen_cursors.add(str(cursor))
            query["cursor"] = cursor
        return items

    def workspace_path(self, suffix: str = "") -> str:
        return f"workspaces/{self.workspace}/{suffix.lstrip('/')}"

    def project_path(self, project_id: str, suffix: str = "") -> str:
        return self.workspace_path(f"projects/{project_id}/{suffix.lstrip('/')}")

    def projects(self) -> list[dict[str, Any]]:
        return self.list_all(self.workspace_path("projects/"))

    def resolve_project(self, reference: str) -> dict[str, Any]:
        return resolve_one(self.projects(), reference, ("id", "identifier", "name"), "project")

    def project_members(self, project_id: str) -> list[dict[str, Any]]:
        return self.list_all(self.project_path(project_id, "project-members/"))

    def resolve_member(self, project_id: str, reference: str) -> dict[str, Any]:
        members = self.project_members(project_id)
        if reference.casefold() == "me":
            current = self.request("GET", "users/me/")
            return resolve_one(members, str(current["id"]), ("id",), "project member")
        return resolve_one(
            members,
            reference,
            ("id", "email", "display_name", "first_name", "last_name"),
            "project member",
        )

    def collection(self, project_id: str, resource: str) -> list[dict[str, Any]]:
        return self.list_all(self.project_path(project_id, f"{resource}/"))

    def resolve_collection(
        self, project_id: str, resource: str, reference: str, label: str
    ) -> dict[str, Any]:
        return resolve_one(
            self.collection(project_id, resource), reference, ("id", "name", "slug"), label
        )

    def resolve_state(self, project_id: str, reference: str) -> dict[str, Any]:
        states = self.collection(project_id, "states")
        group_matches = [state for state in states if str(state.get("group", "")).casefold() == reference.casefold()]
        if group_matches:
            return sorted(
                group_matches,
                key=lambda state: (not bool(state.get("default")), state.get("sequence", 999999)),
            )[0]
        return resolve_one(states, reference, ("id", "name", "slug"), "state")

    def get_issue(self, reference: str, project_reference: str | None = None) -> dict[str, Any]:
        if ISSUE_KEY.match(reference):
            payload = self.request("GET", self.workspace_path(f"work-items/{reference.upper()}/"))
        else:
            if not project_reference:
                raise PlaneError("A UUID work-item reference requires --project")
            project = self.resolve_project(project_reference)
            payload = self.request("GET", self.project_path(str(project["id"]), f"work-items/{reference}/"))
        if not isinstance(payload, dict):
            raise PlaneError("Unexpected work-item response")
        return payload


def resolve_one(
    items: Iterable[dict[str, Any]], reference: str, fields: tuple[str, ...], kind: str
) -> dict[str, Any]:
    choices = list(items)
    needle = reference.casefold()
    exact = [
        item
        for item in choices
        if any(str(item.get(field, "")).casefold() == needle for field in fields)
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise PlaneError(f"Ambiguous {kind} reference: {reference}")
    partial = [
        item
        for item in choices
        if any(needle in str(item.get(field, "")).casefold() for field in fields)
    ]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        names = [str(item.get("name") or item.get("display_name") or item.get("email") or item.get("id")) for item in partial]
        raise PlaneError(f"Ambiguous {kind} reference {reference!r}: {', '.join(names)}")
    raise PlaneError(f"Unknown {kind}: {reference}")


def issue_project_id(issue: dict[str, Any]) -> str:
    project_id = entity_id(issue.get("project")) or issue.get("project_id")
    if not project_id:
        raise PlaneError("Work item does not contain a project ID")
    return str(project_id)


def summarize_issue(issue: dict[str, Any], project: dict[str, Any] | None = None) -> dict[str, Any]:
    identifier = project.get("identifier") if project else None
    sequence = issue.get("sequence_id")
    key = f"{identifier}-{sequence}" if identifier and sequence is not None else None
    return {
        "key": key,
        "id": issue.get("id"),
        "title": issue.get("name"),
        "priority": issue.get("priority"),
        "state": entity_name(issue.get("state")) or issue.get("state"),
        "state_group": issue.get("state", {}).get("group") if isinstance(issue.get("state"), dict) else None,
        "assignees": [entity_name(value) or entity_id(value) for value in as_list(issue.get("assignees"))],
        "labels": [entity_name(value) or entity_id(value) for value in as_list(issue.get("labels"))],
        "target_date": issue.get("target_date"),
        "parent": entity_id(issue.get("parent")),
    }


def project_for_issue(client: PlaneClient, issue: dict[str, Any]) -> dict[str, Any]:
    return client.resolve_project(issue_project_id(issue))


def resolve_many(
    values: list[str] | None, resolver: Any
) -> list[str] | None:
    if values is None:
        return None
    return [str(resolver(value)["id"]) for value in values]


def mutate_ids(
    current: Any,
    replace: list[str] | None,
    additions: list[str],
    removals: list[str],
    resolver: Any,
    clear: bool,
) -> list[str] | None:
    if replace is None and not additions and not removals and not clear:
        return None
    ids = [] if clear else (resolve_many(replace, resolver) if replace is not None else entity_ids(current))
    assert ids is not None
    for value in additions:
        item_id = str(resolver(value)["id"])
        if item_id not in ids:
            ids.append(item_id)
    remove_ids = {str(resolver(value)["id"]) for value in removals}
    return [item_id for item_id in ids if item_id not in remove_ids]


def add_issue_association(
    client: PlaneClient,
    project_id: str,
    issue_id: str,
    resource: str,
    reference: str,
) -> Any:
    singular = "cycle" if resource == "cycles" else "module"
    item = client.resolve_collection(project_id, resource, reference, singular)
    suffix = "cycle-issues" if resource == "cycles" else "module-issues"
    return client.request(
        "POST",
        client.project_path(project_id, f"{resource}/{item['id']}/{suffix}/"),
        data={"issues": [issue_id]},
    )


def build_comment(summary: str, tests: str | None, commit: str | None, pr: str | None) -> str:
    parts = [summary]
    if tests:
        parts.append(f"Tests: {tests}")
    if commit:
        parts.append(f"Commit: {commit}")
    if pr:
        parts.append(f"PR: {pr}")
    return "\n\n".join(parts)


def add_comment(client: PlaneClient, issue: dict[str, Any], body: str, body_is_html: bool = False) -> Any:
    project_id = issue_project_id(issue)
    return client.request(
        "POST",
        client.project_path(project_id, f"work-items/{issue['id']}/comments/"),
        data={"comment_html": body if body_is_html else plain_to_html(body)},
    )


def command_issues_list(client: PlaneClient, args: argparse.Namespace) -> Any:
    projects = [client.resolve_project(args.project)] if args.project else client.projects()
    output = []
    for project in projects:
        issues = client.list_all(
            client.project_path(str(project["id"]), "work-items/"),
            {"expand": "state,assignees,labels"},
        )
        for issue in issues:
            summary = summarize_issue(issue, project)
            if args.state and str(summary.get("state", "")).casefold() != args.state.casefold() and str(summary.get("state_group", "")).casefold() != args.state.casefold():
                continue
            if args.priority and str(summary.get("priority", "")).casefold() != args.priority.casefold():
                continue
            if args.unassigned and summary["assignees"]:
                continue
            if args.label and args.label.casefold() not in {str(label).casefold() for label in summary["labels"]}:
                continue
            output.append(issue if args.full else summary)
            if args.limit and len(output) >= args.limit:
                return output
    return output


def command_issues_next(client: PlaneClient, args: argparse.Namespace) -> Any:
    project = client.resolve_project(args.project)
    issues = client.list_all(
        client.project_path(str(project["id"]), "work-items/"),
        {"expand": "state,assignees,labels"},
    )
    groups = {group.casefold() for group in (args.state_group or ["backlog", "unstarted"])}
    candidates = []
    for issue in issues:
        summary = summarize_issue(issue, project)
        if str(summary.get("state_group", "")).casefold() not in groups:
            continue
        if not args.include_assigned and summary["assignees"]:
            continue
        if args.label and args.label.casefold() not in {str(label).casefold() for label in summary["labels"]}:
            continue
        candidates.append(summary)
    candidates.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(str(item.get("priority") or "").casefold(), 5),
            item.get("target_date") or "9999-12-31",
            int(str(item.get("key") or "-999999").rsplit("-", 1)[-1]),
        )
    )
    return candidates[: args.limit]


def command_issues_create(client: PlaneClient, args: argparse.Namespace) -> Any:
    project = client.resolve_project(args.project)
    project_id = str(project["id"])
    payload: dict[str, Any] = {"name": args.title}
    if args.description is not None:
        payload["description_html"] = plain_to_html(args.description)
    if args.description_html is not None:
        payload["description_html"] = args.description_html
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.state is not None:
        payload["state"] = str(client.resolve_state(project_id, args.state)["id"])
    if args.assignee:
        payload["assignees"] = resolve_many(args.assignee, lambda value: client.resolve_member(project_id, value))
    if args.label:
        payload["labels"] = resolve_many(args.label, lambda value: client.resolve_collection(project_id, "labels", value, "label"))
    if args.parent:
        parent = client.get_issue(args.parent, args.project)
        if issue_project_id(parent) != project_id:
            raise PlaneError("Parent work item must belong to the same project")
        payload["parent"] = parent["id"]
    if args.start_date:
        payload["start_date"] = args.start_date
    if args.target_date:
        payload["target_date"] = args.target_date

    created = client.request("POST", client.project_path(project_id, "work-items/"), data=payload)
    if client.dry_run:
        return {"create": created, "cycle": args.cycle, "module": args.module, "comment": args.comment}
    issue_id = str(created["id"])
    followups: dict[str, Any] = {}
    if args.cycle:
        followups["cycle"] = add_issue_association(client, project_id, issue_id, "cycles", args.cycle)
    if args.module:
        followups["module"] = add_issue_association(client, project_id, issue_id, "modules", args.module)
    if args.comment:
        followups["comment"] = add_comment(client, created, args.comment)
    return {"issue": created, "followups": followups}


def command_issues_update(client: PlaneClient, args: argparse.Namespace) -> Any:
    issue = client.get_issue(args.issue, args.project)
    project_id = issue_project_id(issue)
    payload: dict[str, Any] = {}
    if args.title is not None:
        payload["name"] = args.title
    if args.description is not None:
        payload["description_html"] = plain_to_html(args.description)
    if args.description_html is not None:
        payload["description_html"] = args.description_html
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.state is not None:
        payload["state"] = str(client.resolve_state(project_id, args.state)["id"])
    if args.start_date is not None:
        payload["start_date"] = args.start_date
    if args.target_date is not None:
        payload["target_date"] = args.target_date

    assignees = mutate_ids(
        issue.get("assignees"), args.assignee, args.add_assignee, args.remove_assignee,
        lambda value: client.resolve_member(project_id, value), args.clear_assignees,
    )
    if assignees is not None:
        payload["assignees"] = assignees
    labels = mutate_ids(
        issue.get("labels"), args.label, args.add_label, args.remove_label,
        lambda value: client.resolve_collection(project_id, "labels", value, "label"), args.clear_labels,
    )
    if labels is not None:
        payload["labels"] = labels

    result: dict[str, Any] = {}
    if payload:
        result["update"] = client.request(
            "PATCH", client.project_path(project_id, f"work-items/{issue['id']}/"), data=payload
        )
    if args.cycle:
        result["cycle"] = add_issue_association(client, project_id, str(issue["id"]), "cycles", args.cycle)
    if args.module:
        result["module"] = add_issue_association(client, project_id, str(issue["id"]), "modules", args.module)
    if args.comment:
        result["comment"] = add_comment(client, issue, args.comment)
    if not result:
        raise PlaneError("No update fields were provided")
    return result


def command_issues_claim(client: PlaneClient, args: argparse.Namespace) -> Any:
    initial = client.get_issue(args.issue, args.project)
    project_id = issue_project_id(initial)
    assignee_ref = args.assignee or os.environ.get("PLANE_AGENT_MEMBER") or "me"
    member = client.resolve_member(project_id, assignee_ref)
    started_state = client.resolve_state(project_id, args.state or "started")

    current = client.get_issue(args.issue, args.project)
    states = {str(state["id"]): state for state in client.collection(project_id, "states")}
    current_state_id = entity_id(current.get("state"))
    current_group = states.get(str(current_state_id), {}).get("group")
    if current_group in {"completed", "cancelled"} and not args.force:
        raise PlaneError(f"Cannot claim an issue in the {current_group} state group without --force")
    existing = entity_ids(current.get("assignees"))
    member_id = str(member["id"])
    if existing and member_id not in existing and not args.force:
        raise PlaneError("Issue is already assigned to another member; re-run with --force only if authorized")
    if member_id not in existing:
        existing.append(member_id)

    update = client.request(
        "PATCH",
        client.project_path(project_id, f"work-items/{current['id']}/"),
        data={"assignees": existing, "state": str(started_state["id"])},
    )
    identity = args.agent or os.environ.get("CODEX_AGENT_NAME") or member.get("display_name") or member.get("email")
    comment_body = args.comment or f"Claimed by {identity} via Codex. Work has started."
    comment = add_comment(client, current, comment_body)
    return {"update": update, "comment": comment}


def command_issues_complete(client: PlaneClient, args: argparse.Namespace) -> Any:
    issue = client.get_issue(args.issue, args.project)
    project_id = issue_project_id(issue)
    state = client.resolve_state(project_id, args.state or "completed")
    update = client.request(
        "PATCH",
        client.project_path(project_id, f"work-items/{issue['id']}/"),
        data={"state": str(state["id"])},
    )
    comment = add_comment(client, issue, build_comment(args.summary, args.tests, args.commit, args.pr))
    return {"update": update, "comment": comment}


def command_issues_block(client: PlaneClient, args: argparse.Namespace) -> Any:
    issue = client.get_issue(args.issue, args.project)
    project_id = issue_project_id(issue)
    result: dict[str, Any] = {}
    payload: dict[str, Any] = {}
    if args.state:
        payload["state"] = str(client.resolve_state(project_id, args.state)["id"])
    if args.label:
        label = client.resolve_collection(project_id, "labels", args.label, "label")
        labels = entity_ids(issue.get("labels"))
        if str(label["id"]) not in labels:
            labels.append(str(label["id"]))
        payload["labels"] = labels
    if payload:
        result["update"] = client.request(
            "PATCH", client.project_path(project_id, f"work-items/{issue['id']}/"), data=payload
        )
    result["comment"] = add_comment(client, issue, f"Blocked: {args.reason}")
    return result


def add_project_argument(parser: argparse.ArgumentParser, required: bool = True) -> None:
    parser.add_argument("--project", required=required, help="Project UUID, identifier, or name")


def add_issue_mutation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--description-html")
    parser.add_argument("--priority")
    parser.add_argument("--state", help="State UUID/name/slug or semantic group")
    parser.add_argument("--assignee", action="append", help="Replace assignees; repeatable")
    parser.add_argument("--add-assignee", action="append", default=[])
    parser.add_argument("--remove-assignee", action="append", default=[])
    parser.add_argument("--clear-assignees", action="store_true")
    parser.add_argument("--label", action="append", help="Replace labels; repeatable")
    parser.add_argument("--add-label", action="append", default=[])
    parser.add_argument("--remove-label", action="append", default=[])
    parser.add_argument("--clear-labels", action="store_true")
    parser.add_argument("--start-date")
    parser.add_argument("--target-date")
    parser.add_argument("--cycle")
    parser.add_argument("--module")
    parser.add_argument("--comment")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("PLANE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--workspace", default=os.environ.get("PLANE_WORKSPACE_SLUG", DEFAULT_WORKSPACE))
    parser.add_argument("--api-key-env", default="PLANE_API_KEY")
    parser.add_argument("--dry-run", action="store_true", help="Preview writes while still allowing reads")
    parser.add_argument("--compact", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("me")

    projects = sub.add_parser("projects")
    projects_sub = projects.add_subparsers(dest="action", required=True)
    projects_sub.add_parser("list")
    project_get = projects_sub.add_parser("get")
    project_get.add_argument("project")

    members = sub.add_parser("members")
    members_sub = members.add_subparsers(dest="action", required=True)
    member_list = members_sub.add_parser("list")
    add_project_argument(member_list, required=False)

    for resource in ("states", "cycles", "modules"):
        resource_parser = sub.add_parser(resource)
        resource_sub = resource_parser.add_subparsers(dest="action", required=True)
        resource_list = resource_sub.add_parser("list")
        add_project_argument(resource_list)

    labels = sub.add_parser("labels")
    labels_sub = labels.add_subparsers(dest="action", required=True)
    labels_list = labels_sub.add_parser("list")
    add_project_argument(labels_list)
    labels_create = labels_sub.add_parser("create")
    add_project_argument(labels_create)
    labels_create.add_argument("--name", required=True)
    labels_create.add_argument("--color", default="#5E6AD2")
    labels_create.add_argument("--description")

    issues = sub.add_parser("issues")
    issues_sub = issues.add_subparsers(dest="action", required=True)

    issue_list = issues_sub.add_parser("list")
    add_project_argument(issue_list, required=False)
    issue_list.add_argument("--state")
    issue_list.add_argument("--priority")
    issue_list.add_argument("--label")
    issue_list.add_argument("--unassigned", action="store_true")
    issue_list.add_argument("--limit", type=int)
    issue_list.add_argument("--full", action="store_true")

    issue_next = issues_sub.add_parser("next")
    add_project_argument(issue_next)
    issue_next.add_argument("--label")
    issue_next.add_argument("--state-group", action="append")
    issue_next.add_argument("--include-assigned", action="store_true")
    issue_next.add_argument("--limit", type=int, default=10)

    issue_get = issues_sub.add_parser("get")
    issue_get.add_argument("issue")
    add_project_argument(issue_get, required=False)
    issue_get.add_argument("--comments", action="store_true")

    issue_create = issues_sub.add_parser("create")
    add_project_argument(issue_create)
    issue_create.add_argument("--title", required=True)
    issue_create.add_argument("--description")
    issue_create.add_argument("--description-html")
    issue_create.add_argument("--priority")
    issue_create.add_argument("--state")
    issue_create.add_argument("--assignee", action="append")
    issue_create.add_argument("--label", action="append")
    issue_create.add_argument("--parent")
    issue_create.add_argument("--start-date")
    issue_create.add_argument("--target-date")
    issue_create.add_argument("--cycle")
    issue_create.add_argument("--module")
    issue_create.add_argument("--comment")

    issue_update = issues_sub.add_parser("update")
    issue_update.add_argument("issue")
    add_project_argument(issue_update, required=False)
    add_issue_mutation_arguments(issue_update)

    issue_comment = issues_sub.add_parser("comment")
    issue_comment.add_argument("issue")
    add_project_argument(issue_comment, required=False)
    issue_comment.add_argument("--body", required=True)
    issue_comment.add_argument("--html", action="store_true")

    issue_claim = issues_sub.add_parser("claim")
    issue_claim.add_argument("issue")
    add_project_argument(issue_claim, required=False)
    issue_claim.add_argument("--assignee")
    issue_claim.add_argument("--state")
    issue_claim.add_argument("--agent")
    issue_claim.add_argument("--comment")
    issue_claim.add_argument("--force", action="store_true")

    issue_complete = issues_sub.add_parser("complete")
    issue_complete.add_argument("issue")
    add_project_argument(issue_complete, required=False)
    issue_complete.add_argument("--state")
    issue_complete.add_argument("--summary", required=True)
    issue_complete.add_argument("--tests")
    issue_complete.add_argument("--commit")
    issue_complete.add_argument("--pr")

    issue_block = issues_sub.add_parser("block")
    issue_block.add_argument("issue")
    add_project_argument(issue_block, required=False)
    issue_block.add_argument("--reason", required=True)
    issue_block.add_argument("--label")
    issue_block.add_argument("--state")

    raw = sub.add_parser("raw")
    raw.add_argument("method", choices=["GET", "POST", "PATCH", "PUT", "DELETE"])
    raw.add_argument("path")
    raw.add_argument("--data", help="JSON request body")
    return parser


def dispatch(client: PlaneClient, args: argparse.Namespace) -> Any:
    if args.command == "me":
        return client.request("GET", "users/me/")
    if args.command == "projects":
        return client.projects() if args.action == "list" else client.resolve_project(args.project)
    if args.command == "members":
        if args.project:
            project = client.resolve_project(args.project)
            return client.project_members(str(project["id"]))
        return client.list_all(client.workspace_path("members/"))
    if args.command in {"states", "cycles", "modules"}:
        project = client.resolve_project(args.project)
        return client.collection(str(project["id"]), args.command)
    if args.command == "labels":
        project = client.resolve_project(args.project)
        project_id = str(project["id"])
        if args.action == "list":
            return client.collection(project_id, "labels")
        data = {"name": args.name, "color": args.color}
        if args.description:
            data["description"] = args.description
        return client.request("POST", client.project_path(project_id, "labels/"), data=data)
    if args.command == "issues":
        if args.action == "list":
            return command_issues_list(client, args)
        if args.action == "next":
            return command_issues_next(client, args)
        if args.action == "get":
            issue = client.get_issue(args.issue, args.project)
            if not args.comments:
                return issue
            comments = client.list_all(
                client.project_path(issue_project_id(issue), f"work-items/{issue['id']}/comments/")
            )
            return {"issue": issue, "comments": comments}
        if args.action == "create":
            return command_issues_create(client, args)
        if args.action == "update":
            return command_issues_update(client, args)
        if args.action == "comment":
            issue = client.get_issue(args.issue, args.project)
            return add_comment(client, issue, args.body, args.html)
        if args.action == "claim":
            return command_issues_claim(client, args)
        if args.action == "complete":
            return command_issues_complete(client, args)
        if args.action == "block":
            return command_issues_block(client, args)
    if args.command == "raw":
        data = json.loads(args.data) if args.data else None
        return client.request(args.method, args.path, data=data)
    raise PlaneError("Unsupported command")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        parser.error(f"Set the API key in the {args.api_key_env} environment variable")
    client = PlaneClient(args.base_url, args.workspace, api_key, args.dry_run)
    try:
        result = dispatch(client, args)
        print(json.dumps(result, indent=None if args.compact else 2, ensure_ascii=False, sort_keys=True))
        return 0
    except (PlaneError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
