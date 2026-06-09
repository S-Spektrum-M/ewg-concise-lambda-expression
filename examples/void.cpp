#include <iostream>

int main() {
    auto log_err = (auto &&e) => std::println(std::cerr, "{}", e); // Deduced void
    log_err("This is an error message."); // expected to be logged on stderr
    log_err("Another error occurred.");
}
