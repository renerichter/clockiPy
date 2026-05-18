# Credentials

clockiPy needs three values from your Clockify account:

| Variable                 | Required | Notes                                          |
| ------------------------ | -------- | ---------------------------------------------- |
| `CLOCKIFY_API_KEY`       | yes      | Personal API key from Clockify Profile.        |
| `CLOCKIFY_WORKSPACE_ID`  | yes      | Workspace to query. Use `clockipy --list`.     |
| `CLOCKIFY_USER_ID`       | no       | Auto-resolved from the API when missing.       |

## Resolution order (first complete wins)

1. **Process environment** — what `printenv CLOCKIFY_API_KEY` shows.
2. **`~/rene.env`** — the personal env file in your home directory.
3. **`./clockipy.env`** — project-local fallback (don't commit).

"First complete" means the first source that provides all required keys.
A partial match doesn't stop the search.

## Example files

`~/rene.env` and `./clockipy.env` accept both shell-export and bare KEY=VAL
syntax:

```bash
export CLOCKIFY_API_KEY="ck_abc..."
export CLOCKIFY_WORKSPACE_ID="62f1..."
# CLOCKIFY_USER_ID="63a0..."   # optional
```

## Discovering your IDs

```bash
clockipy --list
```

Prints your user record and every workspace you have access to.

## What happens when credentials are missing

clockiPy exits with status 2 and a message identifying which sources were
checked. Nothing is silently retried against the network.

## Security notes

- Never commit `clockipy.env` to git. The repo's `.gitignore` covers it.
- API keys go in the environment or `~/rene.env` only — both are outside
  the repo.
- `clockipy --list` and `clockipy --refresh` are the only commands that
  always hit the network. `--digest` and `--goals` read the local cache.
