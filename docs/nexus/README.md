# Nexus customisations

Documentation for all features added to Nexus (ABI's web application) beyond the upstream defaults.

## Contents

| File | What it covers |
|---|---|
| [lab.md](./lab.md) | Lab IDE — file tree, Monaco editor, keyboard shortcuts |
| [previews.md](./previews.md) | Markdown & HTML/Slides preview modes |
| [slides.md](./slides.md) | Slide deck authoring format and AI generation |
| [opencode.md](./opencode.md) | opencode AI coding assistant integration |
| [git-integration.md](./git-integration.md) | Git branch selector in the Nexus navbar |
| [file-palette.md](./file-palette.md) | Cmd+P file search palette |
| [terminal.md](./terminal.md) | Integrated bash terminal (PTY + xterm.js) |
| [agent-logos.md](./agent-logos.md) | Automatic AI provider logo resolution |
| [api-reference.md](./api-reference.md) | All new backend API endpoints |

## Quick start

```bash
cd ~/aia
make up
# Nexus:    http://127.0.0.1:3042
# API:      http://127.0.0.1:9879
# opencode: http://127.0.0.1:4242
```

## Key files changed

### Backend (`naas_abi/apps/nexus/apps/api/`)
```
app/api/endpoints/
  lab_fs.py        # filesystem API + raw file serve
  lab_git.py       # git branches / status / checkout
  lab_terminal.py  # PTY WebSocket terminal
app/api/router.py  # router registrations
```

### Frontend (`naas_abi/apps/nexus/apps/web/src/`)
```
app/workspace/[workspaceId]/lab/page.tsx   # Lab page (editor + previews + terminal)
components/shell/
  header.tsx                  # branch selector + file palette trigger
  file-palette.tsx            # Cmd+P search modal
  terminal-pane.tsx           # xterm.js terminal component
  sidebar/
    chat-section.tsx          # agent logos + list/grid toggle
    lab-section.tsx           # file tree (host filesystem)
hooks/use-git.ts              # git polling hook
stores/files.ts               # host filesystem store actions
```

### Config (`~/aia/`)
```
Makefile                  # make up starts stack + opencode
src/opencode/config/opencode.json   # model, MCP, instructions
AGENTS.md                 # opencode system context
SLIDES.md                 # slide format spec (loaded by opencode)
```
