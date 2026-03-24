# Filter Fuzzy Match & Local ECharts Design

## 1. Requirements

### Requirement 1: Local ECharts
**Current:**
```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
```

**Desired:**
```html
<script src="./echarts.min.js"></script>
```

### Requirement 2: Fuzzy Match for --filter-func
**Current:**
```bash
./run.sh --filter-func "print_result::(const char *, int)"  # Must match exactly
```

**Desired:**
```bash
./run.sh --filter-func "print_result"  # Partial match accepted

# Should match:
# - "print_result::(const char *, int)"
# - "print_result::(int)"
# - "MyClass::print_result::(const char *)"
```

**Behavior on Multiple Matches:**
- If input matches 2+ functions: Print warning with list of matched functions
- If input matches 1 function: Use it directly
- If input matches 0 functions: Raise ValueError (existing behavior)

---

## 2. Design Analysis

### 2.1 ECharts Local File

**Strategy A: Bundle with package**
- Download echarts.min.js to package
- Copy to output directory during HTML generation
- Pros: Self-contained, no external dependency
- Cons: Increases package size (~1MB)

**Strategy B: Require user to provide**
- User must place echarts.min.js in output directory
- Pros: Smaller package
- Cons: Poor UX, breaks easily

**Recommendation: Strategy A (Bundle with package)**

**Implementation:**
```python
# File: src/file_graph_generator.py
import shutil

ECHARTS_SOURCE = Path(__file__).parent / 'echarts.min.js'

def write_html_file(html_content: str, output_path: str) -> None:
    """Write HTML file and copy echarts.min.js to output directory."""
    output_dir = Path(output_path).parent

    # Write HTML
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Copy echarts.min.js if it exists
    if ECHARTS_SOURCE.exists():
        dest = output_dir / 'echarts.min.js'
        if not dest.exists():
            shutil.copy(ECHARTS_SOURCE, dest)
            logging.info(f"Copied echarts.min.js to {dest}")
    else:
        logging.warning("echarts.min.js not found in package, using CDN")

    # Update HTML to use local file if copied
    if (output_dir / 'echarts.min.js').exists():
        html_content = html_content.replace(
            'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js',
            './echarts.min.js'
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
```

---

### 2.2 Fuzzy Match Algorithm

**Options:**

| Option | Match Logic | Pros | Cons |
|--------|-------------|------|------|
| **Starts with** | `qname.startswith(input)` | Simple, predictable | May miss matches |
| **Contains** | `input in qname` | Flexible | Too broad, false positives |
| **Fuzzy search** | Levenshtein distance, etc. | Powerful | Complex, overkill |

**Recommendation: Contains match (with prefix priority)**

**Algorithm:**
```python
def _find_matching_functions(self, input_name: str) -> List[Tuple[int, str]]:
    """
    Find functions matching input_name.

    Priority:
    1. Exact match on qualified_name (highest priority)
    2. qualified_name starts with input_name
    3. qualified_name contains input_name

    Returns:
        List of (index, qualified_name) tuples
    """
    matches = []
    input_lower = input_name.lower()

    # Pass 1: Exact match
    for func in self.functions:
        qname = func['self']['qualified_name']
        if qname == input_name:
            matches.append((func['index'], qname))

    if matches:
        return matches[:1]  # Return first exact match

    # Pass 2: Starts with
    for func in self.functions:
        qname = func['self']['qualified_name']
        if qname.startswith(input_name):
            matches.append((func['index'], qname))

    if matches:
        return matches

    # Pass 3: Contains
    for func in self.functions:
        qname = func['self']['qualified_name']
        if input_name in qname:
            matches.append((func['index'], qname))

    return matches
```

**Multiple Matches Warning:**
```python
def filter_by_function(self, target_name: str) -> List[Dict[str, Any]]:
    """Filter graph with fuzzy matching."""
    self.logger.info(f"Filtering graph by function (fuzzy): '{target_name}'")

    # Find matching functions
    matches = self._find_matching_functions(target_name)

    if not matches:
        raise ValueError(f"No function matching '{target_name}' found in graph")

    if len(matches) > 1:
        # Print warning with list of matches
        self.logger.warning(
            f"Multiple functions matching '{target_name}' found. "
            f"Using first match: {matches[0][1]}"
        )
        print(f"\nWARNING: {len(matches)} functions matching '{target_name}':")
        for idx, qname in matches:
            print(f"  - {qname}")
        print(f"\nUsing: {matches[0][1]}\n")

    # Use first match
    target_indices = [idx for idx, _ in matches]

    self.logger.info(f"Selected function: {matches[0][1]}")

    # Continue with path slice...
    upward_nodes = self._trace_upward(target_indices)
    # ...
```

---

## 3. Implementation Plan

### Step 1: ECharts Local File
1. Download echarts.min.js v5.4.3
2. Place in `./clang-call-analyzer/src/echarts.min.js`
3. Modify `file_graph_generator.py` to copy local file
4. Update HTML template to use local file if available

### Step 2: Fuzzy Match
1. Add `_find_matching_functions()` to `graph_filter.py`
2. Modify `filter_by_function()` to use fuzzy matching
3. Add warning for multiple matches
4. Update CLI help text to document fuzzy matching

---

## 4. Edge Cases & Considerations

### 4.1 ECharts File Missing
**Scenario:** echarts.min.js not in package directory

**Fallback:**
- Log warning
- Use CDN URL (existing behavior)
- HTML still works (requires internet)

### 4.2 Fuzzy Match Too Broad
**Scenario:** User types "get" matches 50+ functions

**Mitigation:**
- Only show first 10 matches in warning
- Suggest user to be more specific
- Use starts-with priority to reduce noise

### 4.3 Namespace Collision
**Scenario:**
```python
# Input: "init"
# Matches:
# - "init"
# - "MyClass::init"
# - "init_helper"
```

**Current approach:** Use starts-with priority, still picks first
**Alternative:** Interactive selection (too complex for CLI)

**Decision:** Use priority-based selection, document in help

---

## 5. Testing

### Test 1: Fuzzy Match
```bash
# Exact match (existing behavior)
./run.sh --filter-func "print_result::(const char *, int)"

# Partial match (new behavior)
./run.sh --filter-func "print_result"
# Should match: "print_result::(const char *, int)"

# Multiple matches
./run.sh --filter-func "print"
# Should show warning, pick first match
```

### Test 2: ECharts Local File
```bash
./run.sh --format html -o output
# Check: output/echarts.min.js exists
# Check: output/output.html uses ./echarts.min.js
```

---

## 6. Documentation Updates

### CLI Help Text
```python
parser.add_argument(
    '--filter-func',
    type=str,
    default=None,
    metavar='FUNCTION',
    help='Filter graph to show only functions reachable from FUNCTION. '
         'Supports fuzzy matching (contains, starts-with). '
         'Exact qualified_name is recommended for precision. '
         'Example: "print_result" matches "print_result::(const char *, int)". '
         'If multiple matches found, first match is used with a warning.'
)
```

### README
```markdown
### Function Filtering

The `--filter-func` option supports fuzzy matching:

```bash
# Exact match
./run.sh --filter-func "print_result::(const char *, int)"

# Fuzzy match (contains)
./run.sh --filter-func "print_result"  # Matches all functions containing "print_result"
```

If multiple functions match, a warning is displayed and the first match is used.
```

---

## 7. Summary

| Feature | Status | Priority |
|---------|--------|----------|
| ECharts local file | ✅ Designed | Medium |
| Fuzzy match - single | ✅ Designed | High |
| Fuzzy match - multiple warning | ✅ Designed | High |
| CLI help update | ⏸️ Pending | Low |
| README update | ⏸️ Pending | Low |

**Decision: Proceed with implementation**
