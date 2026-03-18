/**
 * @brief Sample C++ file for testing clang-call-analyzer
 */

#include <iostream>

/**
 * @brief A simple helper function
 * @param x Input value
 * @return x * 2
 */
int helper(int x) {
    return x * 2;
}

/**
 * @brief Main processing function
 * @param value Input value to process
 * @return Processed value
 */
int process(int value) {
    int result = helper(value);
    return result + 1;
}

/**
 * @brief Another helper function
 * @param a First value
 * @param b Second value
 * @return a + b
 */
int add(int a, int b) {
    return a + b;
}

/**
 * @brief Function that calls multiple others
 */
int compute(int x, int y) {
    int p = process(x);
    int s = add(p, y);
    return helper(s);
}

/// @brief Function without full doxygen style
int simple() {
    return 42;
}

/**
 * @brief Test function
 */
void test() {
    int a = compute(5, 3);
    int b = simple();
    std::cout << a << " " << b << std::endl;
}

/**
 * @brief Entry point
 */
int main() {
    test();
    return 0;
}
