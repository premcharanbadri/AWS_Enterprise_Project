#ifndef QUERY_ROUTER_H
#define QUERY_ROUTER_H

#include <string>

class QueryRouter {
public:
    QueryRouter() = default;
    ~QueryRouter() = default;

    // Evaluates the SQL and routes to the appropriate execution engine
    std::string routeQuery(const std::string& sql) const;

private:
    // Helper to determine if a query has analytical shape
    bool isOlapWorkload(const std::string& sql) const;
    
    // Calculates the heuristic compute weight of the query
    double calculateQueryCost(const std::string& sql, bool isOlap) const;
};

#endif // QUERY_ROUTER_H