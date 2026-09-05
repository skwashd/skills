"""Site crawling and link checking."""

from dataclasses import dataclass, field


@dataclass
class Results:
    ok: bool = True
    broken: list[str] = field(default_factory=list)

    def render(self, fmt: str) -> str:
        if fmt == "json":
            import json

            return json.dumps({"ok": self.ok, "broken": self.broken})
        if not self.broken:
            return "All links OK"
        return "\n".join(f"BROKEN: {url}" for url in self.broken)


def check_site(url: str, depth: int = 2, dry_run: bool = False, auth_token: str | None = None) -> Results:
    """Crawl url to the given depth and verify every discovered link.

    When auth_token is set, requests carry it as a bearer token so
    authenticated pages can be crawled. In dry_run mode the crawl is
    planned but nothing is fetched.
    """
    raise NotImplementedError("network layer stripped for the eval fixture")
