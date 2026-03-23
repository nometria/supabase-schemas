# supabase-schemas

> Per-tenant PostgreSQL schema manager for Supabase.

Run 80+ isolated app schemas inside a single Supabase instance.
Each tenant gets its own `app_<id>` schema with migration tracking and
an `auth.users` view — without paying for multiple Supabase projects.

---

## Quick start

```bash
# Clone and install
git clone https://github.com/ownmy-app/supabase-schemas
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
pip install supabase-schemas    # PyPI (coming soon)

# or from source:
git clone https://github.com/ownmy-app/supabase-schemas
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

Each schema gets: `app_<sanitized-id>` (lowercase, underscores, `app_` prefix).

---

## Immediate next steps
1. Publish to PyPI as `supabase-schemas`
2. Write blog post: "How to run 80+ isolated Postgres schemas in one Supabase project" — drives SEO + inbound
3. Add `clone` command: copy schema structure (not data) from one tenant to another
4. Add `export` command: dump a tenant's data to JSON

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
