# Railway persistence

The application stores mutable state in SQLite: staff accounts, candidate accounts, tickets, ticket statuses, sessions, and audit history. A Railway deploy creates a new container filesystem, so that state must not live only under `/app/data`.

Configure the Railway service once:

1. Add a Railway Volume to the service.
2. Set its mount path to `/app/state`.
3. Add the variable `PERSISTENT_DATA_DIR=/app/state`.
4. Keep `MVP_DATA_DIR=data` so the bundled admissions sources remain available in the image.
5. Deploy and verify `/health`, then create a test ticket, restart/redeploy, and verify its status and owner remain present.

Production now refuses to start when `PERSISTENT_DATA_DIR` is missing or points at the knowledge directory. This prevents a deploy from appearing healthy while silently creating a blank database.

Do not mount the Volume over `/app/data`: that would hide the source PDF and `sources.md` copied into the image. The Docker Compose configuration uses `data/state` as the local equivalent.

This SQLite setup is intended for one Railway replica. If the service is scaled to multiple replicas, move the mutable state to PostgreSQL instead of sharing a SQLite file.

If the currently running deployment still has the old ephemeral database, copy it to the new Volume before the first restart if it is still accessible. Data already discarded with an old container cannot be reconstructed by the application.
