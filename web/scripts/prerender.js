/**
 * Build-time prerender script.
 *
 * Flow:
 *   1. Reads the client-build's dist/index.html as the HTML template.
 *   2. Imports the SSR bundle (dist/server/entry-server.js) produced by
 *      `vite build --ssr`.
 *   3. For each public route: calls render(url), injects the HTML string and
 *      react-helmet-async head tags into the template, writes
 *      dist/path/index.html (or dist/index.html for /).
 *   4. Prints a summary.
 *
 * This file uses ES module syntax to match the project's "type": "module".
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const distDir = path.resolve(__dirname, '../dist')
const serverBundle = path.resolve(distDir, 'server/entry-server.js')

async function run() {
  if (!fs.existsSync(serverBundle)) {
    console.error('[prerender] SSR bundle not found at', serverBundle)
    console.error('  Run: vite build && vite build --ssr src/entry-server.tsx --outDir dist/server')
    process.exit(1)
  }

  const template = fs.readFileSync(path.join(distDir, 'index.html'), 'utf-8')
  const { render, routes } = await import(serverBundle)

  console.log(`[prerender] Rendering ${routes.length} public routes...`)
  let ok = 0

  for (const route of routes) {
    try {
      const { html: appHtml, helmet } = render(route)

      // Inject server-rendered content and head tags into the template.
      // Replace the empty root div and inject Helmet tags.
      const headTags = helmet
        ? [
            helmet.title?.toString() || '',
            helmet.meta?.toString() || '',
            helmet.link?.toString() || '',
            helmet.script?.toString() || '',
          ].join('\n    ')
        : ''

      let finalHtml = template
        // Replace the Helmet placeholder title (the generic one from index.html)
        // with the page-specific tags from react-helmet-async.
        .replace(
          /<title>.*?<\/title>/,
          headTags || '<title>TrustCapture</title>'
        )
        // Inject the rendered app HTML into the root div.
        .replace(
          '<div id="root"></div>',
          `<div id="root">${appHtml}</div>`
        )

      // Write to dist/route/index.html (or dist/index.html for /)
      const outPath =
        route === '/'
          ? path.join(distDir, 'index.html')
          : path.join(distDir, route.slice(1), 'index.html')

      fs.mkdirSync(path.dirname(outPath), { recursive: true })
      fs.writeFileSync(outPath, finalHtml)
      console.log(`  ✓  ${route}  →  ${path.relative(distDir, outPath)}`)
      ok++
    } catch (err) {
      console.error(`  ✗  ${route}  failed:`, err.message)
    }
  }

  console.log(`[prerender] Done: ${ok}/${routes.length} routes.`)
  if (ok < routes.length) process.exit(1)
}

run()
