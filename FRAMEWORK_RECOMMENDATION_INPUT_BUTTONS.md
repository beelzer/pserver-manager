# Framework Recommendation: Input-Height Buttons

## Problem

When placing buttons next to input fields (QLineEdit, QComboBox, etc.), the default button sizes don't match the input field heights, creating visual misalignment.

**Current State:**
- Button default: `padding: 6px 8px` + `min-height: 16px` = ~28-32px total height
- QLineEdit: `padding: 6px 8px` = ~26-28px total height (varies with font)
- ButtonSize.SMALL: Fixed 28px height
- ButtonSize.MEDIUM: Fixed 36px height
- ButtonSize.LARGE: Fixed 44px height

**Current Workaround (in PServer Manager):**
```python
browse_btn = Button("Browse...", variant=ButtonVariant.SECONDARY)
browse_btn.setStyleSheet("padding: 6px 8px; min-height: 0px;")
```

This requires manual stylesheet overrides in every application that needs this pattern.

## Use Cases

This pattern appears in:
1. **File/Folder browsers** - Browse, Clear buttons next to path inputs
2. **Search fields** - Search, Clear buttons next to search inputs
3. **Form actions** - Add, Remove buttons next to list/combo inputs
4. **Inline editors** - Edit, Save, Cancel buttons next to editable fields

## Recommendation: Add to Framework

### Option 1: New ButtonSize.COMPACT (Recommended)

Add a new button size that matches input field heights:

```python
class ButtonSize(Enum):
    """Button size options."""
    COMPACT = "compact"  # Matches input field height
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
```

**Implementation in `buttons.py`:**
```python
def _apply_size(self) -> None:
    """Apply size styling."""
    self.setProperty("size", self._size.value)

    if self._size == ButtonSize.COMPACT:
        # Match input field height with minimal padding
        self.setStyleSheet("padding: 6px 8px; min-height: 0px;")
        self.setMinimumWidth(60)
    else:
        size_map = {
            ButtonSize.SMALL: (80, 28),
            ButtonSize.MEDIUM: (100, 36),
            ButtonSize.LARGE: (120, 44),
        }
        min_width, height = size_map[self._size]
        self.setMinimumWidth(min_width)
        self.setFixedHeight(height)

    self.style().unpolish(self)
    self.style().polish(self)
    self.update()
```

**Usage:**
```python
browse_btn = Button("Browse...",
                   variant=ButtonVariant.SECONDARY,
                   size=ButtonSize.COMPACT)
```

### Option 2: Add Helper Method

Add a convenience method to Button class:

```python
def match_input_height(self) -> None:
    """Make button height match QLineEdit inputs."""
    self.setStyleSheet("padding: 6px 8px; min-height: 0px;")
```

**Usage:**
```python
browse_btn = Button("Browse...", variant=ButtonVariant.SECONDARY)
browse_btn.match_input_height()
```

### Option 3: New InputRowButton Widget

Create a specialized button class for input rows:

```python
class InputRowButton(Button):
    """Button optimized for placement next to input fields."""

    def __init__(self, text: str = "", parent: QWidget | None = None, **kwargs):
        super().__init__(text, parent, size=ButtonSize.COMPACT, **kwargs)
```

## Analysis

### Pros of Adding to Framework:
1. ✅ **Common UI Pattern** - Buttons next to inputs are ubiquitous
2. ✅ **Consistency** - All apps using the framework get consistent behavior
3. ✅ **Cleaner App Code** - No manual stylesheet overrides needed
4. ✅ **Maintainability** - Single place to update if input heights change
5. ✅ **Discoverability** - Developers can find the solution in the API

### Cons:
1. ⚠️ **Framework Complexity** - Adds another size variant
2. ⚠️ **Edge Cases** - Different themes might have different input heights
3. ⚠️ **Not Universal** - Some designs want different button heights intentionally

## Recommendation

**✅ Implement Option 1: Add ButtonSize.COMPACT**

**Rationale:**
- Most aligned with existing API (ButtonSize enum)
- Clear, discoverable through IDE autocomplete
- Minimal code change to framework
- Solves 80% of use cases
- Apps can still override with custom styles if needed

**Documentation to Add:**
```python
class ButtonSize(Enum):
    """Button size options.

    COMPACT: Matches input field height, ideal for buttons next to QLineEdit/QComboBox
    SMALL: Small standalone button (28px height)
    MEDIUM: Default button size (36px height)
    LARGE: Large emphasis button (44px height)
    """
    COMPACT = "compact"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
```

## Migration Path

1. **Phase 1:** Add ButtonSize.COMPACT to framework
2. **Phase 2:** Update PServer Manager to use it
3. **Phase 3:** Document pattern in framework examples
4. **Phase 4:** Add to features showcase

## Impact Assessment

**PServer Manager Changes:**
```python
# Before (current workaround)
browse_btn = Button("Browse...", variant=ButtonVariant.SECONDARY)
browse_btn.setStyleSheet("padding: 6px 8px; min-height: 0px;")

# After (using framework)
browse_btn = Button("Browse...",
                   variant=ButtonVariant.SECONDARY,
                   size=ButtonSize.COMPACT)
```

**Lines of Code Reduction:** ~1 line per button instance (4 instances in WoW settings = 4 lines)

**Benefits Beyond Code Reduction:**
- Future-proof if input styling changes
- Consistent across all dialogs
- Clear intent in code
- No stylesheet magic strings

## Conclusion

This is a **framework-worthy pattern** that should be added. It's common enough to warrant framework support, simple enough to implement cleanly, and valuable enough to improve developer experience.

**Recommended Action:** Implement ButtonSize.COMPACT in qtframework and update PServer Manager to use it.
