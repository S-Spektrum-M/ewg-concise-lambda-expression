#include <cstdio>
#include <map>
#include <string>
#include <print>

int main() {
    auto square    = (x) => x * x;              // [] (auto&& x) { return x * x; }
    auto add       = (x, y) => x + y;           // [] (auto&& x, auto &&y) {return x + y};
    auto identity  = (x) => x;                  // [] (auto &&x) -> auto {return x;}
                                                // returns a copy
    auto greet     = () => std::puts("hi");     // returns int (the result of puts)

    // Mixing inferred and explicit parameter forms
    auto clamp_pos = (int x) => x < 0 ? 0 : x;
    auto project_value = (const auto& db, y) => db.at(y);

    std::map<int, std::string> db = {{1, "one"}};

    auto print = (x) => std::println("{}", x);

    print(square(2));
    print(add(1, 2));
    print(identity(5));
    print(greet());
    print(clamp_pos(-5));
    print(project_value(db, 1));

    return 0;
}
