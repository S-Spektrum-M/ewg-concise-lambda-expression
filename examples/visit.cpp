#include <iostream>
#include <variant>
#include <string>

template<class... Ts> struct overloaded : Ts... { using Ts::operator()...; };

void handle_int(int i) {
    std::cout << "int: " << i << '\n';
}

void handle_default(const auto& x) {
    std::cout << "default\n";
}

int main() {
    std::variant<int, std::string> v = 42;
    
    // With std::visit
    std::visit(overloaded{
        (int  i) => handle_int(i),
        (auto& x) => handle_default(x),
    }, v);
    
    v = "hello";
    std::visit(overloaded{
        (int  i) => handle_int(i),
        (auto& x) => handle_default(x),
    }, v);
    
    return 0;
}
