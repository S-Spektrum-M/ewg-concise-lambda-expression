#include <iostream>
#include <vector>
#include <string>
#include <ranges>

struct Person {
    std::string name;
    int age;
};

int main() {
    std::vector<Person> people = {{"Alice", 20}, {"Bob", 15}, {"Charlie", 25}};
    namespace views = std::views;
    
    // In a pipeline
    auto names = people
               | views::filter((p) => p.age >= 18)
               | views::transform((p) => p.name);
               
    for (const auto& name : names) {
        std::cout << name << '\n';
    }
    return 0;
}
