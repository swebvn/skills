# Plane API Reference

## Connection

- API root: `{PLANE_BASE_URL}/api/v1`
- Authentication header: `X-API-Key: $PLANE_API_KEY`
- Workspace slug: `PLANE_WORKSPACE_SLUG`
- The list endpoints on the configured self-hosted instance use cursor pagination and normally return `results` plus `next_cursor`.

The frontend workspace URL `https://plane.tdagroup.co/dev/` maps to base URL `https://plane.tdagroup.co` and workspace slug `dev`.

## Verified endpoints

| Operation | Method and path |
|---|---|
| Current user | `GET /users/me/` |
| Projects | `GET /workspaces/{workspace}/projects/` |
| Workspace members | `GET /workspaces/{workspace}/members/` |
| Project members | `GET /workspaces/{workspace}/projects/{project}/project-members/` |
| Work items | `GET/POST /workspaces/{workspace}/projects/{project}/work-items/` |
| Work item detail | `GET/PATCH /workspaces/{workspace}/projects/{project}/work-items/{id}/` |
| Work item by key | `GET /workspaces/{workspace}/work-items/{PROJECT-123}/` |
| Work item search | `GET /workspaces/{workspace}/work-items/search/` |
| Comments | `GET/POST /workspaces/{workspace}/projects/{project}/work-items/{item}/comments/` |
| States | `GET /workspaces/{workspace}/projects/{project}/states/` |
| Labels | `GET/POST /workspaces/{workspace}/projects/{project}/labels/` |
| Cycles | `GET /workspaces/{workspace}/projects/{project}/cycles/` |
| Add cycle items | `POST /workspaces/{workspace}/projects/{project}/cycles/{cycle}/cycle-issues/` |
| Modules | `GET /workspaces/{workspace}/projects/{project}/modules/` |
| Add module items | `POST /workspaces/{workspace}/projects/{project}/modules/{module}/module-issues/` |

## Common work-item fields

- `name`
- `description_html`
- `priority`
- `state` as a state UUID
- `assignees` as member UUIDs
- `labels` as label UUIDs
- `parent` as a work-item UUID
- `start_date` and `target_date` as `YYYY-MM-DD`
- `estimate_point` or `point`, depending on server configuration

Comments use `comment_html`. Cycle and module membership use a separate request with `{"issues": ["work-item-uuid"]}`.

## State semantics

Resolve workflow intent through the state `group` field:

- `backlog`
- `unstarted`
- `started`
- `completed`
- `cancelled`

Projects may rename individual states. Prefer a default state in the requested group, then the lowest sequence value.

## Troubleshooting

- `401` or `403`: verify the token, permissions, and `X-API-Key` header.
- `404` at `/api/v1/`: expected on some Plane versions; test a concrete endpoint such as `/api/v1/users/me/`.
- Empty project members: the assignee may be a workspace member but not a project member.
- Ambiguous names: use a project identifier, email address, issue key, or UUID.
- Schema drift: run a read request with `raw` and update the CLI only after inspecting the live JSON.
