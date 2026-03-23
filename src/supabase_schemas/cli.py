"""CLI entry point for supabase-schemas."""
import sys
import argparse
from .schema_manager import SchemaManager


def main():
    parser = argparse.ArgumentParser(
        prog="supabase-schemas",
        description="Per-tenant PostgreSQL schema manager for Supabase",
    )
    parser.add_argument(
        "command",
        choices=["create", "drop", "list", "migrate"],
        help="Command to run",
    )
    parser.add_argument("tenant_id", nargs="?", help="Tenant ID")
    parser.add_argument("--migrations-dir", default="./migrations", help="Path to migrations directory")
    parser.add_argument("--force", action="store_true", help="Force drop without confirmation")
    parser.add_argument("--details", action="store_true", help="Show extra details in list")
    parser.add_argument("--url", help="Database URL (or DATABASE_URL env var)")

    args = parser.parse_args()

    import os
    db_url = args.url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: --url or DATABASE_URL env var required", file=sys.stderr)
        sys.exit(1)

    mgr = SchemaManager(db_url)

    if args.command == "create":
        if not args.tenant_id:
            print("Error: tenant_id required for create", file=sys.stderr)
            sys.exit(1)
        mgr.create_schema(args.tenant_id, migrations_dir=args.migrations_dir)
        print(f"Created schema for tenant: {args.tenant_id}")

    elif args.command == "drop":
        if not args.tenant_id:
            print("Error: tenant_id required for drop", file=sys.stderr)
            sys.exit(1)
        if not args.force:
            confirm = input(f"Drop schema for '{args.tenant_id}'? [y/N] ")
            if confirm.lower() != "y":
                print("Aborted.")
                sys.exit(0)
        mgr.drop_schema(args.tenant_id)
        print(f"Dropped schema for tenant: {args.tenant_id}")

    elif args.command == "list":
        schemas = mgr.list_schemas(details=args.details)
        if not schemas:
            print("No tenant schemas found.")
        for s in schemas:
            print(f"  {s}")

    elif args.command == "migrate":
        if not args.tenant_id:
            print("Error: tenant_id required for migrate", file=sys.stderr)
            sys.exit(1)
        mgr.migrate(args.tenant_id, migrations_dir=args.migrations_dir)
        print(f"Migrations applied for tenant: {args.tenant_id}")


if __name__ == "__main__":
    main()
