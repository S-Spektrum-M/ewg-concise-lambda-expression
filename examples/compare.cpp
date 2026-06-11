#include <algorithm>
#include <cmath>
#include <compare>
#include <print>
#include <utility>
#include <vector>

struct Point {
    int m_x;
    int m_y;
    constexpr auto operator<=>(const Point &P) const noexcept = default;
};

int main() {
    std::vector<Point> points = {{1, 2}, {3, 4}, {5, 6}};

    std::ranges::sort(points, (p1, p2) => p1 <=> p2 == decltype(p1 <=> p2)::less);
    std::println("Ascending Order:");
    for (const auto &[x, y] : points) {
        std::println("X: {}, Y: {}", x, y);
    }

    std::ranges::sort(points, (p1, p2) => p1 <=> p2 == decltype(p1 <=> p2)::greater);
    std::println("Descending Order:");
    for (const auto &[x, y] : points) {
        std::println("X: {}, Y: {}", x, y);
    }
    auto dist_origin = (p1) => std::sqrt(p1.m_x * p1.m_x + p1.m_y * p1.m_y);
    std::ranges::sort(points, (p1, p2) =>
                      std::sqrt(p1.m_x * p1.m_x + p1.m_y * p1.m_y) < std::sqrt(p1.m_x * p1.m_x + p1.m_y * p1.m_y)
      );
    std::println("Sorted by Distance from Origin:");
    for (const auto &[x, y] : points) {
        std::println("X: {}, Y: {}, Distance: {}", x, y, dist_origin(Point{x, y}));
    }
}
