const algoliasearch = require('algoliasearch');
const fs = require('fs');
const path = require('path');
const matter = require('gray-matter');

// Load environment variables
require('dotenv').config();

// Function to extract text content from markdown
function extractContent(markdown) {
  return markdown
    .replace(/```[\s\S]*?```/g, '') // Remove code blocks
    .replace(/`[^`]*`/g, '') // Remove inline code
    .replace(/#{1,6}\s/g, '') // Remove headers
    .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold
    .replace(/\*(.*?)\*/g, '$1') // Remove italic
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // Remove links, keep text
    .replace(/\n+/g, ' ') // Replace newlines with spaces
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim();
}

// Function to recursively read markdown files
function readMarkdownFiles(docsDir, baseUrl = '', context = null) {
  const records = [];

  if (!fs.existsSync(docsDir)) {
    return records;
  }

  const files = fs.readdirSync(docsDir);

  for (const file of files) {
    const filePath = path.join(docsDir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory() && !file.startsWith('.') && !file.startsWith('_')) {
      // Recursively read subdirectories
      const subRecords = readMarkdownFiles(filePath, `${baseUrl}/${file}`, context);
      records.push(...subRecords);
    } else if (file.endsWith('.md') && file !== 'README.md') {
      try {
        const content = fs.readFileSync(filePath, 'utf8');
        const { data: frontmatter, content: markdown } = matter(content);

        // Skip if explicitly excluded
        if (frontmatter.algolia === false) {
          continue;
        }

        // Extract title from frontmatter or first heading
        const title = frontmatter.title ||
                     markdown.match(/^#\s+(.+)$/m)?.[1] ||
                     file.replace('.md', '').replace(/[-_]/g, ' ');

        // Create URL path
        let urlPath;
        if (file === 'index.md') {
          urlPath = baseUrl || '/';
        } else {
          urlPath = `${baseUrl}/${file.replace('.md', '')}`;
        }

        // Clean up URL path
        urlPath = urlPath.replace(/\/+/g, '/').replace(/\/$/, '') || '/';

        // Make URL absolute for Docusaurus search (use site config URL or fallback)
        const siteUrl = context.siteConfig?.url || 'http://localhost:3003';
        const absoluteUrl = `${siteUrl}${urlPath}`;

        // Extract hierarchy from path
        const pathParts = baseUrl.split('/').filter(Boolean);
        const hierarchy = {
          lvl0: pathParts[0] ? pathParts[0].replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Documentation',
          lvl1: pathParts[1] ? pathParts[1].replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : title,
          lvl2: pathParts[2] ? pathParts[2].replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : null,
        };

        // Extract content and limit length
        const cleanContent = extractContent(markdown);
        const contentPreview = cleanContent.substring(0, 8000);

        const record = {
          objectID: urlPath.replace(/^\//, '') || 'home',
          title,
          content: contentPreview,
          url: absoluteUrl,
          hierarchy,
          type: 'content',
          // Docusaurus-specific fields for faceting
          docusaurus_tag: 'default',
          language: 'en',
          lang: 'en',
          version: 'current',
          // Add additional metadata
          lastModified: stat.mtime.toISOString(),
          wordCount: cleanContent.split(/\s+/).length
        };

        records.push(record);
        console.log(` Indexed: ${title} (${urlPath})`);
      } catch (error) {
        console.error(` Error processing ${filePath}:`, error.message);
      }
    }
  }

  return records;
}

// Docusaurus plugin
module.exports = function algoliaIndexPlugin(context, options) {
  return {
    name: 'algolia-index-plugin',

    async postBuild({ siteConfig, routesPaths, outDir }) {
      // Get admin API key from environment or options
      const adminApiKey = options.adminApiKey || process.env.ALGOLIA_ADMIN_API_KEY;

      console.log(' Debug: Admin API Key from options:', options.adminApiKey ? 'PROVIDED' : 'NOT PROVIDED');
      console.log(' Debug: Admin API Key from env:', process.env.ALGOLIA_ADMIN_API_KEY ? 'PROVIDED' : 'NOT PROVIDED');

      // Only run if we have Algolia admin credentials
      if (!adminApiKey) {
        console.log('  Skipping Algolia indexing - no admin API key provided');
        return;
      }

      try {
        console.log(' Starting Algolia indexing...');

        // Initialize Algolia client (v4 API)
        const client = algoliasearch(options.appId, adminApiKey);
        const index = client.initIndex(options.indexName);

        // Read all markdown files from the docs directory
        const docsDir = path.join(context.siteDir, 'docs');
        const records = readMarkdownFiles(docsDir, '', context);

        console.log(` Found ${records.length} documents to index`);

        if (records.length === 0) {
          console.log('  No documents found to index');
          return;
        }

        // Clear existing index (v4 API)
        await index.clearObjects();
        console.log('  Cleared existing index');

        // Add records to Algolia in batches (v4 API)
        const batchSize = 100;
        const batches = [];

        for (let i = 0; i < records.length; i += batchSize) {
          batches.push(records.slice(i, i + batchSize));
        }

        let totalIndexed = 0;
        for (const batch of batches) {
          const { objectIDs } = await index.saveObjects(batch);
          const batchSize = batch.length;
          totalIndexed += batchSize;
          console.log(` Indexed batch: ${batchSize} documents`);
        }

        console.log(` Successfully indexed ${totalIndexed} documents to Algolia`);

        // Configure index settings for better search (v4 API)
        await index.setSettings({
            searchableAttributes: [
              'title',
              'hierarchy.lvl0',
              'hierarchy.lvl1',
              'hierarchy.lvl2',
              'content'
            ],
            attributesToHighlight: [
              'title',
              'hierarchy.lvl0',
              'hierarchy.lvl1',
              'content'
            ],
            attributesToSnippet: [
              'content:20'
            ],
            // Critical: Add faceting attributes for Docusaurus
            attributesForFaceting: [
              'docusaurus_tag',
              'language',
              'lang',
              'version',
              'type'
            ],
            ranking: [
              'typo',
              'geo',
              'words',
              'filters',
              'proximity',
              'attribute',
              'exact',
              'custom'
            ],
            customRanking: [
              'desc(wordCount)'
            ]
        });

        console.log('  Updated index settings');
        console.log(' Algolia indexing completed successfully!');

      } catch (error) {
        console.error(' Error during Algolia indexing:', error);
        throw error;
      }
    }
  };
};
