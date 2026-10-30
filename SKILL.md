---
name: animated-email-signature
description: Make an animated email signature, a looping GIF card under your name, from a few inputs (name, title, company, website, colours, a few short lines, an optional logo). Produces the GIF, a still first frame and the HTML to paste into Gmail, then walks through hosting the GIF and setting it in Gmail. Use when someone asks for an animated, GIF or moving email signature, or wants to change one made with this skill.
---

# Animated email signature

This skill turns a short JSON config into:

- `signature.gif`: a 520x196 card (1040x392 pixels, sharp on retina screens) that loops through 2 to 4 slides
- `signature-static.png`: the first frame, for places that don't play GIFs
- `signature.html`: the name, a title line and the linked GIF, ready to paste into Gmail
- `preview.html`: the signature under a sample email, in light and dark

The script is `scripts/make_signature.py` in this skill's folder. The card's layout is `template/card.html`.

## 1. Check the tools

Run these and install whatever is missing (ask the user before installing anything):

- `python3 --version` (3.9 or newer)
- `python3 -c "import playwright"`. If it fails: `pip install playwright`, then `python3 -m playwright install chromium`
- `ffmpeg -version` and `gifsicle --version`. macOS: `brew install ffmpeg gifsicle`. Ubuntu: `sudo apt install ffmpeg gifsicle`

## 2. Ask for the inputs

Ask in one message:

1. Name, job title and company
2. Website (the card links to it)
3. Two colours: the card's background (a dark colour works best) and an accent
4. A short label and a headline for the card's right side, such as "Bookkeeping" and "Bookkeeping for small businesses."
5. Two to four short lines, one per slide. The last one plays first, so it should be the line that matters most (an offer, a guarantee, what to do next)
6. A logo, optional: a square SVG or PNG

Don't ask for anything else. Use the defaults in the config reference below.

## 3. Write the config

Make a folder `email-signature/` in the current directory, copy the logo into it, and write `email-signature/signature.json`. Start from `examples/simple/signature.json` in this skill's folder.

- Plain sentences go in `lines`. Put the user's last line last.
- `*word*` shows a word in the accent colour, and `\n` starts a new line. Break lines by hand so each slide has 2 or 3 lines of about 18 characters.
- If a line describes something happening on a screen, use `slides` instead of `lines` and pick a slide type:
  - someone typing into an app (a search, a chat prompt): `typing`
  - an answer or a list of results: `list`, with up to 3 short items and an optional `overlay` question shown over the list
  - a screenshot or photo the user gives you: `image`
  - anything else: `statement`
  `examples/rosefall/signature.json` uses typing, list (with an overlay) and statement.
- The headline fits 2 lines of about 22 characters. The company name fits about 16 characters.

## 4. Make it

```
python3 <this skill's folder>/scripts/make_signature.py email-signature/signature.json
```

It prints the GIF's size and length. For each `warning:` line, shorten that text and run again. Open `email-signature/output/signature.gif` and `preview.html` for the user and ask what to change. Keep the GIF under 1 MB.

## 5. Put the GIF online

Gmail loads signature images from a link, so `signature.gif` needs a public https address. Ask the user where they will put it (their website is best). Don't upload it anywhere without their go. When they give the link, check it:

```
curl -sI <link>
```

It must answer 200 with `content-type: image/gif`. Then write the HTML with the link:

```
python3 <this skill's folder>/scripts/make_signature.py email-signature/signature.json --gif-url <link> --html-only
```

## 6. Set it in Gmail

Give the user these steps:

1. Open `email-signature/output/signature.html` in Chrome.
2. Select all (Cmd+A on a Mac, Ctrl+A on Windows) and copy.
3. In Gmail, click the gear, then See all settings. On the General tab, scroll to Signature.
4. Click Create new, give it a name, and paste into the box.
5. Under Signature defaults, choose it for new emails and for replies and forwards.
6. Click Save Changes at the bottom of the page.

## 7. Check it

Ask the user to send an email to themselves and open it on their phone in the Gmail app, in light and dark mode. The card should animate and open their website when tapped.

## Config reference

| Field | Required | What it does |
|---|---|---|
| `name` | yes | Shown above the card, in the HTML |
| `company` | yes | In the title line and the card's footer |
| `title` | no | Shown before the company in the title line |
| `link` | no | Where the card links to |
| `lines` | `lines` or `slides` | One `statement` slide per line |
| `slides` | `lines` or `slides` | Slides with types (below) |
| `colors` | no | `background` and `accent`. Every other colour is worked out from these, and any can be set by hand (see the Rosefall example) |
| `label`, `headline` | no | The card's right side |
| `label_icon` | no | `search`, `check`, `spark`, `mail`, `none`, or a path to a small image |
| `logo` | no | Shown in the footer and on statement slides |
| `statement_logo` | no | A different logo for statement slides |
| `alt` | no | Text for the image, for screen readers and blocked images |
| `start_with_last` | no | `true` by default: the loop opens on the last slide |
| `gif_url` | no | The GIF's public link, same as `--gif-url` |

Slide fields: every slide takes `seconds`. `statement` takes `text` and `big`. `typing` takes `app`, `greeting` and `text`. `list` takes `app`, `question`, `lead`, `items`, `overlay` and `overlay_seconds`. `image` takes `src` and `caption`.
