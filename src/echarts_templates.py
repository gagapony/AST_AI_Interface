"""CSS template for ECharts visualization."""

CSS_TEMPLATE = """
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  overflow: hidden;
}

#controls {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #f5f5f5;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

#search-input {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  width: 300px;
  font-size: 14px;
}

#match-count {
  font-size: 12px;
  color: #666;
}

.toolbar {
  display: flex;
  gap: 10px;
}

select, button {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

button:hover {
  background: #e0e0e0;
}

#graph-container {
  position: absolute;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
}

/* Dark theme */
body.dark-theme {
  background: #1a1a1a;
}

body.dark-theme #controls {
  background: #2a2a2a;
  border-bottom: 1px solid #444;
}

body.dark-theme #search-input,
body.dark-theme select,
body.dark-theme button {
  background: #333;
  border-color: #555;
  color: #fff;
}

body.dark-theme button:hover {
  background: #444;
}

body.dark-theme #match-count {
  color: #aaa;
}

/* Light theme */
body.light-theme {
  background: #fafafa;
}

body.light-theme #controls {
  background: #ffffff;
  border-bottom: 1px solid #e0e0e0;
}
"""
