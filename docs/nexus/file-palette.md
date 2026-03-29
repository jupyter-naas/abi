# File palette (Cmd+P)

VS Code-style quick file search available from anywhere in Nexus.

## Open

- Press `⌘P` (or `Ctrl+P`)
- Click the **Go to file…** search bar in the center of the navbar

## Behaviour

1. Opens immediately showing **recently opened files** (tabs currently open in Lab)
2. As you type, fuzzy-searches all files in `~/aia` via `/api/lab/fs/search`
3. Results are sorted: filename prefix match → filename contains → path contains
4. Selecting a file opens it in the Lab editor

## Keyboard navigation

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate results |
| `↵` Enter | Open selected file |
| `Esc` | Close palette |

## File icon colours

| Colour | Extensions |
|---|---|
| Blue | `.ts` `.tsx` |
| Yellow | `.js` `.jsx` |
| Green | `.py` |
| Purple | `.md` `.mdx` |
| Orange | `.html` `.htm` |
| Pink | `.css` `.scss` |
| Amber | `.json` `.yaml` `.yml` `.toml` |
| Emerald | `.sh` `.bash` `.zsh` |

## Source files

| File | Purpose |
|---|---|
| `.abi/.../api/endpoints/lab_fs.py` | `GET /api/lab/fs/search?q={query}&limit=40` |
| `.abi/.../web/src/components/shell/file-palette.tsx` | Palette modal component |
| `.abi/.../web/src/components/shell/header.tsx` | Trigger button + `⌘P` listener |
