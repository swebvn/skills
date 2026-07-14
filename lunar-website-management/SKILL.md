---
name: lunar-website-management
description: Manage Lucommerce/Lunar tenant storefronts through the internal API. Use when an agent needs to inspect or update products, product reviews, product combinations, search logs, site settings, locales, or redirect-domain configuration on a Lunar storefront using GET/POST HTTP APIs instead of editing code or using the admin UI.
---

# Lunar Website Management

## Overview

Use this skill to operate a Lucommerce tenant storefront through its internal API. Prefer these APIs for automation tasks that manage website content or settings without logging into Lunar Admin.

## Operating Rules

- Use the tenant storefront domain as the base URL, not the central hub domain.
- Prefix every endpoint with `/api/internal`.
- Use only `GET` and `POST`; this API intentionally avoids `PATCH`, `PUT`, and `DELETE`.
- Require the caller to provide the target store domain for each task and the calling system to provide the internal API token at runtime.
- Authenticate production calls with `Authorization: Bearer <token>` unless the caller runs from an allowed IP.
- Never hardcode, invent, log, or commit an internal API token in this skill or generated artifacts.
- Treat product delete as unavailable. The controller exists in code, but the route is intentionally disabled.
- Do not call central `/api/hub/*` routes unless the task is explicitly hub/tenant-administration work.
- After mutating products, reviews, settings, locales, or redirects, expect page/cache invalidation to happen server-side.

## Required Inputs

External systems and agents using this skill must supply:

- Store domain or URL: the target storefront domain for the current task, for example `store.example.com` or `https://store.example.com`.
- `LUCOMMERCE_INTERNAL_API_TOKEN`: the secret token accepted by that tenant's Lucommerce internal API.

Also accept legacy alias `INTERNAL_API_TOKEN` for the token.

## Credential Resolution

Resolve credentials in this order:

1. Resolve the store URL from the current task. If the caller gives `store.example.com`, normalize it to `https://store.example.com` unless the caller specifies another scheme.
2. Read environment variables:
   - `LUCOMMERCE_INTERNAL_API_TOKEN`, falling back to `INTERNAL_API_TOKEN`
3. Read the calling platform's secret manager or HTTP credential store if it exposes secrets to the agent.
4. If the store domain or token is still missing, ask the caller for the missing value before making API calls.

Operators should set the token in the system that runs the agent, not in this skill. Examples:

```bash
export LUCOMMERCE_INTERNAL_API_TOKEN="secret-token"
```

For hosted agents, CI, no-code tools, or workflow engines, store the token as a secret named `LUCOMMERCE_INTERNAL_API_TOKEN` and configure HTTP requests to send it as a bearer token.

## References

Read [references/internal-api.md](references/internal-api.md) when forming requests, payloads, or response expectations.

Read [references/workflows.md](references/workflows.md) for common product and website-management workflows.

## Quick Start

For a store at `https://store.example.com`:

```bash
STORE_URL="https://store.example.com"
curl -H "Authorization: Bearer $LUCOMMERCE_INTERNAL_API_TOKEN" \
  "$STORE_URL/api/internal/products?status=published"
```

Create or update products with `POST`:

```bash
STORE_URL="https://store.example.com"
curl -X POST "$STORE_URL/api/internal/products/create" \
  -H "Authorization: Bearer $LUCOMMERCE_INTERNAL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Galaxy Phone Case","status":"draft","price":24.9,"sku":"CASE-001","combination_id":32}'
```

## Validation

When working in the repository, verify route availability with:

```bash
php artisan route:list --path=api/internal
```

For code changes to this API package, run:

```bash
php artisan test tests/Feature/InternalApis/ProductManagementApiTest.php
php artisan test
```
