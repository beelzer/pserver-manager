# Icons Guide

## Directory Structure

```
icons/
├── games/          # Game icons (e.g., wow.png, runescape.png)
└── versions/       # Version/expansion icons (e.g., wow-vanilla.png, wow-wotlk.png)
```

## WoW Expansion Icons

Download these from Warcraft Wiki:

### Vanilla
- URL: https://warcraft.wiki.gg/images/Wow_icon.png
- Save as: `versions/wow-vanilla.png`

### The Burning Crusade
- URL: https://warcraft.wiki.gg/images/Bc_icon.png
- Save as: `versions/wow-tbc.png`

### Wrath of the Lich King
- URL: https://warcraft.wiki.gg/images/Wrath-Logo-Small.png
- Save as: `versions/wow-wotlk.png`

### Cataclysm
- URL: https://warcraft.wiki.gg/images/Cata-Logo-Small.png
- Save as: `versions/wow-cataclysm.png`

### Mists of Pandaria
- URL: https://warcraft.wiki.gg/images/Mists-Logo-Small.png
- Save as: `versions/wow-mop.png`

### Warlords of Draenor
- URL: https://warcraft.wiki.gg/images/Warlords-Logo-Small.png
- Save as: `versions/wow-wod.png`

### Legion
- URL: https://warcraft.wiki.gg/images/Legion-Logo-Small.png
- Save as: `versions/wow-legion.png`

### Battle for Azeroth
- URL: https://warcraft.wiki.gg/images/Battle_for_Azeroth-Logo-Small.png
- Save as: `versions/wow-bfa.png`

## Game Icons

### World of Warcraft
- URL: https://warcraft.wiki.gg/images/Wow_icon.png
- Save as: `games/wow.png`

### RuneScape
- Search for official RuneScape logo/icon
- Save as: `games/runescape.png`

### Mu Online
- Search for official Mu Online logo/icon
- Save as: `games/mu-online.png`

### Flyff
- Search for official Flyff logo/icon
- Save as: `games/flyff.png`

## Usage in YAML

```yaml
# Game icon
icon: "games/wow.png"

# Version icon
versions:
  - id: vanilla
    name: "Vanilla (1.12)"
    icon: "versions/wow-vanilla.png"
```
