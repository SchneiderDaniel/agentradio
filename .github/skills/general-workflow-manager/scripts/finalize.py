import json
import subprocess
import sys
import argparse
import os

# Import the configuration
try:
    from workflow_config import TRANSITIONS
    from utils import load_config
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from workflow_config import TRANSITIONS
    from utils import load_config

CONFIG = load_config()

def run_command(command, env=None):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=env, encoding="utf-8")
        return result.stdout.strip() or True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr}")
        return None

def post_comment(issue_number, comment_file, repo=CONFIG["repo"]):
    print(f"Posting comment to issue #{issue_number}...")
    try:
        with open(comment_file, "r", encoding="utf-8") as f:
            comment_body = f.read()
    except Exception as e:
        print(f"❌ Error reading comment file: {e}")
        return False

    # Idempotency check: skip if an identical comment already exists
    existing = run_command([
        "gh", "issue", "view", str(issue_number),
        "--repo", repo,
        "--json", "comments"
    ])
    if existing and existing is not True:
        import json as _json
        try:
            data = _json.loads(existing)
            for c in data.get("comments", []):
                if c.get("body", "").strip() == comment_body.strip():
                    print(f"⚠️ Comment already exists on issue #{issue_number}, skipping.")
                    return True
        except Exception:
            pass

    result = run_command([
        "gh", "issue", "comment", str(issue_number),
        "--repo", repo,
        "--body", comment_body
    ])
    return result is not None

def add_memory(text_file, project, role, namespace):
    print(f"Syncing to Myosotis (Namespace: {namespace})...")
    try:
        with open(text_file, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"❌ Error reading memory file: {e}")
        return False

    # Construct PYTHONPATH to find the myosotis package
    root_dir = os.getcwd()
    myosotis_dir = os.path.join(root_dir, "flask_blogs", "myosotis")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = myosotis_dir + os.pathsep + env.get("PYTHONPATH", "")

    # Call Myosotis CLI
    result = run_command([
        sys.executable, "-m", "myosotis.cli.main", "add",
        text,
        "--project", project,
        "--role", role,
        "--namespace", namespace
    ], env=env)
    
    if result:
        print(f"✅ Myosotis Sync: {result}")
        return True
    return False

def ensure_issue_open(issue_number, repo=CONFIG["repo"]):
    """Re-open the GitHub issue if GitHub project automation auto-closed it.
    
    When a project board item is moved to 'Done', GitHub may automatically
    close the linked issue. This function detects and reverses that action,
    since only the human reviewer is allowed to close issues.
    """
    import time
    time.sleep(2)  # Brief pause to allow GitHub automation to run first

    state_json = run_command([
        "gh", "issue", "view", str(issue_number),
        "--repo", repo,
        "--json", "state"
    ])
    if not state_json or state_json is True:
        print(f"⚠️ Could not verify issue #{issue_number} state.")
        return

    try:
        state = json.loads(state_json).get("state", "").upper()
    except Exception:
        state = ""

    if state == "CLOSED":
        print(f"⚠️ Issue #{issue_number} was auto-closed by GitHub automation. Re-opening...")
        result = run_command([
            "gh", "issue", "reopen", str(issue_number),
            "--repo", repo
        ])
        if result is not None:
            print(f"✅ Issue #{issue_number} re-opened. Only the human reviewer may close it.")
        else:
            print(f"❌ Failed to re-open issue #{issue_number}. Manual intervention required.")
    else:
        print(f"✅ Issue #{issue_number} is still open — no auto-close detected.")


def transition_workflow(issue_number, outcome, repo=CONFIG["repo"]):
    print(f"Updating GitHub Project status (Outcome: {outcome})...")

    project_number = CONFIG.get("github_project_number")
    owner = repo.split("/")[0]

    # 1. Get item_id, project_id and current_status via project item-list
    items_json = run_command([
        "gh", "project", "item-list", str(project_number),
        "--owner", owner,
        "--format", "json",
        "--limit", "500"
    ])

    if not items_json:
        return False

    items_data = json.loads(items_json)
    item = next(
        (i for i in items_data.get("items", [])
         if i.get("content", {}).get("number") == issue_number),
        None
    )

    if not item:
        print(f"❌ Error: Issue #{issue_number} not found in project #{project_number}.")
        return False

    item_id = item.get("id")
    current_status = item.get("status")

    if not current_status:
        print(f"❌ Error: Could not determine current status for issue #{issue_number}.")
        return False

    # Fetch the project node ID
    projects_json = run_command([
        "gh", "project", "list",
        "--owner", owner,
        "--format", "json"
    ])
    if not projects_json:
        return False
    projects_data = json.loads(projects_json)
    project_node = next(
        (p for p in projects_data.get("projects", []) if p.get("number") == project_number),
        None
    )
    if not project_node:
        print(f"❌ Error: Project #{project_number} not found.")
        return False
    project_id = project_node.get("id")

    # 2. Determine target status
    status_transitions = TRANSITIONS.get(current_status)
    if not status_transitions:
        print(f"❌ Error: No transitions defined for '{current_status}'.")
        return False

    target_status = status_transitions.get(outcome)
    if not target_status:
        print(f"❌ Error: No target for outcome '{outcome}' from '{current_status}'.")
        return False
    
    # 3. Find field and option IDs
    fields_json = run_command([
        "gh", "project", "field-list", str(project_number),
        "--owner", owner,
        "--format", "json"
    ])
    
    if not fields_json:
        return False
    
    fields_data = json.loads(fields_json)
    status_field = next((f for f in fields_data.get("fields", []) if f.get("name") == "Status"), None)
    if not status_field:
        return False
    
    field_id = status_field.get("id")
    option = next((o for o in status_field.get("options", []) if o.get("name").lower() == target_status.lower()), None)
    if not option:
        return False
    
    option_id = option.get("id")
    
    # Apply update
    update_result = run_command([
        "gh", "project", "item-edit",
        "--id", item_id,
        "--project-id", project_id,
        "--field-id", field_id,
        "--single-select-option-id", option_id
    ])
    
    if update_result:
        print(f"✅ Project Status: Advanced from '{current_status}' to '{target_status}'.")
        # Guard: if the board moved to "Done", GitHub automation may auto-close the issue.
        # Detect and reverse that — only the human reviewer may close the issue.
        if target_status.lower() == "done":
            ensure_issue_open(issue_number, repo)
        return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Finalize an agent mission (GitHub + Myosotis + Project Status).")
    parser.add_argument("issue_number", type=int, help="The issue number.")
    parser.add_argument("outcome", type=str, help="Mission outcome (success, failure, revision_requested, etc.).")
    parser.add_argument("--comment-file", type=str, help="File with GitHub comment body.")
    parser.add_argument("--memory-file", type=str, help="File with Myosotis memory text.")
    parser.add_argument("--memory-project", type=str, default=CONFIG["myosotis_project"], help="Myosotis project.")
    parser.add_argument("--memory-role", type=str, help="Myosotis role (e.g., product_owner).")
    parser.add_argument("--memory-namespace", type=str, help="Myosotis namespace (e.g., requirements).")
    parser.add_argument("--repo", type=str, default=CONFIG["repo"], help="The repository.")
    
    args = parser.parse_args()
    
    print(f"--- 🏁 Mission Finalization (Issue #{args.issue_number}) ---")
    
    success = True
    
    # 1. Post GitHub Comment
    if args.comment_file:
        if not post_comment(args.issue_number, args.comment_file, args.repo):
            success = False

    # 2. Sync to Myosotis
    if args.memory_file and args.memory_role and args.memory_namespace:
        if not add_memory(args.memory_file, args.memory_project, args.memory_role, args.memory_namespace):
            success = False
    elif args.memory_file:
        print("⚠️ Warning: Memory file provided but role/namespace missing. Skipping Myosotis sync.")

    # 3. Transition Project Status
    if not transition_workflow(args.issue_number, args.outcome, args.repo):
        success = False

    if success:
        print("🎉 Mission Finalized Successfully.")
        sys.exit(0)
    else:
        print("❌ Mission Finalization encountered errors.")
        sys.exit(1)
