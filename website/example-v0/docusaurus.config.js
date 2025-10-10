// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'ABI Platform',
  tagline: 'Build Your Custom AI with Agentic Brain Infrastructure',
      favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://abi-platform.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'jupyter-naas', // Usually your GitHub org/user name.
  projectName: 'abi', // Usually your repo name.

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/jupyter-naas/abi/tree/main/website/example-v0/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/jupyter-naas/abi/tree/main/website/example-v0/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Replace with your project's social card
      image: 'img/abi-social-card.jpg',
      navbar: {
        title: 'ABI Platform',
        logo: {
          alt: 'ABI Logo',
          src: 'img/logo.png',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Documentation',
          },
          {to: '/chat', label: 'Chat', position: 'left'},
          {
            href: 'https://github.com/jupyter-naas/abi',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: 'Getting Started',
                to: '/docs/intro',
              },
              {
                label: 'Chat',
                to: '/chat',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/jupyter-naas/abi',
              },
              {
                label: 'Issues',
                href: 'https://github.com/jupyter-naas/abi/issues',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'Naas AI',
                href: 'https://naas.ai',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Naas AI. Built with ABI.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
