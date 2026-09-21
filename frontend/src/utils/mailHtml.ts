import DOMPurify from 'dompurify'

export function buildMailDocument(rawHtml: string): string {
  const safeHtml = DOMPurify.sanitize(rawHtml, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'link', 'meta'],
    FORBID_ATTR: ['src', 'srcset', 'href', 'onerror', 'onclick', 'onload', 'style'],
    ALLOW_DATA_ATTR: false,
  })

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
  <style>
    body { margin: 0; color: #202124; font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; word-break: break-word; }
    a { color: #1769aa; }
    img { max-width: 100%; height: auto; }
  </style>
</head>
<body>${safeHtml}</body>
</html>`
}
