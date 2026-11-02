---
myst:
  html_meta:
    description: A Markdown page with authored MyST metadata.
---

# MyST Markdown example

Markdown sources share the Sphinx build with the existing reStructuredText pages.
MyST parses this page into the same document tree used to produce HTML,
individual Markdown context files, and `llms.txt`.

## Build outputs

- Build HTML documentation.
- Generate Markdown context for each page.
- Optionally combine page content in `llms-full.txt`.

```python
print("MyST code survives conversion")
```

```{only} markdown
This MyST paragraph appears only in Markdown output.
```

Continue with [links from Markdown](myst-links.md) or the existing
[RST apple example](apples.rst).
