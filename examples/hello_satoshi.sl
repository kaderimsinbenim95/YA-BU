// hello_satoshi.sl — First SatoshiLang Program
//
// Demonstrates basic language features:
//   - Function definitions
//   - Arithmetic expressions
//   - Let bindings
//   - If/else control flow
//   - Recursive function calls
//   - Blockchain-native types

// Simple addition function
fn add(a: u64, b: u64) -> u64 {
    return a + b;
}

// Fibonacci (recursive)
fn fibonacci(n: u64) -> u64 {
    if n <= 1 {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

// Compute the hash of a value
fn hash_data(value: str) -> str {
    return sha256(value);
}

// Main entry point
fn main() -> u64 {
    // Arithmetic
    let x = 10 + 5 * 2;      // 20
    let y = x / 4;            // 5
    let z = x - y;            // 15

    // Function call
    let sum = add(x, z);      // 35

    // Fibonacci
    let fib10 = fibonacci(10); // 55

    // Conditional
    let result = 0;
    if fib10 > 50 {
        result = sum + fib10;   // 90
    } else {
        result = sum;
    }

    // Log the result
    log("hello_satoshi", result);

    return result;
}
