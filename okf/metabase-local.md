---
type: operations
description: Local Metabase removal.
---

# Local Metabase

Metabase was stopped and uninstalled on 2026-10-27. The Docker container
`metabase` and image `metabase/metabase:latest` were removed and their absence
verified.

The Docker volume `metabase_data`, including application settings and the
embedded H2 database, was also deleted at the user's request and its absence
verified. Colima and Docker remain installed.

The source SQLite files under `output/customer_cleanup` and
`output/books_custom_modules` were mounted read-only and remain untouched.
