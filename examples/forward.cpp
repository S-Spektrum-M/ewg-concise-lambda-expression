#include <iostream>
#include <print>
#include <utility>

void f(auto &&x) {
    if constexpr (std::is_rvalue_reference_v<decltype(x)>) {
        std::println("\t\trvalue: {}", x);
    } else {
        std::println("\t\tlvalue: {}", x);
    }
}

int main() {
    auto forwarding = [](auto &&x) {
        f(std::forward<decltype(x)>(x));
    };
    auto forwarding_new = (x) => f(std::forward<decltype(x)>(x));

    auto no_forwarding = [](auto &&x) {
        f(x);
    };
    auto no_forwarding_new = (x) => f(x);

    int y = 10;
    std::println("Forwarding:");
    std::println("\tLambdas:");
    forwarding(y);  // lvalue
    forwarding(42); // rvalue
    std::println("\tConcise Lambdas:");
    forwarding_new(y);  // lvalue
    forwarding_new(42); // rvalue
    std::println("No Forwarding:");
    std::println("\tLambdas:");
    no_forwarding(y);  // lvalue
    no_forwarding(42); // rvalue
    std::println("\tConcise Lambdas:");
    no_forwarding_new(y);  // lvalue
    no_forwarding_new(42); // rvalue
}
