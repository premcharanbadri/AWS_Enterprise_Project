#include "QueryRouter.h"
#include <iostream>
#include <vector>

int main() {
    std::cout << "=== AWS Federated Query Router Initialized ===\n\n";
    
    QueryRouter router;
    
    // Simulate a stream of incoming queries from various microservices
    std::vector<std::string> incomingQueries = {
        "SELECT first_name, last_name FROM users WHERE user_id = 99281",
        "SELECT region, SUM(revenue) FROM daily_sales GROUP BY region",
        "SELECT c.name, AVG(o.total) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name HAVING AVG(o.total) > 10000"
    };
    
    int traceCounter = 1000;
    
    for (const auto& sql : incomingQueries) {
        std::string traceId = "REQ-" + std::to_string(traceCounter++);
        
        // Execute the routing algorithm
        auto context = router.analyzeAndRoute(traceId, sql);
        
        // Display the result
        context->printRoutingDecision();
    }
    
    return 0;
}