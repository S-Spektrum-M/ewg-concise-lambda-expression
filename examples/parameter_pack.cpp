#include <print>

int main() {
    auto print_hello = (auto... xs) => std::println("Hello, {} from {}!", xs...);
    print_hello("world", "Siddharth");
}
