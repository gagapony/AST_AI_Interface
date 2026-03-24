# Filter Exact Match Design

## Requirements

### Matching Strategy (Strict Two-Tier)

User wants exact matching only, not fuzzy matching.

**Two-tier priority:**
1. **Tier 1**: Exact match on `qualified_name` (highest priority)
2. **Tier 2**: Exact match on `name` (fallback only if Tier 1 fails)

**No fuzzy matching:**
- ❌ No starts-with matching
- ❌ No contains matching
- ✅ Only exact match

---

## Algorithm

### _find_matching_functions()

```python
def _find_matching_functions(self, input_name: str) -> List[Tuple[int, str]]:
    """
    Find functions matching input_name with strict two-tier matching.

    Priority:
    1. Exact match on qualified_name (highest priority)
    2. Exact match on name (fallback if qualified_name not found)

    Returns at most one match.
    """
    # Tier 1: Exact match on qualified_name
    for func in self.functions:
        qname = func['self']['qualified_name']
        if qname == input_name:
            return [(func['index'], qname)]

    # Tier 2: Exact match on name (fallback)
    for func in self.functions:
        name = func['self']['name']
        if name == input_name:
            return [(func['index'], func['self']['qualified_name'])]

    # No match found
    return []
```

---

## Examples

### Example 1: Match qualified_name (Tier 1)

**Function in graph:**
```json
{
  "name": "print_result",
  "qualified_name": "print_result::(const char *, int)"
}
```

**User input:**
```bash
--filter-func "print_result::(const char *, int)"
```

**Result:**
- ✅ Matches qualified_name exactly
- Returns: `[index, "print_result::(const char *, int)"]`

---

### Example 2: Match name (Tier 2 fallback)

**Function in graph:**
```json
{
  "name": "print_result",
  "qualified_name": "print_result::(const char *, int)"
}
```

**User input:**
```bash
--filter-func "print_result"
```

**Process:**
1. Tier 1: Check `qualified_name == "print_result"` → ❌ No match
2. Tier 2: Check `name == "print_result"` → ✅ Match!

**Result:**
- ✅ Matches name exactly (fallback)
- Returns: `[index, "print_result::(const char *, int)"]`

---

### Example 3: No match

**Function in graph:**
```json
{
  "name": "print_result",
  "qualified_name": "print_result::(const char *, int)"
}
```

**User input:**
```bash
--filter-func "print"
```

**Process:**
1. Tier 1: Check `qualified_name == "print"` → ❌ No match
2. Tier 2: Check `name == "print"` → ❌ No match

**Result:**
- ❌ No match found
- Raises: `ValueError("Function 'print' not found in graph")`

---

### Example 4: Overloaded functions

**Functions in graph:**
```json
[
  {
    "name": "print_result",
    "qualified_name": "print_result::(const char *, int)"
  },
  {
    "name": "print_result",
    "qualified_name": "print_result::(int)"
  },
  {
    "name": "print_result",
    "qualified_name": "print_result::(float)"
  }
]
```

**User input:**
```bash
--filter-func "print_result"
```

**Process:**
1. Tier 1: Check all `qualified_name == "print_result"` → ❌ No match
2. Tier 2: Check `name == "print_result"`
   - Matches multiple functions!
   - Returns the **first match** found

**Result:**
- ⚠️ Returns first match (unspecified which one)
- Could be any of the three overloaded functions

**Note:** This is a limitation of strict matching. For overloaded functions,
user should use the full `qualified_name` to be specific.

---

## Advantages

| Aspect | Strict Matching | Fuzzy Matching |
|--------|----------------|----------------|
| Precision | ✅ High | ❌ Low |
| Predictability | ✅ High | ⚠️ Medium |
| False positives | ✅ None | ⚠️ Possible |
| Ease of use | ⚠️ Medium | ✅ High |

---

## Edge Cases

### Case 1: Namespace-qualified name

**Function in graph:**
```json
{
  "name": "print",
  "qualified_name": "MyClass::print::(const char *)"
}
```

**User input:**
```bash
--filter-func "MyClass::print::(const char *)"
```

**Result:**
- ✅ Matches qualified_name exactly

---

### Case 2: Template function

**Function in graph:**
```json
{
  "name": "process",
  "qualified_name": "process<int>(int)"
}
```

**User input:**
```bash
--filter-func "process"
```

**Result:**
- ✅ Matches name exactly

---

### Case 3: Constructor/Destructor

**Function in graph:**
```json
{
  "name": "~MyClass",
  "qualified_name": "MyClass::~MyClass()"
}
```

**User input:**
```bash
--filter-func "~MyClass"
```

**Result:**
- ✅ Matches name exactly

---

## Documentation

### CLI Help Text
```
--filter-func FUNCTION
    Filter graph to show only functions reachable from FUNCTION.
    Supports exact match on qualified_name or name.
    Priority: qualified_name > name.
    Example: "print_result" matches name="print_result" or
             qualified_name="print_result::(const char *, int)".
    Generates filegraph_<FUNCTION>.json and .html.
```

### User Guide
```
To filter by a specific function, use --filter-func:

# Exact match on qualified_name (most precise)
./run.sh --filter-func "print_result::(const char *, int)"

# Exact match on name (easier to type)
./run.sh --filter-func "print_result"

# Namespace-qualified
./run.sh --filter-func "MyClass::process::(int)"

# Note: Use qualified_name for overloaded functions
./run.sh --filter-func "print_result::(const char *, int)"
```

---

## Summary

**Design Decision:**
- Strict exact matching only (two-tier priority)
- No fuzzy matching to avoid false positives
- User must be explicit with `qualified_name` for overloaded functions

**Implementation:**
- ✅ `_find_matching_functions()` with two-tier logic
- ✅ Removes multi-match warnings (unnecessary with strict matching)
- ✅ Updated CLI help text
