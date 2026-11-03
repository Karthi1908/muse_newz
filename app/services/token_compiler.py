import json
from pathlib import Path
from config.settings import settings


def compile_tokens_css(
    tokens_path: Path | None = None,
    output_css_path: Path | None = None,
) -> str:
    """Compile design/tokens.v1.json into app/static/css/tokens.v1.css (Principle 6)."""
    src = tokens_path or (settings.DESIGN_DIR / "tokens.v1.json")
    dst = output_css_path or (settings.BASE_DIR / "app" / "static" / "css" / "tokens.v1.css")
    data = json.loads(src.read_text(encoding="utf-8"))

    typo = data["typography"]
    scale = typo["scale"]
    light = data["palette_light"]
    dark = data["palette_dark"]
    sem = data["verification_semantic"]
    grid = data["grid"]

    css = f"""/* AUTO-GENERATED FROM design/tokens.v1.json — Design Version {data["design_version"]} */
/* DO NOT EDIT MANUALLY. Principle 6: One design, many formats. */
:root {{
  --design-version: "{data["design_version"]}";
  --font-masthead: {typo["font_masthead"]};
  --font-headline: {typo["font_headline"]};
  --font-body: {typo["font_body"]};
  --font-ui: {typo["font_ui"]};
  --font-mono: {typo["font_mono"]};

  --scale-masthead: {scale["masthead"]};
  --scale-lead-headline: {scale["lead_headline"]};
  --scale-feature-headline: {scale["feature_headline"]};
  --scale-secondary-headline: {scale["secondary_headline"]};
  --scale-brief-headline: {scale["brief_headline"]};
  --scale-deck: {scale["deck"]};
  --scale-body: {scale["body"]};
  --scale-caption: {scale["caption"]};
  --scale-meta: {scale["meta"]};

  --bg-paper: {light["bg_paper"]};
  --bg-elevated: {light["bg_elevated"]};
  --ink-primary: {light["ink_primary"]};
  --ink-secondary: {light["ink_secondary"]};
  --ink-muted: {light["ink_muted"]};
  --rule-heavy: {light["rule_heavy"]};
  --rule-light: {light["rule_light"]};
  --outside-tint: {light["outside_tint"]};

  --verified-fg: {sem["verified_fg"]};
  --verified-bg: {sem["verified_bg"]};
  --corrected-removed-fg: {sem["corrected_removed_fg"]};
  --corrected-removed-bg: {sem["corrected_removed_bg"]};

  --grid-max-width: {grid["max_width"]};
  --grid-column-gap: {grid["column_gap"]};
  --rule-heavy-border: {grid["rule_heavy_weight"]} var(--rule-heavy);
  --rule-thin-border: {grid["rule_thin_weight"]} var(--rule-light);
}}

[data-theme="dark"] {{
  --bg-paper: {dark["bg_paper"]};
  --bg-elevated: {dark["bg_elevated"]};
  --ink-primary: {dark["ink_primary"]};
  --ink-secondary: {dark["ink_secondary"]};
  --ink-muted: {dark["ink_muted"]};
  --rule-heavy: {dark["rule_heavy"]};
  --rule-light: {dark["rule_light"]};
  --outside-tint: {dark["outside_tint"]};

  --verified-fg: {sem["verified_fg_dark"]};
  --verified-bg: {sem["verified_bg_dark"]};
  --corrected-removed-fg: {sem["corrected_removed_fg_dark"]};
  --corrected-removed-bg: {sem["corrected_removed_bg_dark"]};
}}
"""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(css, encoding="utf-8")
    except OSError:
        pass
    return css


if __name__ == "__main__":
    compile_tokens_css()
