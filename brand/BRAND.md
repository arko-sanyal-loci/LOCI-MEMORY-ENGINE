# Billo Tech brand

| File | Use |
|---|---|
| `billo-tech-logo-light.svg` | Wordmark for light backgrounds (default) |
| `billo-tech-logo-dark.svg` | Wordmark for dark backgrounds |
| `billo-tech-mark.svg` | Square mark: avatars, favicons, the GitHub organization picture |

## Design language

The mark is a rounded square with a stroked white **B** and a small amber dot: a fact heating up.
The gradient runs from indigo (memory, depth) to cyan (recall, clarity), the same two ends as
LOCI's cold and hot tiers.

| Token | Hex | Role |
|---|---|---|
| Indigo | `#4F46E5` | primary, gradient start, light-mode wordmark |
| Cyan | `#06B6D4` | accent, gradient end |
| Amber | `#F59E0B` | heat dot, highlights; only ever small |
| Amber light | `#FDE68A` | heat dot centre |
| White | `#FFFFFF` | strokes on the mark, dark-mode wordmark |

Type: **Inter** for words, **JetBrains Mono** for code and the tagline. Badges use
`style=flat-square` with the indigo and cyan values above.

## Rules

- Keep the mark square with its 56/256 corner radius. Do not recolour the B.
- Use the light wordmark on light backgrounds and the dark one on dark; on GitHub use a
  `<picture>` element so it follows the reader's theme.
- The amber dot is the only warm colour. Do not add others.
