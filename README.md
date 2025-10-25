# TF2 HUD Normalizer

Converts TF2 HUDs to work on both Windows and Linux.

## Usage

```bash
python3 hud_normalizer.py <HUD_FOLDER>
```

## What it does

- Lowercases all files/folders
- Normalizes font paths in clientscheme files
- Converts paths to explicit format
- Fixes cfg depth-based `../` paths

The HUD *should* work identically on both platforms after running.

I will add font sizing as an argument sometime later for all the GNOMEheads out there.
