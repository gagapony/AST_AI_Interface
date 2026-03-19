/**
 * Simple test file without external dependencies
 */

int add(int a, int b) {
    return a + b;
}

int multiply(int x, int y) {
    return x * y;
}

int compute(int value) {
    int doubled = multiply(value, 2);
    return add(doubled, 10);
}

void test() {
    int result = compute(5);
}
