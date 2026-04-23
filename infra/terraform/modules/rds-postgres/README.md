# rds-postgres

RDS Postgres 17 with `pgvector` preloaded. Master credentials are stored in Secrets Manager.

After `apply`, run once against the new database to enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

A future enhancement is to run this via a `null_resource` with `local-exec` + `psql` from a bastion or a Lambda backed function — kept manual for now to keep the module dependency-free.
