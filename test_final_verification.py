#!/usr/bin/env python3
"""Final verification test for the template fix."""

import json
import sys
from string import Template

sys.path.insert(0, 'src')

from echarts_templates import HTML_TEMPLATE, CSS_TEMPLATE, APP_SCRIPT_TEMPLATE


def test_template_fix():
    """Test that the template fix works correctly."""
    print("="*70)
    print("FINAL VERIFICATION TEST")
    print("="*70)

    # Create test data
    test_data = {
        "nodes": [
            {
                "id": 0,
                "name": "main",
                "path": "/src/main.cpp",
                "line_range": [1, 10],
                "category": "Default"
            },
            {
                "id": 1,
                "name": "init",
                "path": "/src/init.cpp",
                "line_range": [1, 20],
                "category": "Default"
            }
        ],
        "edges": [
            {
                "source": 0,
                "target": 1,
                "lineStyle": {"width": 2, "color": "#999"}
            }
        ],
        "categories": [
            {"name": "Default", "itemStyle": {"color": "#7f7f7f"}}
        ]
    }

    data_json = json.dumps(test_data, ensure_ascii=False, indent=2)

    print(f"\n1. Template Validation")
    print("-" * 70)

    # Check HTML_TEMPLATE uses $ placeholders
    if '$css' in HTML_TEMPLATE and '$data' in HTML_TEMPLATE and '$app_script' in HTML_TEMPLATE:
        print("   ✅ HTML_TEMPLATE uses $placeholder syntax")
    else:
        print("   ❌ HTML_TEMPLATE does not use $placeholder syntax")
        return False

    # Check APP_SCRIPT_TEMPLATE has no escaped braces
    if '{{' not in APP_SCRIPT_TEMPLATE:
        print("   ✅ APP_SCRIPT_TEMPLATE has no double braces")
    else:
        print(f"   ❌ APP_SCRIPT_TEMPLATE has {APP_SCRIPT_TEMPLATE.count('{{')} double braces")
        return False

    print(f"\n2. Template Substitution")
    print("-" * 70)

    try:
        template = Template(HTML_TEMPLATE)
        html = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=APP_SCRIPT_TEMPLATE
        )
        print("   ✅ Template substitution succeeded")
    except KeyError as e:
        print(f"   ❌ KeyError: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
        return False

    print(f"\n3. HTML Validation")
    print("-" * 70)

    issues = []

    # Check structure
    if '<!DOCTYPE html>' in html and '</html>' in html:
        print("   ✅ HTML structure valid")
    else:
        issues.append("HTML structure invalid")

    # Check placeholders are replaced
    if '$css' not in html and '$data' not in html and '$app_script' not in html:
        print("   ✅ All placeholders replaced")
    else:
        issues.append("Some placeholders not replaced")

    # Check data is embedded
    if '"nodes": [' in html and '"edges": [' in html:
        print("   ✅ Graph data embedded")
    else:
        issues.append("Graph data not embedded")

    # Check JavaScript code
    js_checks = [
        ('let chart;', 'Chart variable'),
        ('function initGraph()', 'initGraph function'),
        ('echarts.init', 'ECharts init'),
        ('chart.setOption', 'setOption call'),
        ('document.addEventListener', 'Event listener'),
        ('tooltipFormatter', 'Tooltip formatter'),
    ]

    for code, desc in js_checks:
        if code in html:
            print(f"   ✅ {desc} present")
        else:
            issues.append(f"{desc} missing")

    print(f"\n4. JavaScript Syntax Validation")
    print("-" * 70)

    # Check for malformed braces
    if '{{{' not in html:
        print("   ✅ No triple braces")
    else:
        issues.append(f"Found {html.count('{{{')} triple braces - will break JS")

    if '{{{{' not in html:
        print("   ✅ No quad braces")
    else:
        issues.append(f"Found {html.count('{{{{')} quad braces - will break JS")

    # Check function syntax
    if 'function initGraph() {' in html:
        print("   ✅ Function syntax correct")
    else:
        issues.append("Function syntax incorrect")

    # Check object syntax
    if 'const option = {' in html:
        print("   ✅ Object syntax correct")
    else:
        issues.append("Object syntax incorrect")

    # Check ES6 template strings
    if '${data.name}' in html or '${' in html:
        print("   ✅ ES6 template strings preserved")
    else:
        print("   ⚠️  Warning: ES6 template strings not found")

    print(f"\n5. Writing Output")
    print("-" * 70)

    output_file = 'final_verification.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   ✅ Written to {output_file}")

    # File stats
    size_kb = len(html) / 1024
    line_count = html.count('\n')
    print(f"   Size: {size_kb:.1f} KB, Lines: {line_count}")

    print(f"\n" + "="*70)
    if issues:
        print("❌ TEST FAILED")
        print("="*70)
        print("\nIssues:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        return False
    else:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n🎉 The template fix is working perfectly!")
        print(f"\n📄 Open {output_file} in your browser to view the ECharts graph.")
        print("\n📝 Summary of fixes:")
        print("   • Changed from str.format() to string.Template")
        print("   • Updated HTML_TEMPLATE to use $placeholder syntax")
        print("   • Removed unnecessary brace escaping from APP_SCRIPT_TEMPLATE")
        print("   • All JavaScript code now has correct syntax")
        print("   • ECharts templates and ES6 template strings preserved")
        return True


if __name__ == '__main__':
    success = test_template_fix()
    sys.exit(0 if success else 1)
