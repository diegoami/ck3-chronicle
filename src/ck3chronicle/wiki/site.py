"""What a published site says about where it came from: nothing hard-wired.

The POC wrote its own repository into every page footer, its companion into
the landing page and its documents into every ``portraits.json``. Here each
is a setting (``[site]`` in ``ck3chronicle.toml``), passed to the renderer
and the manifest writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The product's own home: the footer's link unless configured otherwise.
HOME = "https://github.com/diegoami/ck3-chronicle"


def default_docs() -> dict[str, str]:
    """Where the image-name rule is written down, as ``portraits.json`` says.

    No ``images`` entry: where delivered images live is the deployment's to
    say, and a site that has not said so gets no link rather than someone
    else's.
    """
    return {
        "names": f"{HOME}/blob/main/docs/IMAGES.md#the-rule",
        "contract": f"{HOME}/blob/main/docs/IMAGES.md",
    }


@dataclass(frozen=True)
class Site:
    """The links a site carries.

    `generator_*` is the footer's "Generated ... by"; `companion_*` names the
    tool that harvests the images, on the landing page, and is left out when
    unset; `docs` is ``portraits.json``'s ``docs`` block, in order.
    """

    generator_name: str = "ck3-chronicle"
    generator_url: str = HOME
    companion_name: str | None = None
    companion_url: str | None = None
    docs: dict[str, str] = field(default_factory=default_docs)

    @property
    def companion_label(self) -> str | None:
        """The companion's link text: its name, else its URL's last segment."""
        if not self.companion_url:
            return None
        return self.companion_name or self.companion_url.rstrip("/").rsplit("/", 1)[-1]


DEFAULT_SITE = Site()
