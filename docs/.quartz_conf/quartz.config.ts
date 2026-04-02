import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

const env = process.env
const fromEnv = (key: string, fallback: string) => env[key] ?? fallback

const config: QuartzConfig = {
  configuration: {
    pageTitle: fromEnv("SITE_TITLE", "naas.ai Docs"),
    pageTitleSuffix: fromEnv("SITE_TITLE_SUFFIX", " | naas.ai"),
    enableSPA: true,
    enablePopovers: true,
    analytics: {
      provider: "plausible",
    },
    locale: "en-US",
    baseUrl: fromEnv("BASE_URL", "localhost:8080"),
    ignorePatterns: ["private", "templates", ".obsidian", ".quartz_conf", "ontology", ".old"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
        typography: {
          header: "Comfortaa",
          body: "Comfortaa",
          code: "JetBrains Mono",
        },
      colors: {
        lightMode: {
          light: fromEnv("LIGHT_LIGHT", "#faf8f8"),
          lightgray: fromEnv("LIGHT_LIGHTGRAY", "#e5e5e5"),
          gray: fromEnv("LIGHT_GRAY", "#b8b8b8"),
          darkgray: fromEnv("LIGHT_DARKGRAY", "#4e4e4e"),
          dark: fromEnv("LIGHT_DARK", "#2b2b2b"),
          secondary: fromEnv("LIGHT_SECONDARY", "#284b63"),
          tertiary: fromEnv("LIGHT_TERTIARY", "#84a59d"),
          highlight: fromEnv("LIGHT_HIGHLIGHT", "rgba(143, 159, 169, 0.15)"),
          textHighlight: fromEnv("LIGHT_TEXT_HIGHLIGHT", "#fff23688"),
        },
        darkMode: {
          light: fromEnv("DARK_LIGHT", "hsl(240, 4%, 11%)"),
          lightgray: fromEnv("DARK_LIGHTGRAY", "hsl(0, 0%, 18%)"),
          gray: fromEnv("DARK_GRAY", "#22c55e"),
          darkgray: fromEnv("DARK_DARKGRAY", "hsl(0, 0%, 65%)"),
          dark: fromEnv("DARK_DARK", "hsl(0, 0%, 98%)"),
          secondary: fromEnv("DARK_SECONDARY", "#22c55e"),
          tertiary: fromEnv("DARK_TERTIARY", "#4ade80"),
          highlight: fromEnv("DARK_HIGHLIGHT", "rgba(34, 197, 94, 0.08)"),
          textHighlight: fromEnv("DARK_TEXT_HIGHLIGHT", "rgba(34, 197, 94, 0.2)"),
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "git", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      Plugin.CustomOgImages(),
    ],
  },
}

export default config
