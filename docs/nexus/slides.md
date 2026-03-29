# Slide decks

See also: [`~/aia/SLIDES.md`](../SLIDES.md) — the authoritative format spec loaded by opencode.

## Authoring slides

Slides are **plain HTML + CSS**, no framework required.

### File layout

```
src/<project>/
├── slides.html   ← deck (all slides, vertical scroll)
├── slides.css    ← all styles
└── images/       ← assets (hero photos, logos)
```

### HTML structure

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Deck Title</title>
  <link rel="stylesheet" href="slides.css" />
</head>
<body>

  <!-- Cover slide -->
  <div class="slide-wrapper">
    <div class="slide title-slide" id="slide-1">
      <h1>Title</h1>
      <div class="title-sub">Subtitle</div>
    </div>
  </div>

  <!-- Section divider -->
  <div class="slide-wrapper">
    <div class="slide section-slide" id="slide-s1">
      <div class="section-number">01</div>
      <h2 class="section-title">Chapter name</h2>
    </div>
  </div>

  <!-- Content slide -->
  <div class="slide-wrapper">
    <div class="slide content-slide" id="slide-2">
      <div class="slide-section">Section label</div>
      <h2 class="slide-title">Slide title</h2>
      <div class="slide-hook">One-line hook</div>
    </div>
  </div>

  <!-- Responsive scaler (always include) -->
  <script>
    function scaleSlides() {
      document.querySelectorAll(".slide-wrapper").forEach((w) => {
        const s = Math.min(w.offsetWidth / 1280, 1);
        const slide = w.querySelector(".slide");
        slide.style.transform = `scale(${s})`;
        w.style.paddingBottom = "0";
        w.style.height = Math.round(720 * s) + "px";
      });
    }
    requestAnimationFrame(scaleSlides);
    window.addEventListener("resize", scaleSlides);
  </script>
</body>
</html>
```

### Slide types

| Class | Use |
|---|---|
| `title-slide` | Cover / opening |
| `content-slide` | Regular body (most slides) |
| `section-slide` | Chapter divider |
| `closing-slide` | Final / CTA |

### CSS skeleton

```css
:root {
  --slide-w: 1280px;
  --slide-h: 720px;
  --color-primary: #002b5c;
  --color-accent:  #0570cc;
}

.slide-wrapper {
  width: 100%;
  max-width: 1280px;
  margin: 8px auto;
  position: relative;
  overflow: hidden;
}

.slide {
  position: absolute;
  top: 0; left: 0;
  width: 1280px;
  height: 720px;
  transform-origin: top left;
  padding: 48px 64px;
  box-sizing: border-box;
}
```

## Generating slides with AI

In the Lab AI pane (opencode), ask:

> *"Create a 6-slide deck about [topic] at `src/myproject/slides.html`, use dark navy and blue brand colors"*

opencode has `SLIDES.md` loaded as a system instruction so it knows the exact format, generates `slides.html` + `slides.css`, and writes them directly to the filesystem.

## Preview in Lab

1. Open `slides.html` in the Lab file tree
2. Split view appears automatically (editor left, slides right)
3. Make changes via the AI pane or editor
4. Press **Reload** to pick up CSS changes, or `Cmd+S` to save + auto-refresh

## Reference implementation

`src/fmz-engagement/apps/web-slides/src/` — full production deck with hero images, brand tokens, and PPTX export.
