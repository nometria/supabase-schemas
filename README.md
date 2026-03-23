# supabase-schemas

> Per-tenant PostgreSQL schema manager for Supabase.

Run 80+ isolated app schemas inside a single Supabase instance.
Each tenant gets its own `app_<id>` schema with migration tracking and
an `auth.users` view — without paying for multiple Supabase projects.

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
git clone https://github.com/YOUR_ORG/supabase-schemas
cd supabase-schemas
pip install -r requirements.txt
cp .env.example .env
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
python src/schema_manager.py create my-tenant

# Create and run migrations immediately
python src/schema_manager.py create my-tenant --migrations-dir ./migrations

# List all tenant schemas
python src/schema_manager.py list
python src/schema_manager.py list --details   # also shows tables

# Run migrations for an existing schema
python src/schema_manager.py migrate my-tenant --migrations-dir ./migrations

# Drop a schema (DESTRUCTIVE — asks for confirmation)
python src/schema_manager.py drop my-tenant
python src/schema_manager.py drop my-tenant --force   # skip confirmation
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
