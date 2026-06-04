#include "QueryRouter.h"
#include <iostream>
#include <cassert>

void runTestSuite() {
    QueryRouter router;
    
    std::cout << "Starting QueryRouter validation suite...\n";

    // Test 1: Standard OLTP (Expected: Amazon RDS)
    std::string q1 = "SELECT id, name FROM users WHERE id = 1";
    assert(router.routeQuery(q1) == "AMAZON_RDS");
    
    // Test 2: Standard OLAP (Expected: AWS Athena)
    std::string q2 = "SELECT SUM(revenue) FROM sales";
    assert(router.routeQuery(q2) == "AWS_ATHENA");
    
    // Test 3: Heavy OLAP with massive string length (Expected: Snowflake) Simulating a massive 200+ character generated ORM query
    std::string q3 = "SELECT SUM(revenue) FROM sales JOIN customers ON sales.customer_id = customers.id WHERE region = 'US-EAST' AND status = 'ACTIVE' AND category IN ('A', 'B', 'C', 'D', 'E') GROUP BY region ORDER BY revenue DESC";
    assert(router.routeQuery(q3) == "SNOWFLAKE");
    
    // Test 4: Space-before-parenthesis evasion attempt 
    std::string q4 = "SELECT SUM (revenue) FROM sales";
    assert(router.routeQuery(q4) == "AWS_ATHENA");
    
    // Test 5: Non-ASCII characters (UTF-8). 
    std::string q5 = "SELECT id FROM users WHERE last_name = 'René'";
    assert(router.routeQuery(q5) == "AMAZON_RDS");
    
    // Test 6: Empty string boundary condition
    assert(router.routeQuery("") == "AMAZON_RDS");

    std::cout << "[SUCCESS] All 6 test cases passed successfully.\n";
}

int main() {
    runTestSuite();
    return 0;
}