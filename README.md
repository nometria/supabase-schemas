# supabase-schemas

Built by the [Nometria](https://nometria.com) team — we take AI-built apps to production.

> Per-tenant PostgreSQL schema manager for Supabase.

Run 80+ isolated app schemas inside a single Supabase instance.
Each tenant gets its own `app_<id>` schema with migration tracking and
an `auth.users` view — without paying for multiple Supabase projects.

---

## Quick start

```bash
# Clone and install
git clone https://github.com/nometria/supabase-schemas
cd supabase-schemas
pip install -e .

# Set your database URL
export DATABASE_URL=postgresql://postgres.your-ref:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres

# Create a tenant schema
supabase-schemas create acme-corp

# List all tenant schemas
supabase-schemas list

# Run migrations for a tenant
supabase-schemas migrate acme-corp --migrations-dir ./migrations

# Clone schema structure to a new tenant (no data)
supabase-schemas clone acme-corp acme-staging

# Export a tenant's data to JSON
supabase-schemas export acme-corp --output acme.json

# Drop a tenant schema
supabase-schemas drop acme-corp --force

# Run tests
pytest tests/ -v
```

---

## Why

Supabase multi-tenancy via schema-per-tenant is the most cost-effective
pattern for building multi-tenant SaaS. But there's no official CLI for it.
This fills that gap.

---

## Install

```bash
pip install supabase-schemas

# or from source:
git clone https://github.com/nometria/supabase-schemas
cd supabase-schemas
pip install -e .
```

---

## Setup

Set `DATABASE_URL` to your Supabase direct PostgreSQL connection:

```bash
# .env
DATABASE_URL=postgresql://postgres.your-ref:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

You also need this function in your Supabase SQL:

```sql
create or replace function public.ensure_schema_exposed(schema_name text)
returns void language plpgsql security definer as $$
begin
  execute format('create schema if not exists %I', schema_name);
  execute format('grant usage on schema %I to anon, authenticated, service_role', schema_name);
  execute format('alter default privileges in schema %I grant all on tables to anon, authenticated, service_role', schema_name);
end $$;
```

---

## Commands

```bash
# Create a new tenant schema
supabase-schemas create my-tenant

# Create and run migrations immediately
supabase-schemas create my-tenant --migrations-dir ./migrations

# List all tenant schemas
supabase-schemas list
supabase-schemas list --details   # also shows tables

# Run migrations for an existing schema
supabase-schemas migrate my-tenant --migrations-dir ./migrations

# Clone schema structure from one tenant to another (no data)
supabase-schemas clone acme-prod acme-staging

# Export a tenant's data to JSON
supabase-schemas export my-tenant                    # prints to stdout
supabase-schemas export my-tenant --output dump.json # writes to file

# Drop a schema (DESTRUCTIVE — asks for confirmation)
supabase-schemas drop my-tenant
supabase-schemas drop my-tenant --force   # skip confirmation
```

---

## How it works

1. `create` → calls `public.ensure_schema_exposed(schema_name)`, creates `_migrations` tracking table, injects `auth.users` view
2. `migrate` → reads `.sql` files sorted alphabetically, skips already-applied, records each in `_migrations`
3. `list` → queries `information_schema.schemata` for all `app_*` schemas
4. `drop` → `DROP SCHEMA CASCADE` (with confirmation prompt)
5. `clone` → creates target schema, then copies tables (`CREATE TABLE ... (LIKE source INCLUDING ALL)`), views (rewrites definitions to reference target), and functions (replaces schema qualifiers). No data is copied.
6. `export` → reads every table in the schema and serializes all rows to JSON with a `_manifest` header containing schema name, timestamp, per-table row counts, and total rows

Each schema gets: `app_<sanitized-id>` (lowercase, underscores, `app_` prefix).

---

## Clone details

`clone` copies the full schema structure without any row data:

- **Tables** -- uses `CREATE TABLE ... (LIKE source INCLUDING ALL)` to preserve indexes, constraints, defaults, and sequences
- **Views** -- reads `information_schema.views` and rewrites the definition to reference the target schema
- **Functions** -- reads `pg_proc` / `pg_get_functiondef` and replaces the schema qualifier

```bash
# Clone production structure into a staging schema
supabase-schemas clone acme-prod acme-staging

# Output:
#   Cloned table: orders
#   Cloned table: products
#   Cloned view: order_summary
#   Cloned function: calculate_total
#   Cloned schema 'app_acme_prod' -> 'app_acme_staging' (2 tables, 1 views, 1 functions, structure only)
```

---

## Export details

`export` dumps all table data to JSON with a manifest:

```bash
# Print to stdout
supabase-schemas export acme-prod

# Write to file
supabase-schemas export acme-prod --output acme-backup.json
```

Output format:

```json
{
  "_manifest": {
    "schema": "app_acme_prod",
    "exported_at": "2025-06-15T12:00:00+00:00",
    "tables": {
      "orders": 42,
      "products": 15
    },
    "total_rows": 57
  },
  "orders": [
    {"id": 1, "total": 99.50, "created_at": "2025-01-01"}
  ],
  "products": [
    {"id": 1, "name": "Widget", "price": 9.99}
  ]
}
```

Non-JSON-serializable values (bytes, datetime, UUID, Decimal) are automatically converted to strings.

---

## Immediate next steps
1. Publish to PyPI as `supabase-schemas`
2. Write blog post: "How to run 80+ isolated Postgres schemas in one Supabase project" — drives SEO + inbound

---

## Commercial viability
- Low standalone (open source is the right play)
- High as a content marketing asset — "Supabase multi-tenant" is a top-10 searched pattern
- Drives inbound to core platform: "now that you have your schemas sorted, let's self-host the whole thing"

---

## Example output

Running `pytest tests/ -v`:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-9.0.2, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: /tmp/ownmy-releases/supabase-schemas
configfile: pyproject.toml
plugins: anyio-4.12.1, cov-7.1.0
collecting ... collected 4 items

tests/test_schema_manager.py::test_schema_name_format PASSED             [ 25%]
tests/test_schema_manager.py::test_schema_name_sanitizes_special_chars PASSED [ 50%]
tests/test_schema_manager.py::test_import_succeeds_without_psycopg2 PASSED [ 75%]
tests/test_schema_manager.py::test_tenant_id_validation PASSED           [100%]

============================== 4 passed in 0.02s ===============================
```

See `examples/sample-schema-list.txt` for what `supabase-schemas list` output looks like.

