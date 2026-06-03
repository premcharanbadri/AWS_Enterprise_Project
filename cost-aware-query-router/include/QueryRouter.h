#ifndef QUERY_ROUTER_H
#define QUERY_ROUTER_H

#include <string>
#include <memory>

// Explicit routing destinations
enum class ExecutionEngine {
    AMAZON_RDS,      // Fast, low-latency OLTP (PostgreSQL)
    AWS_ATHENA,      // Serverless, S3-based OLAP
    SNOWFLAKE        // Heavy, high-performance columnar OLAP
};

class QueryContext {
public:
    std::string queryId;
    std::string rawSql;
    double estimatedComputeCost;
    ExecutionEngine targetEngine;

    QueryContext(std::string id, std::string sql);
    void printRoutingDecision() const;
};

class QueryRouter {
public:
    QueryRouter();
    
    // Uses modern C++ smart pointers to prevent memory leaks
    std::unique_ptr<QueryContext> analyzeAndRoute(const std::string& queryId, const std::string& sql);

private:
    bool isOlapWorkload(const std::string& sql) const;
    double calculateHeuristicCost(const std::string& sql) const;
};

#endif // QUERY_ROUTER_H