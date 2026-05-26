#include <print>
#include <type_traits>

int main() {
    auto add_one = (std::integral auto x) => x + 1;
    std::println("int: {}" ,std::is_invocable<decltype(add_one), int>::value);
    std::println("string: {}" ,std::is_invocable<decltype(add_one), std::string>::value);
}
