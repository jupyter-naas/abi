// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

// const lightCodeTheme = require("prism-react-renderer/themes/github");

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "NaasAI Platform Docs",
  tagline:
    "Build AI Networks as a Service with ontology-powered intelligence. Create, deploy, and scale AI assistants that understand relationships across your data, models, and workflows.",
  favicon: "img/favicon.ico",

  // Set the production url of your site here
  url: "https://docs.naas.ai",
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: "/",

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "jupyter-naas",
  projectName: "abi",

  onBrokenLinks: "warn",
  onBrokenMarkdownLinks: "warn",

  // Even if you don't use internalization, you can use this field to set useful
  // metadata like html lang. For example, if your site is Chinese, you may want
  // to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve("./sidebars.js"),
          routeBasePath: "/", // Serve docs from root URL
          // Remove this to remove the "sedit this page" links.
        },
        blog: false,
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      }),
    ],
  ],

  themes: ["@docusaurus/theme-mermaid"],

  plugins: [
    [
      require.resolve("./plugins/algolia-index"),
      {
        appId: "NGBDVK8FYQ",
        adminApiKey: process.env.ALGOLIA_ADMIN_API_KEY, // We'll use environment variable for security
        indexName: "docs.naas.ai",
      },
    ],
  ],

  markdown: {
    mermaid: true,
    format: 'detect',
  },

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Social sharing configuration
      image: "img/landing-screensaver.gif",
      metadata: [
        { name: "twitter:card", content: "summary_large_image" },
        {
          name: "twitter:image",
          content: "https://docs.naas.ai/img/landing-screensaver.gif",
        },
        {
          property: "og:image",
          content: "https://docs.naas.ai/img/landing-screensaver.gif",
        },
        { property: "og:image:width", content: "1200" },
        { property: "og:image:height", content: "630" },
        { property: "og:type", content: "website" },
      ],
      // Algolia search configuration
      algolia: {
        appId: "NGBDVK8FYQ",
        apiKey: "f6ee1784b03f118828d7de35b9f7c178",
        indexName: "docs.naas.ai",
        contextualSearch: true,
      },
      fontFamily: {
        sans: ["San Francisco", "Arial", "sans-serif"],
      },
      colorMode: {
        defaultMode: "dark",
        disableSwitch: false,
      },
      navbar: {
        style: "dark",
        title: "",
        // For the scrollbar to be sticky or hide while scrolled down
        // hideOnScroll: true,
        logo: {
          alt: "Naas",
          href: "/",
          src: "/img/naas.png",
        },
        items: [
          {
            to: "get-started/quickstart",
            position: "left",
            label: "Get Started",
          },
          {
            to: "architecture/what-is-abi",
            position: "left",
            label: "Architecture",
          },
          {
            to: "capabilities/overview",
            position: "left",
            label: "Capabilities",
          },
          {
            to: "reference/libraries",
            position: "left",
            label: "Reference",
          },
          {
            to: "updates",
            position: "left",
            label: "Updates",
          },
          // Right side
          {
            to: "https://ontology.naas.ai/",
            label: "Ontology",
            position: "right",
          },
          {
            href: "https://github.com/jupyter-naas",
            position: "right",
            className: "header-github-link",
            "aria-label": "GitHub repository",
          },
        ],
      },
      footer: {
        style: "light",
        copyright: `
          <div style="display: flex; flex-direction: column; align-items: center; gap: 1rem;">
            <div style="display: flex; gap: 1rem; align-items: center;">
              <a href="https://github.com/jupyter-naas" target="_blank" rel="noopener noreferrer" style="color: var(--ifm-footer-link-color); transition: color 0.2s;" onmouseover="this.style.color='var(--ifm-color-primary)'" onmouseout="this.style.color='var(--ifm-footer-link-color)'">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
              </a>
              <a href="https://join.slack.com/t/naas-club/shared_invite/zt-1970s5rie-dXXkigAdEJYc~LPdQIEaLA" target="_blank" rel="noopener noreferrer" style="color: var(--ifm-footer-link-color); transition: color 0.2s;" onmouseover="this.style.color='var(--ifm-color-primary)'" onmouseout="this.style.color='var(--ifm-footer-link-color)'">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
                </svg>
              </a>
              <a href="https://www.linkedin.com/company/naas-ai/" target="_blank" rel="noopener noreferrer" style="color: var(--ifm-footer-link-color); transition: color 0.2s;" onmouseover="this.style.color='var(--ifm-color-primary)'" onmouseout="this.style.color='var(--ifm-footer-link-color)'">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
              </a>
              <a href="https://x.com/JupyterNaas" target="_blank" rel="noopener noreferrer" style="color: var(--ifm-footer-link-color); transition: color 0.2s;" onmouseover="this.style.color='var(--ifm-color-primary)'" onmouseout="this.style.color='var(--ifm-footer-link-color)'">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
              </a>
            </div>
            <div>
              Copyright © ${new Date().getFullYear()} <a href="https://home.naas.ai" target="_blank" rel="noopener noreferrer">NaasAI</a>, Inc.
            </div>
          </div>
        `,
      },
      //   navbar: {
      //   items: [
      //     {
      //       type: 'html',
      //       position: 'right',
      //       value: `<a href="https://www.naas.ai/auth/login" target="_blank"><button>Sign in</button><a>`,
      //     },
      //   ],
      // },
    }),
};

module.exports = config;
