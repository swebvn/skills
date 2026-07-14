# Internal API Reference

## Contents

- [Products](#products)
- [Product Reviews](#product-reviews)
- [Combinations](#combinations)
- [Search Logs](#search-logs)
- [Settings And Site Controls](#settings-and-site-controls)
- [Cache Controls](#cache-controls)

All routes are tenant storefront routes under the target store domain supplied in the current task:

```text
https://{store_domain}/api/internal
```

Production access is guarded by the Lucommerce internal API middleware. External systems should send:

```text
Authorization: Bearer <INTERNAL_API_TOKEN>
```

The preferred runtime secret name is:

```text
LUCOMMERCE_INTERNAL_API_TOKEN
```

Accepted legacy alias:

```text
INTERNAL_API_TOKEN
```

The store domain is not configured in the skill because it depends on the store being managed. The caller must provide it in the task, for example `store.example.com`; normalize bare domains to `https://store.example.com`.

The token must be supplied by the calling environment, such as a secret manager, environment variable, secure tool setting, HTTP bearer credential, or explicit user-provided credential. Do not store the token in this skill. Some deployments may also allow requests from configured IPs without a bearer token.

Setup examples:

```bash
export LUCOMMERCE_INTERNAL_API_TOKEN="secret-token"
```

GitHub Actions:

```yaml
env:
  LUCOMMERCE_INTERNAL_API_TOKEN: ${{ secrets.LUCOMMERCE_INTERNAL_API_TOKEN }}
```

Generic HTTP clients should configure bearer authentication with `LUCOMMERCE_INTERNAL_API_TOKEN`; the store domain/base URL should come from the current task or workflow input.

## Products

### List Products

```text
GET /api/internal/products
```

Query parameters:

```text
status=draft|published
search=keyword
source=api
id_source=external-id
combination_id=32
per_page=1..100
```

Response:

```json
{
  "data": [
    {
      "id": 123,
      "status": "published",
      "name": "Galaxy Phone Case",
      "slug": "galaxy-phone-case",
      "sku": "CASE-001",
      "price": 24.9,
      "price_cents": 2490,
      "compare_price": 29.9,
      "compare_price_cents": 2990,
      "stock": 12,
      "collection_ids": [1],
      "source": "api",
      "id_source": "external-1",
      "meta": {"combination_id": 32},
      "combination_id": 32,
      "is_combination_product": true,
      "thumbnail_url": "https://...",
      "image_urls": ["https://..."]
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 25,
    "total": 1,
    "last_page": 1
  }
}
```

### Show Product

```text
GET /api/internal/products/{productIdentifier}
```

`productIdentifier` can be product ID or slug. Response includes the same shape as list items and, when a product has `combination_id`, combination min/max prices:

```json
{
  "data": {
    "id": 123,
    "combination_id": 32,
    "combination_min_price": 13.5,
    "combination_max_price": 17,
    "combination_min_price_cents": 1350,
    "combination_max_price_cents": 1700
  }
}
```

### Create Product

```text
POST /api/internal/products/create
```

Payload:

```json
{
  "name": "Galaxy Phone Case",
  "description": "A durable case.",
  "short_description": "Durable case",
  "status": "draft",
  "slug": "galaxy-phone-case",
  "sku": "CASE-001",
  "price": 24.9,
  "price_cents": 2490,
  "compare_price": 29.9,
  "compare_price_cents": 2990,
  "stock": 12,
  "collection_ids": [1, 2],
  "image_urls": ["https://example.com/image.jpg"],
  "source": "api",
  "id_source": "external-1",
  "meta": {"campaign": "summer"},
  "combination_id": 32
}
```

Required:

- `name`
- either `price` or `price_cents`

Notes:

- `status` defaults to `draft`.
- `slug` defaults to a unique slug generated from `name`.
- `price` and `compare_price` are major units; `price_cents` and `compare_price_cents` are integer cents.
- `source` and `id_source` are create-only external identity fields. Set them when creating synced products, then use list filters to find the product later.
- `combination_id` is saved into product `meta.combination_id`.
- `image_urls` are fetched server-side into the product media collection.

### Update Product

```text
POST /api/internal/products/{productIdentifier}/update
```

Use any subset of mutable product fields from the create payload. Do not send `source` or `id_source`; the update API rejects those fields because external identity is immutable after create.

To replace all images, include:

```json
{
  "replace_images": true,
  "image_urls": ["https://example.com/new-image.jpg"]
}
```

To clear a product combination:

```json
{
  "combination_id": null
}
```

### Delete Product

No active product delete route exists. Do not call `/api/internal/products/{productIdentifier}/delete`; it is intentionally commented out.

## Product Reviews

### Create Product Review

```text
POST /api/internal/products/{productIdentifier}/reviews/create
```

`productIdentifier` can be product ID or slug.

Simple payload:

```json
{
  "name": "Jane Doe",
  "content": "Great product, exactly as described.",
  "image_urls": ["https://example.com/review-1.jpg"]
}
```

Full payload:

```json
{
  "name": "Jane Doe",
  "author": "Jane Doe",
  "email": "jane@example.com",
  "score": 5,
  "content": "Great product, exactly as described.",
  "status": "published",
  "rejection_reason": null,
  "created_at": "2026-07-01T10:00:00Z",
  "image_urls": [
    "https://example.com/review-1.jpg",
    "https://example.com/review-2.webp"
  ]
}
```

Required:

- `name` or `author`
- `content`

Notes:

- `name` is stored as the review `author`.
- `score` defaults to `5`.
- `status` defaults to `published`.
- Supported statuses are `pending`, `published`, and `rejected`.
- `image_urls` are fetched server-side into the `review_images` media collection. Send up to 5 images.

Response:

```json
{
  "data": {
    "id": 123,
    "product_id": 456,
    "product_name": "Galaxy Phone Case",
    "name": "Jane Doe",
    "author": "Jane Doe",
    "email": "jane@example.com",
    "score": 5,
    "content": "Great product, exactly as described.",
    "status": "published",
    "rejection_reason": null,
    "image_urls": ["https://..."],
    "created_at": "2026-07-01T10:00:00+00:00",
    "updated_at": "2026-07-01T10:00:00+00:00"
  }
}
```

### Update Review

```text
POST /api/internal/reviews/{review}/update
```

Use any subset of mutable review fields from the create payload. To replace all review images, include:

```json
{
  "replace_images": true,
  "image_urls": ["https://example.com/new-review-image.jpg"]
}
```

Publishing or unpublishing a review is a status update:

```json
{"status": "pending"}
```

### Delete Review

```text
POST /api/internal/reviews/{review}/delete
```

Deletes the review and clears its `review_images` media collection.

## Combinations

Combinations are remote catalog definitions fetched through `App\Services\Combination` from Lunar HQ.

### List Combinations

```text
GET /api/internal/combinations
```

Response:

```json
{
  "data": [
    {"id": 32, "name": "Phone Case"}
  ]
}
```

### Show Combination

```text
GET /api/internal/combinations/{combination}
```

Response:

```json
{
  "data": {
    "id": 32,
    "name": "Phone Case",
    "variants": [],
    "extra_options": []
  }
}
```

### Show Product Combination

```text
GET /api/internal/products/{productIdentifier}/combination
```

Response:

```json
{
  "product_id": 123,
  "combination_id": 32,
  "combination": {"id": 32, "name": "Phone Case"},
  "combination_min_price": 13.5,
  "combination_max_price": 17,
  "combination_min_price_cents": 1350,
  "combination_max_price_cents": 1700
}
```

### Update Product Combination

```text
POST /api/internal/products/{productIdentifier}/combination
```

Set:

```json
{"combination_id": 32}
```

Remove:

```json
{"combination_id": null}
```

The API validates non-null IDs by fetching the combination from Lunar HQ.

## Search Logs

### List Raw Search Logs

```text
GET /api/internal/search-logs
```

Query parameters:

```text
keyword=poster
created_from=2026-06-01
created_to=2026-06-23
per_page=1..100
```

Response:

```json
{
  "data": [
    {
      "id": 1,
      "keyword": "poster",
      "results_count": 4,
      "created_at": "2026-06-23T10:00:00.000000Z"
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 25,
    "total": 1,
    "last_page": 1
  }
}
```

### Summarize Search Logs

Use `summary=1` to group raw logs by keyword and return derived counts:

```text
GET /api/internal/search-logs?summary=1
```

Query parameters:

```text
keyword=poster
created_from=2026-06-01
created_to=2026-06-23
per_page=1..100
summary=1
```

Response:

```json
{
  "data": [
    {
      "keyword": "poster",
      "searches_count": 12,
      "last_searched_at": "2026-06-23 10:00:00"
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 25,
    "total": 1,
    "last_page": 1
  }
}
```

## Settings And Site Controls

### Update Settings

```text
POST /api/internal/settings
```

Payload:

```json
{
  "group": "site",
  "attributes": {
    "name": "Store Name",
    "description": "Store description",
    "theme": "lunar-3"
  }
}
```

Supported groups:

- `site`
- `footer`
- `pinterest`

### Update Locales

```text
POST /api/internal/locales
```

Payload:

```json
{
  "locales": ["en", "fr", "de"]
}
```

Supported locale values:

```text
en, fr, de, es, it, pt, zh, ja, ko
```

### Redirect Domain

```text
POST /api/internal/redirect-domain
POST /api/internal/redirect-domain/toggle
```

Configure redirect:

```json
{"new_domain": "new-store.example.com"}
```

Toggle redirect:

```json
{"enable": true}
```

## Cache Controls

### Clear Website Cache

```text
POST /api/internal/cache/clear
```

Clears storefront response/page cache, application cache, and settings cache.

Response:

```json
{
  "message": "Website cache cleared successfully."
}
```
