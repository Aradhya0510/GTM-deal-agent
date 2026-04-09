# Databricks notebook source
import json, mlflow

result = {}
result["mlflow_version"] = mlflow.__version__

# Check mlflow.pyfunc for ChatAgent
pyfunc_names = [n for n in dir(mlflow.pyfunc) if 'agent' in n.lower() or 'chat' in n.lower()]
result["mlflow_pyfunc_agent"] = pyfunc_names

# Check for ChatAgent in mlflow
agent_checks = {}
for path in ['mlflow.pyfunc.ChatAgent', 'mlflow.models.resources.DatabricksVectorSearchIndex',
             'mlflow.models.resources.DatabricksFunction', 'mlflow.models.resources.DatabricksServingEndpoint']:
    parts = path.rsplit('.', 1)
    try:
        mod = __import__(parts[0], fromlist=[parts[1]])
        agent_checks[path] = hasattr(mod, parts[1])
    except:
        agent_checks[path] = False
result["checks"] = agent_checks

# Check for UC tools
uc_checks = {}
for mod_path in ['databricks_agents', 'unitycatalog', 'langchain_databricks', 'langchain_community.tools.databricks']:
    try:
        __import__(mod_path)
        uc_checks[mod_path] = True
    except:
        uc_checks[mod_path] = False
result["module_available"] = uc_checks

# Check langchain_community.tools
try:
    from langchain_community import tools as lc_tools
    lc_names = [n for n in dir(lc_tools) if 'databricks' in n.lower() or 'uc' in n.lower() or 'vector' in n.lower()]
    result["langchain_tools"] = lc_names
except:
    result["langchain_tools"] = "not available"

# Check for ChatAgent properly
try:
    from mlflow.pyfunc import ChatAgent
    result["ChatAgent_import"] = "OK from mlflow.pyfunc"
except ImportError:
    try:
        from mlflow.types.agent import ChatAgent
        result["ChatAgent_import"] = "OK from mlflow.types.agent"
    except ImportError:
        result["ChatAgent_import"] = "NOT FOUND"

dbutils.notebook.exit(json.dumps(result, indent=2))
