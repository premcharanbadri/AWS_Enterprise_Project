#ifndef QUERY_ROUTER_H
#define QUERY_ROUTER_H

#include <string>
#include <memory>

// Strategy interface for pluggable query-cost estimation models.
class ICostModel {
public:
    virtual ~ICostModel() = default;

    // Returns a heuristic compute weight for an already-uppercased SQL string.
    virtual double estimateCost(const std::string& upperSql, bool isOlap) const = 0;
};

// Default cost model: weights the number and type of analytical operators (joins, aggregations, grouping) rather than the raw length of the query.
class HeuristicCostModel : public ICostModel {
public:
    double estimateCost(const std::string& upperSql, bool isOlap) const override;
};

class QueryRouter {
public:
    // Uses the default heuristic cost model.
    QueryRouter();

    // Strategy injection point: swap in an alternative cost model.
    explicit QueryRouter(std::unique_ptr<ICostModel> costModel);

    ~QueryRouter();

    // Evaluates the SQL and routes to the appropriate execution engine.
    std::string routeQuery(const std::string& sql) const;

private:
    bool isOlapWorkload(const std::string& upperSql) const;
    static std::string toUpper(const std::string& sql);

    std::unique_ptr<ICostModel> costModel_;
};

#endif
