import os
import logging

logger = logging.getLogger(__name__)

# Analytical query run against Snowflake's built-in TPC-H sample data.
# It totals revenue by customer market segment, which is the kind of
# large aggregation that belongs on a columnar warehouse rather than a
# transactional database.
REVENUE_BY_SEGMENT_QUERY = """
    SELECT
        customer.c_mktsegment        AS market_segment,
        SUM(orders.o_totalprice)     AS total_revenue,
        COUNT(*)                     AS order_count
    FROM snowflake_sample_data.tpch_sf1.orders   AS orders
    JOIN snowflake_sample_data.tpch_sf1.customer AS customer
        ON orders.o_custkey = customer.c_custkey
    GROUP BY customer.c_mktsegment
    ORDER BY total_revenue DESC
"""


def snowflake_is_configured() -> bool:
    """True only when the credentials needed to reach Snowflake are present."""
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
    return all(os.environ.get(name) for name in required)


def run_revenue_analysis() -> str:
    """
    Connect to Snowflake and run the revenue-by-segment query against the
    free TPC-H sample data, then return a readable summary of the rows.

    The connector is imported here rather than at the top of the file so the
    rest of the project still runs when Snowflake isn't installed or configured.
    """
    import snowflake.connector

    connection = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    )

    logger.info("Running revenue-by-segment query on Snowflake.")
    try:
        cursor = connection.cursor()
        cursor.execute(REVENUE_BY_SEGMENT_QUERY)
        rows = cursor.fetchall()
    finally:
        connection.close()

    lines = ["Revenue by market segment (Snowflake TPC-H sample data):"]
    for market_segment, total_revenue, order_count in rows:
        lines.append(f"  {market_segment}: {total_revenue:,.2f} across {order_count:,} orders")
    return "\n".join(lines)
