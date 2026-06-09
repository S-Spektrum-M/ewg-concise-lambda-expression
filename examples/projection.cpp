#include <algorithm>
#include <print>
#include <ranges>
#include <string>
#include <vector>

struct Address {
    std::string street;
    int number;
    int zip;
};

struct Employee {
    std::string name;
    int id;
    Address address;
};

int main() {
    std::vector<Employee> employees = {
        {"Alice", 1, {"Main St", 123, 12345}},
        {"Bob", 2, {"Second St", 456, 67890}},
        {"Charlie", 3, {"Third St", 789, 13579}}};
    std::ranges::sort(employees, std::ranges::less{}, (e) => e.address.street);
    for (auto& employee : employees) {
        std::println("Employee: {}, Street: {}", employee.name, employee.address.street);
    }
}
