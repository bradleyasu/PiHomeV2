"""Generic HTTP callback registry for PiHome screens and services.

Any screen or service that needs to receive an HTTP callback (OAuth redirects,
webhook confirmations, etc.) can register a handler here rather than modifying
server.py directly.

Usage
-----
In your screen::

    from server.callbacks import register_callback, unregister_callback

    # Register when starting an auth / webhook flow:
    register_callback("/myapp/callback", self._handle_callback)

    # Handler receives the parsed query-string and returns HTML for the browser:
    def _handle_callback(self, params: dict[str, list[str]]) -> str:
        code = params.get("code", [None])[0]
        ...
        return "<h2>Done! You can close this tab.</h2>"

    # Unregister when leaving the screen or after the flow completes:
    unregister_callback("/myapp/callback")

Handler contract
----------------
* Called on the HTTP server thread — do NOT touch Kivy UI directly.
  Use ``Clock.schedule_once`` or start a background ``Thread`` instead.
* ``params`` — result of ``urllib.parse.parse_qs`` on the callback URL's
  query string; values are lists, e.g. ``params["code"][0]``.
* Return a plain HTML string to display in the browser, or ``None`` /
  empty string for a generic "OK" response.
"""

from typing import Callable

# path-prefix → callable
_REGISTRY: dict[str, Callable] = {}


def register_callback(path_prefix: str, handler: Callable) -> None:
    """Register *handler* for any GET whose path starts with *path_prefix*.

    Re-registering the same prefix silently replaces the previous handler.
    """
    _REGISTRY[path_prefix] = handler


def unregister_callback(path_prefix: str) -> None:
    """Remove the handler for *path_prefix* (no-op if not registered)."""
    _REGISTRY.pop(path_prefix, None)
