# Git integration

The Nexus navbar has a real-time Git branch selector wired to the `~/aia` repository.

## What it shows

- **Current branch name** with a colour code (green = main, blue = dev, cyan = feature/, red = hotfix/)
- **Change count badge** (amber) — sum of staged + changed + untracked files
- **Dropdown** with branch list, status summary, ahead/behind counts, and a "New branch" input

## Polling

The hook polls every 10 seconds. Click **Refresh** in the dropdown to force an immediate update.

## Checkout / create branch

Click any branch in the list to check it out. Click **+ New branch**, type a name, press Enter or **Create**.

## Source files

| File                                           | Purpose                                                    |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `.abi/.../api/endpoints/lab_git.py`            | Backend: `/api/lab/git/branches`, `/status`, `/checkout`   |
| `.abi/.../web/src/hooks/use-git.ts`            | React hook — polls branches + status, exposes `checkout()` |
| `.abi/.../web/src/components/shell/header.tsx` | Renders the branch button and dropdown                     |

## API reference

| Method | Endpoint                | Returns                                                        |
| ------ | ----------------------- | -------------------------------------------------------------- |
| `GET`  | `/api/lab/git/branches` | `[{name, current, ahead, behind}]`                             |
| `GET`  | `/api/lab/git/status`   | `{branch, staged[], changed[], untracked[], ahead, behind}`    |
| `POST` | `/api/lab/git/checkout` | `{branch, created}` — body: `{"branch":"name","create":false}` |
