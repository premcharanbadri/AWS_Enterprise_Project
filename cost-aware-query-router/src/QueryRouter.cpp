#include "QueryRouter.h"
#include <regex>
#include <algorithm>
#include <cctype>
#include <iterator>

namespace {

// Counts non-overlapping matches of a pattern within text.
int countMatches(const std::string& text, const std::regex& pattern) {
    auto begin = std::sregex_iterator(text.begin(), text.end(), pattern);
    auto end = std::sregex_iterator();
    return static_cast<int>(std::distance(begin, end));
}

} // namespace

std::string QueryRouter::toUpper(const std::string& sql) {
    std::string upper = sql;
    // Cast to unsigned char to avoid undefined behavior on non-ASCII bytes
    // (e.g. UTF-8 table aliases) being passed to std::toupper.
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
    return upper;
}

bool QueryRouter::isOlapWorkload(const std::string& upperSql) const {
    if (upperSql.empty()) return false;

    // Static const so the (relatively expensive) regex compiles once. \s* tolerates
    // ORM-spaced keywords such as "SUM (col)" and "GROUP  BY".
    static const std::regex olapPatterns(
        R"((GROUP\s+BY|PARTITION\s+BY|JOIN|SUM\s*\(|AVG\s*\(|COUNT\s*\(|MIN\s*\(|MAX\s*\())");
    return std::regex_search(upperSql, olapPatterns);
}

double HeuristicCostModel::estimateCost(const std::string& upperSql, bool isOlap) const {
    if (upperSql.empty()) return 1.0;

    // Lightweight OLTP row-lookup baseline.
    if (!isOlap) {
        return 1.0;
    }

    static const std::regex joinPattern(R"(\bJOIN\b)");
    static const std::regex aggPattern(R"((SUM|AVG|COUNT|MIN|MAX)\s*\()");
    static const std::regex groupPattern(R"(GROUP\s+BY|PARTITION\s+BY)");

    // Analytical baseline plus a weight per heavy operator. Joins dominate cost,
    // grouping is moderate, scalar aggregations are cheapest. Driven by query
    // shape, not by character length.
    double cost = 25.0;
    cost += countMatches(upperSql, joinPattern) * 10.0;
    cost += countMatches(upperSql, groupPattern) * 3.0;
    cost += countMatches(upperSql, aggPattern) * 2.0;
    return cost;
}

std::string QueryRouter::routeQuery(const std::string& sql) const {
    const std::string upperSql = toUpper(sql);
    const bool isOlap = isOlapWorkload(upperSql);
    const double cost = costModel_->estimateCost(upperSql, isOlap);

    if (cost > 30.0) {
        return "SNOWFLAKE";   // Heavy columnar joins
    } else if (cost >= 25.0) {
        return "AWS_ATHENA";  // Standard aggregations
    }
    return "AMAZON_RDS";      // Lightweight transactional lookups
}

QueryRouter::QueryRouter() : costModel_(std::make_unique<HeuristicCostModel>()) {}

QueryRouter::QueryRouter(std::unique_ptr<ICostModel> costModel)
    : costModel_(std::move(costModel)) {}

QueryRouter::~QueryRouter() = default;
