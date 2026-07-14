# Workflows

## Contents

- [Choose The Right Domain](#choose-the-right-domain)
- [Product Creation Workflow](#product-creation-workflow)
- [Product Update Workflow](#product-update-workflow)
- [Product Review Workflow](#product-review-workflow)
- [Combination Workflow](#combination-workflow)
- [Search Logs Workflow](#search-logs-workflow)
- [Website Settings Workflow](#website-settings-workflow)
- [Locale Workflow](#locale-workflow)
- [Redirect Domain Workflow](#redirect-domain-workflow)
- [Cache Clear Workflow](#cache-clear-workflow)
- [Safety Checklist](#safety-checklist)

## Choose The Right Domain

Use the tenant storefront domain for tenant website operations:

```text
https://tenant-domain.com/api/internal/...
```

Use central `/api/hub/*` only for tenant provisioning, renaming, restore, stats, or hub-level administration.

Before making calls, obtain the store domain from the current task and `LUCOMMERCE_INTERNAL_API_TOKEN` from the caller's runtime. Accept `INTERNAL_API_TOKEN` as a token alias. Do not assume repo-local `.env` access and do not embed the token in prompts, logs, code, docs, or commits.

## Product Creation Workflow

1. Fetch combinations if the product needs configurable buying options:

   ```text
   GET /api/internal/combinations
   ```

2. Create the product as `draft` unless the user explicitly asks to publish:

   ```text
   POST /api/internal/products/create
   ```

3. Include `collection_ids` to place the product in storefront navigation/catalog pages.

4. Include `source` and `id_source` when syncing from another system so later updates can find the same product. These fields are create-only and cannot be changed by the update endpoint.

5. Fetch the product after creation to confirm slug, price, combination state, and media URLs:

   ```text
   GET /api/internal/products/{id}
   ```

## Product Update Workflow

1. Locate the product by ID, slug, or source metadata:

   ```text
   GET /api/internal/products?source=api&id_source=external-1
   ```

2. Send only changed mutable fields. Do not send `source` or `id_source`; use them only as lookup filters.

   ```text
   POST /api/internal/products/{id}/update
   ```

3. Use `price_cents` for exact money updates when possible.

4. Use `replace_images=true` only when the user intends to remove existing product images.

## Product Review Workflow

Use product review APIs to create, update, or delete storefront reviews. New internal API reviews default to `published`.

1. Create a simple published review by product ID or slug:

   ```text
   POST /api/internal/products/{productIdentifier}/reviews/create
   {"name":"Jane Doe","content":"Great product.","image_urls":["https://example.com/review.jpg"]}
   ```

2. Include `score` only when it should differ from the default `5`.

3. Use `status` when a review should be created as `pending` or `rejected` instead of `published`.

4. Update mutable review fields by review ID:

   ```text
   POST /api/internal/reviews/{review}/update
   {"content":"Updated review text","score":4}
   ```

5. Use `replace_images=true` only when the user intends to remove existing review images.

6. Delete a review by ID:

   ```text
   POST /api/internal/reviews/{review}/delete
   ```

## Combination Workflow

Use combinations for products where storefront price/options come from Lunar HQ combination definitions.

1. List available combinations:

   ```text
   GET /api/internal/combinations
   ```

2. Inspect a combination before assigning it:

   ```text
   GET /api/internal/combinations/{id}
   ```

3. Assign it to a product:

   ```text
   POST /api/internal/products/{id}/combination
   {"combination_id": 32}
   ```

4. Remove it by posting `null`:

   ```text
   POST /api/internal/products/{id}/combination
   {"combination_id": null}
   ```

5. Verify min/max prices:

   ```text
   GET /api/internal/products/{id}/combination
   ```

## Search Logs Workflow

Use search logs for storefront search analytics. Raw logs preserve history; summary mode derives keyword counts.

1. List recent raw logs:

   ```text
   GET /api/internal/search-logs
   ```

2. Filter by keyword or date:

   ```text
   GET /api/internal/search-logs?keyword=poster&created_from=2026-06-01&created_to=2026-06-23
   ```

3. Get top searched keywords:

   ```text
   GET /api/internal/search-logs?summary=1
   ```

## Website Settings Workflow

For site name, description, theme, logo paths, cache flag, or custom scripts/styles:

```text
POST /api/internal/settings
{"group":"site","attributes":{...}}
```

For footer content:

```text
POST /api/internal/settings
{"group":"footer","attributes":{...}}
```

For Pinterest settings:

```text
POST /api/internal/settings
{"group":"pinterest","attributes":{...}}
```

## Locale Workflow

Set the complete desired locale list; do not send only a delta unless the API contract changes.

```text
POST /api/internal/locales
{"locales":["en","fr","de"]}
```

## Redirect Domain Workflow

Configure redirect target first, then enable or disable the redirect flag:

```text
POST /api/internal/redirect-domain
{"new_domain":"new-store.example.com"}
```

```text
POST /api/internal/redirect-domain/toggle
{"enable":true}
```

## Cache Clear Workflow

Clear website cache after content, product, settings, theme, or domain changes when the user asks for fresh storefront output:

```text
POST /api/internal/cache/clear
```

Re-fetch the affected storefront or internal resource after clearing cache when verification is required.

## Safety Checklist

- Confirm target tenant domain before writes.
- Confirm the internal API token came from the caller's secure runtime, secret manager, HTTP credential store, or explicit credentials.
- Prefer draft status for newly created products unless publishing is requested.
- Product reviews created through the internal API default to published; set `status` explicitly when moderation is required.
- Avoid product deletion; no active delete API is available.
- Use exact cents fields for price automation.
- Clear cache after updates when the user needs storefront changes visible immediately.
- Re-fetch updated entities after POST requests.
