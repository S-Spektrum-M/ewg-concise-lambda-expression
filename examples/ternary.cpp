#include <cstdio>
#include <print>
#include <string_view>
#include <vector>

enum class NodeStatus { Success, TransientFailure, CriticalFailure };

struct BuildNode {
    std::string_view name;
    NodeStatus status;
    int retry_count;
};

int main() {
    std::vector<BuildNode> cluster = {
        {"CAST_Transformer", NodeStatus::Success, 0},
        {"COLD_Linker", NodeStatus::TransientFailure, 2},
        {"CRAB_ArtifactRegistry", NodeStatus::CriticalFailure, 0},
        {"COB_Builder", NodeStatus::TransientFailure, 5}};

    // Multi-stage nested ternary mapping entirely inside a concise lambda.
    // Deduces node as BuildNode&& or BuildNode& seamlessly.
    auto triage_node = (node) =>
        node.status == NodeStatus::Success ?
            "STABLE" :
        node.status == NodeStatus::TransientFailure ?
            (node.retry_count > 3 ? "EXHAUSTED_RETRY" : "PENDING_RETRY") :
        "IMMEDIATE_ATTENTION";

    // Print the declarative evaluations
    for (const auto &node : cluster) {
        std::println(
            "Node: {:<22} -> Triage: {}", node.name, triage_node(node));
    }

    return 0;
}
