#include <cstdio>
#include <map>
#include <string>
#include <print>
#include <unordered_map>

int main() {
    // ucs in founding order
    std::unordered_map<int, std::string> pets_registry = {
        {100, "Dog"},
        {101, "Cat"},
        {102, "Hamster"},
        {103, "Parrot"},
    };


    // demonstrates the use of:
    //  - the comma operator to perform side effects (incrementing the counter)
    //  - auto && + int & -> int & semantics to allow mutation of the counter variable from within the lambda for stateful expressions
    auto log_and_format = (const auto& db, id, counter) => (
        counter++,
        std::format("[Invocation: {}] [ID: {}] -> Name: {}", counter, id, db.at(id))
    );

    int mutations = 0;
    std::println("{}", log_and_format(pets_registry, 101, mutations));
    std::println("{}", log_and_format(pets_registry, 103, mutations));
    std::println("Total Lambda Invocations: {}", mutations);

    return 0;
}
