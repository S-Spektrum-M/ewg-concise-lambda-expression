#include <iostream>
#include <vector>
#include <string>
#include <algorithm>

struct Employee {
    std::string name;
    int hire_date;
};

int main() {
    std::vector<Employee> employees = {{"Alice", 2010}, {"Bob", 2005}, {"Charlie", 2015}};

    // As a projection / comparator
    std::ranges::sort(employees, std::less{}, (e) => e.hire_date);

    for (const auto& e : employees) {
        std::cout << e.name << " " << e.hire_date << '\n';
    }
    return 0;
}
