# Runbook: Admin Bootstrap

How to create the initial platform admin safely. There is **no hardcoded admin
password** anywhere in the repository. An admin is created only when you supply a
secret out-of-band, either via the owner CLI (preferred) or a pre-hashed deploy
environment variable.

> **Never** paste a password, a password hash, or any database URL into chat,
> tickets, logs, or commit messages. The tooling only ever emits non-secret status
> codes.

## Status codes

The bootstrap step logs exactly one machine-greppable status per run (no values):

| Status code | Meaning |
|---|---|
| `ADMIN_EXISTS` | An admin row already exists. Nothing was created or changed. |
| `BOOTSTRAP_ENV_STILL_SET` | An admin exists **and** the bootstrap env vars are still set. Remove the env vars. Logged as a WARNING on every boot until removed. |
| `NO_ADMIN_NO_BOOTSTRAP` | The table is empty and no bootstrap secret was provided. Nothing was created (fail-closed). WARNING. |
| `BOOTSTRAP_INVALID reason=<code>` | A bootstrap secret was provided but is invalid (bad email, bad bcrypt prefix/length/cost, disallowed charset, or only one of the two env vars set). Nothing was created. ERROR. The `reason` is a code, never a value. |
| `ADMIN_CREATED` | Exactly one admin was created from the supplied secret. |
| `ALREADY_EXISTS` | A concurrent instance created the admin first (or a racing duplicate email). Non-fatal. |
| `BOOTSTRAP_DB_ERROR exc=<ClassName>` | A database error occurred (connection, lock timeout, etc.). The deploy path still exits 0 so the service starts. Only the exception class name is logged. |

The deploy entry point (`python -m app.core.admin_bootstrap`) **always exits 0** so
the service never crash-loops; `start.sh` additionally has a `|| echo` fallback.

## Preferred path: owner CLI (via Render Shell)

1. Open the service **Shell** in the Render dashboard (verify Shell availability on
   your plan first; if unavailable, use the env path below).
2. Run:
   ```
   python -m app.cli.create_admin --email admin@trustcapture.com
   ```
3. Enter the new password **twice** at the hidden prompts. It must be at least 14
   characters with a mix of character classes. The password is never echoed.
4. On success you see `ADMIN_CREATED` and the CLI exits 0.
   - If an admin already exists it is a **no-op** (exit 0). To add another admin
     deliberately, pass `--force-additional`.
   - A weak/short/mismatched password or bad email exits non-zero and creates nothing.

## Fallback path: pre-hashed deploy environment variable

Use this for non-interactive fresh environments when Render Shell is unavailable.

1. **Generate a bcrypt hash offline** (never in shared logs). Any trusted machine
   with the app's hasher works, for example:
   ```
   python -c "from app.core.security import hash_password; import getpass; print(hash_password(getpass.getpass()))"
   ```
   Copy the resulting `$2b$...` hash privately.
2. In the Render dashboard, set **two** environment variables on the service:
   - `ADMIN_BOOTSTRAP_EMAIL` = `admin@trustcapture.com`
   - `ADMIN_BOOTSTRAP_PASSWORD_HASH` = the generated bcrypt hash
   > Setting only one of the two is treated as `BOOTSTRAP_INVALID` and creates nothing.
3. Deploy. In the deploy logs, confirm the bootstrap step logged `ADMIN_CREATED`.
4. **Remove both env vars** (`ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD_HASH`)
   and redeploy. Confirm the `BOOTSTRAP_ENV_STILL_SET` warning **no longer appears**
   and the status is now `ADMIN_EXISTS`. Leaving the hash in the dashboard is a
   standing risk; removing it is mandatory.

## Verifying login

After bootstrap, confirm the admin can log in through the normal
`POST /api/admin/login` flow with the password you chose. Existing admin rows are
never modified by the bootstrap step.

## Reminders

- No password or hash is ever stored in source or printed by this tooling.
- `BOOTSTRAP_ENV_STILL_SET` on every boot means you forgot step 4 of the env path.
- Rotate the admin password through the normal application flow if you suspect
  exposure; treat any previously committed credential as permanently compromised.
