#include "QueryRouter.h"
#include <regex>
#include <algorithm>
#include <cctype>

// Helper to determine if a query has analytical shape
bool QueryRouter::isOlapWorkload(const std::string& sql) const {
    if (sql.empty()) return false;

    std::string upperSql = sql;
    
    // BUG 12 FIX: Cast to unsigned char to prevent Undefined Behavior (UB) 
    // when processing non-ASCII bytes (e.g., Unicode table aliases).
    std::transform(upperSql.begin(), upperSql.end(), upperSql.begin(),
                   [](unsigned char c) { return std::toupper(c); });

    // BUG 11 & 13 FIX: Declare as static const to prevent re-compilation on every call,
    // reducing overhead from ~100us to ~100ns. Added \\s* to catch ORM-spaced keywords like "SUM (col)".
    static const std::regex olapPatterns("(GROUP BY|SUM\\s*\\(|AVG\\s*\\(|JOIN|PARTITION BY)");
    
    return std::regex_search(upperSql, olapPatterns);
}

// Calculates the heuristic compute weight of the query
double QueryRouter::calculateQueryCost(const std::string& sql, bool isOlap) const {
    if (sql.empty()) return 1.0;

    // BUG 14 FIX: Rebalanced the cost heuristic. 
    // OLAP operations now incur a massive base penalty (25.0) to guarantee 
    // warehouse routing, while string length impact is minimized to 0.01.
    if (isOlap) {
        return 25.0 + (sql.length() * 0.01);
    }
    
    // Standard OLTP row-lookup cost
    return 1.0 + (sql.length() * 0.01);
}

// Evaluates the SQL and routes to the appropriate execution engine
std::string QueryRouter::routeQuery(const std::string& sql) const {
    bool isOlap = isOlapWorkload(sql);
    double costWeight = calculateQueryCost(sql, isOlap);

    if (costWeight > 26.0) {
        return "SNOWFLAKE"; // Heavy columnar joins
    } else if (costWeight >= 25.0) {
        return "AWS_ATHENA"; // Standard aggregations
    } else {
        return "AMAZON_RDS"; // Lightweight transactional lookups
    }
}