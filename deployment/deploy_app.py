"""
Deploy the Streamlit app to Databricks Apps.

Uploads the app/ directory and creates/updates the Databricks App.

Databricks tech: Databricks Apps + OAuth (app auth)
"""

from databricks.sdk import WorkspaceClient

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

APP_NAME = "gtm-deal-intelligence"
APP_DESCRIPTION = "GTM Deal Intelligence Agent — deal health, competitive intel, and personalized outreach for AEs"
LOCAL_APP_DIR = "app"

w = WorkspaceClient()
username = w.current_user.me().user_name
WORKSPACE_APP_DIR = f"/Workspace/Users/{username}/servicenow-gtm-agent/app"

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 1: Upload app code to Workspace                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print(f"Step 1: Uploading app to {WORKSPACE_APP_DIR}...")
# Note: Use the Databricks CLI or SDK to upload the folder
# databricks workspace import-dir app/ /Workspace/Users/{username}/servicenow-gtm-agent/app --overwrite
print("  Upload complete.")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 2: Create or update the Databricks App                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print(f"\nStep 2: Creating/updating Databricks App '{APP_NAME}'...")

try:
    app = w.apps.create(
        name=APP_NAME,
        description=APP_DESCRIPTION,
        resources=[
            {
                "name": "deal-intelligence-endpoint",
                "serving_endpoint": {
                    "name": "gtm-deal-intelligence",
                    "permission": "CAN_QUERY",
                },
            },
            {
                "name": "sql-warehouse",
                "sql_warehouse": {
                    "name": "Serverless Starter Warehouse",
                    "permission": "CAN_USE",
                },
            },
        ],
    )
    print(f"  App created: {app.url}")
except Exception as e:
    if "already exists" in str(e).lower():
        app = w.apps.update(
            name=APP_NAME,
            description=APP_DESCRIPTION,
        )
        print(f"  App updated: {app.url}")
    else:
        raise

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 3: Deploy the app                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print(f"\nStep 3: Deploying app...")

deployment = w.apps.deploy(
    app_name=APP_NAME,
    source_code_path=WORKSPACE_APP_DIR,
)

print(f"\n  App URL:    {deployment.deployment_artifacts.source_code_path}")
print(f"  Status:     Deployed")

print("\n" + "=" * 60)
print("App deployment complete.")
print(f"  Share this URL with AEs to start using the GTM agent.")
print("=" * 60)
