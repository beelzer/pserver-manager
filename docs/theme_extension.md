# Theme Extension Guide

The qtframework theme system is fully extensible, allowing you to add custom token categories for app-specific needs without modifying the framework itself.

## Adding Custom Tokens

### In Your Theme YAML

Simply add new top-level token categories under the `tokens` section. Any category not recognized by the framework (primitive, semantic, components, etc.) will be preserved as custom tokens.

**Example: Adding Ping Colors**

```yaml
name: my_theme
display_name: My Theme
# ... other theme metadata ...

tokens:
  # Standard framework tokens
  primitive:
    primary_500: "#2196F3"
    # ... etc ...

  semantic:
    bg_primary: "#FFFFFF"
    # ... etc ...

  # Custom app-specific tokens
  ping:
    excellent: "#00FF00"  # < 50ms
    good: "#FFFF00"       # 50-100ms
    poor: "#FF0000"       # > 300ms
    offline: "#808080"

  # Another custom category
  server_status:
    online: "#00FF00"
    offline: "#FF0000"
    starting: "#FFA500"
```

## Accessing Custom Tokens

### Option 1: Using `resolve_token()`

Works for both standard and custom tokens:

```python
from qtframework.themes.theme import Theme

theme = Theme.from_yaml("my_theme.yaml")

# Access custom tokens just like standard tokens
ping_color = theme.tokens.resolve_token("ping.excellent")
status_color = theme.tokens.resolve_token("server_status.online")
```

### Option 2: Using `get_custom()` (Recommended for Custom Tokens)

Provides a convenient way to access custom tokens with default values:

```python
# Get custom token with default fallback
ping_color = theme.tokens.get_custom("ping.excellent", "#00FF00")

# Access nested custom tokens
status_color = theme.tokens.get_custom("server_status.online", "#FFFFFF")

# Non-existent token returns default
unknown = theme.tokens.get_custom("ping.unknown", "#FFFFFF")
```

### Option 3: Direct Dictionary Access

For programmatic access to all custom tokens:

```python
# Get all custom token categories
custom_categories = theme.tokens.custom.keys()

# Access custom token dict directly
ping_tokens = theme.tokens.custom["ping"]
excellent_color = ping_tokens["excellent"]
```

## Use Cases

### Server Manager Example

```python
# In your server manager UI code
def get_ping_color(ping_ms: int) -> str:
    """Get color based on ping latency."""
    theme = self.theme_manager.current_theme

    if ping_ms < 0:
        return theme.tokens.get_custom("ping.offline", "#808080")
    elif ping_ms < 50:
        return theme.tokens.get_custom("ping.excellent", "#00FF00")
    elif ping_ms < 100:
        return theme.tokens.get_custom("ping.good", "#FFFF00")
    else:
        return theme.tokens.get_custom("ping.poor", "#FF0000")

def get_status_color(status: str) -> str:
    """Get color based on server status."""
    theme = self.theme_manager.current_theme
    return theme.tokens.get_custom(f"server_status.{status}", "#808080")
```

### Game-Specific Colors

```yaml
tokens:
  # WoW class colors
  class_colors:
    warrior: "#C79C6E"
    paladin: "#F58CBA"
    hunter: "#ABD473"
    rogue: "#FFF569"
    priest: "#FFFFFF"
    death_knight: "#C41F3B"
    shaman: "#0070DE"
    mage: "#40C7EB"
    warlock: "#8787ED"
    druid: "#FF7D0A"

  # OSRS skill colors
  skill_colors:
    combat: "#FF0000"
    gathering: "#00FF00"
    artisan: "#0000FF"
    support: "#FFFF00"
```

## Persistence

Custom tokens are automatically:
- ✅ Loaded from YAML themes
- ✅ Preserved when themes are saved
- ✅ Included in theme exports
- ✅ Available through all theme access methods

## Best Practices

1. **Use Descriptive Category Names**: Use clear names like `ping`, `server_status`, `class_colors`
2. **Document Custom Tokens**: Add comments in your YAML explaining what each custom token is for
3. **Provide Defaults**: Always use `get_custom()` with sensible defaults for robustness
4. **Keep Framework Clean**: Don't add app-specific tokens to qtframework - keep them in your app themes
5. **Theme Consistency**: If you add custom tokens, add them to all your themes for consistency

## Example Implementation

See `pserver_manager/themes/wow.yaml` for a complete example with ping colors and server status tokens.

## Framework Compatibility

Custom tokens are completely forward and backward compatible:
- Older versions of qtframework will ignore unknown token categories (no errors)
- Newer versions preserve all custom tokens
- Themes without custom tokens work normally
- No framework modifications required
