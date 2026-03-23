"""CLI entry point for supabase-schemas."""
import sys
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        prog="supabase-schemas",
        description="Per-tenant PostgreSQL schema manager for Supabase",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["create", "drop", "list", "migrate"],
        help="Command to run",
    )
    parser.add_argument("tenant_id", nargs="?", help="Tenant ID")
    parser.add_argument("--migrations-dir", default="./migrations", help="Path to migrations directory")
    parser.add_argument("--force", action="store_true", help="Force drop without confirmation")
    parser.add_argument("--details", action="store_true", help="Show extra details in list")
    parser.add_argument("--url", help="Database URL (or DATABASE_URL env var)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    db_url = args.url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: --url or DATABASE_URL env var required", file=sys.stderr)
        sys.exit(1)

    from .schema_manager import (
        create_app_schema,
        drop_app_schema,
        list_app_schemas,
        run_migrations,
        get_connection,
    )

    if args.command == "create":
        if not args.tenant_id:
            print("Error: tenant_id required for create", file=sys.stderr)
            sys.exit(1)
        schema = create_app_schema(args.tenant_id)
        print(f"Created schema for tenant: {args.tenant_id} → {schema}")

    elif args.command == "drop":
        if not args.tenant_id:
            print("Error: tenant_id required for drop", file=sys.stderr)
            sys.exit(1)
        if not args.force:
            confirm = input(f"Drop schema for '{args.tenant_id}'? [y/N] ")
            if confirm.lower() != "y":
                print("Aborted.")
                sys.exit(0)
        drop_app_schema(args.tenant_id)
        print(f"Dropped schema for tenant: {args.tenant_id}")

    elif args.command == "list":
        schemas = list_app_schemas()
        if not schemas:
            print("No tenant schemas found.")
        for s in schemas:
            print(f"  {s}")

    elif args.command == "migrate":
        if not args.tenant_id:
            print("Error: tenant_id required for migrate", file=sys.stderr)
            sys.exit(1)
        applied = run_migrations(args.tenant_id, migrations_dir=args.migrations_dir)
        print(f"Applied {len(applied)} migrations for tenant: {args.tenant_id}")


if __name__ == "__main__":
    main()
