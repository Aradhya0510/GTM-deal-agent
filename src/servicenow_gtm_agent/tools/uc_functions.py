"""Unity Catalog function tools for the deal intelligence agent.

These wrap UC SQL TABLE functions registered in setup/03_uc_functions.sql.
The agent calls them via databricks_langchain's UCFunctionToolkit.

IMPORTANT:
- UC SQL functions must use RETURNS TABLE (not scalar RETURNS STRING)
  to avoid correlated scalar subquery errors.
- Python UC Functions cannot use SparkSession on serverless compute.
- Use pre-aggregated JOINs instead of correlated subqueries.

Databricks tech: Unity Catalog Functions + Serverless SQL Warehouse
"""

from databricks_langchain import UCFunctionToolkit


def get_uc_tools(catalog: str = "users", schema: str = "aradhya_chouhan") -> list:
    """Create UC Function tools via UCFunctionToolkit.

    Returns LangChain tool objects that can be passed to llm.bind_tools().
    """
    toolkit = UCFunctionToolkit(
        function_names=[
            f"{catalog}.{schema}.calculate_deal_health",
            f"{catalog}.{schema}.get_account_signals",
        ]
    )
    return list(toolkit.tools)
