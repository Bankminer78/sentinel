"""Legacy UI shim.

The dashboard now lives at sentinel/static/{index.html, app.js, style.css}
served via FastAPI StaticFiles + a FileResponse for the root route. This
file used to embed the entire HTML in a Python triple-quoted string, which
turned out to be a bad idea: a misplaced backslash in the JS broke the
whole dashboard with no static checking to catch it.

This module stays as a stub so the existing import in sentinel/server.py
keeps working until Phase 3 of the refactor cleans up the import list.
"""


def get_ui_html() -> str:
    """Returns a redirect note. Real UI is served by FastAPI StaticFiles."""
    return (
        "<!DOCTYPE html><html><body>"
        "<p>Sentinel UI moved. Visit <a href='/'>/</a></p>"
        "</body></html>"
    )
