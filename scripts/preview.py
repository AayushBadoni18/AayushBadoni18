"""Local preview: wraps README.md in a column the width of GitHub's profile README (846px).
The README is plain HTML (p, a, img, br), which GitHub passes through unchanged, so no Markdown step is needed."""
import os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
body = open(os.path.join(root, "README.md"), encoding="utf-8").read().replace('<img ', '<img style="max-width:100%" ')
css = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css"
os.makedirs(os.path.join(root, "preview"), exist_ok=True)
open(os.path.join(root, "preview", "index.html"), "w", encoding="utf-8").write(
    f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
    f'<base href="/"><link rel="stylesheet" href="{css}">'
    f'<style>body{{margin:0}}@media(prefers-color-scheme:dark){{body{{background:#0d1117}}}}'
    f'.markdown-body{{box-sizing:border-box;max-width:894px;margin:0 auto;padding:24px}}@media(max-width:600px){{.markdown-body{{padding:16px}}}}</style>'
    f'<article class="markdown-body">{body}</article>')
print("preview/index.html written")
