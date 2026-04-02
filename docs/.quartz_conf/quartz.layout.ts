import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"
import { QuartzComponent, QuartzComponentConstructor } from "./quartz/components/types"

const defaultTheme = process.env.DEFAULT_THEME === "light" ? "light" : "dark"

/* ── Force default theme ─────────────────────────────────────── */
const ForceDarkDefault: QuartzComponent = () => null
ForceDarkDefault.beforeDOMLoaded = `
const savedTheme = localStorage.getItem("theme")
if (!savedTheme) {
  localStorage.setItem("theme", "${defaultTheme}")
  document.documentElement.setAttribute("saved-theme", "${defaultTheme}")
}
`

/* ── naas.ai top navigation bar ──────────────────────────────── */
const NaasTopBar: QuartzComponent = () => null
NaasTopBar.afterDOMLoaded = `
;(function () {
  const bar = document.createElement('nav')
  bar.id = 'naas-topbar'
  bar.innerHTML = \`
    <div class="naas-topbar-inner">
      <a href="https://naas.ai" class="naas-topbar-logo" aria-label="naas.ai home">
        <svg width="72" height="20" viewBox="0 0 72 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <text x="0" y="16" font-family="Comfortaa, sans-serif" font-weight="700" font-size="16" fill="#22c55e">naas.ai</text>
        </svg>
      </a>
      <div class="naas-topbar-divider"></div>
      <span class="naas-topbar-section">Documentation</span>
      <div class="naas-topbar-spacer"></div>
      <a href="https://github.com/jupyter-naas/abi" class="naas-topbar-link" target="_blank" rel="noopener">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
        GitHub
      </a>
      <a href="https://naas.ai" class="naas-topbar-back">← naas.ai</a>
      <a href="https://naas.ai/#get-started" class="naas-topbar-cta">Get Started</a>
    </div>
  \`
  document.body.insertBefore(bar, document.body.firstChild)
})()
`

const ForceDarkDefaultComponent: QuartzComponentConstructor = () => ForceDarkDefault
const NaasTopBarComponent: QuartzComponentConstructor = () => NaasTopBar

export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [ForceDarkDefaultComponent(), NaasTopBarComponent()],
  footer: Component.Footer({
    links: {
      "naas.ai": "https://naas.ai",
      GitHub: "https://github.com/jupyter-naas/abi",
      Discord: "https://discord.gg/cRFFHYye7t",
    },
  }),
}

export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
        { Component: Component.ReaderMode() },
      ],
    }),
    Component.Explorer(),
  ],
  right: [
    Component.Graph(),
    Component.DesktopOnly(Component.TableOfContents()),
    Component.Backlinks(),
  ],
}

export const defaultListPageLayout: PageLayout = {
  beforeBody: [Component.Breadcrumbs(), Component.ArticleTitle(), Component.ContentMeta()],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
      ],
    }),
    Component.Explorer(),
  ],
  right: [],
}
