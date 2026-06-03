#include "QueryRouter.h"
#include <iostream>
#include <regex>
#include <algorithm>
#include <cctype>

QueryContext::QueryContext(std::string id, std::string sql) 
    : queryId(std::move(id)), rawSql(std::move(sql)), estimatedComputeCost(0.0), targetEngine(ExecutionEngine::AMAZON_RDS) {}

void QueryContext::printRoutingDecision() const {
    std::cout << "[Trace ID: " << queryId << "] Routing Decision\n";
    std::cout << "  -> SQL: " << rawSql << "\n";
    std::cout << "  -> Estimated Cost Weight: " << estimatedComputeCost << "\n";
    
    std::cout << "  -> Target Engine: ";
    switch (targetEngine) {
        case ExecutionEngine::AMAZON_RDS: std::cout << "Amazon RDS (OLTP)\n"; break;
        case ExecutionEngine::AWS_ATHENA: std::cout << "AWS Athena (Serverless OLAP)\n"; break;
        case ExecutionEngine::SNOWFLAKE:  std::cout << "Snowflake (Heavy OLAP)\n"; break;
    }
    std::cout << "--------------------------------------------------\n";
}

QueryRouter::QueryRouter() = default;

bool QueryRouter::isOlapWorkload(const std::string& sql) const {
    // Convert to uppercase for standard matching
    std::string upperSql = sql;
    std::transform(upperSql.begin(), upperSql.end(), upperSql.begin(), ::toupper);
    
    // Regular expressions to detect heavy analytical operations
    std::regex olapPatterns("(GROUP BY|SUM\\(|AVG\\(|JOIN|PARTITION BY)");
    return std::regex_search(upperSql, olapPatterns);
}

double QueryRouter::calculateHeuristicCost(const std::string& sql) const {
    double cost = 1.0; // Base cost for simple SELECT
    
    // Heuristic: More characters generally imply more complex conditions/joins
    cost += (sql.length() * 0.05);
    
    // Penalize heavily for analytical keywords
    if (isOlapWorkload(sql)) {
        cost *= 7.5; 
    }
    
    return cost;
}

std::unique_ptr<QueryContext> QueryRouter::analyzeAndRoute(const std::string& queryId, const std::string& sql) {
    // Modern C++ memory allocation (No raw 'new' keywords)
    auto context = std::make_unique<QueryContext>(queryId, sql);
    
    context->estimatedComputeCost = calculateHeuristicCost(sql);
    
    // Business Logic: Route based on compute cost threshold
    if (context->estimatedComputeCost < 10.0) {
        context->targetEngine = ExecutionEngine::AMAZON_RDS;
    } else if (context->estimatedComputeCost < 50.0) {
        context->targetEngine = ExecutionEngine::AWS_ATHENA;
    } else {
        context->targetEngine = ExecutionEngine::SNOWFLAKE;
    }
    
    return context;
}