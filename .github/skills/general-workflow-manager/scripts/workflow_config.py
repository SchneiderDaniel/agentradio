# Mapping of personas to the statuses they are authorized to work on.
GATES = {
    "Analyst": ["Backlog"],
    "Architect": ["Technical Design"],
    "QA-Lead": ["Test Design"],
    "Developer": ["Implementation", "Revision Required"],
    "Auditor": ["Review"]
}

# Mapping of current status and mission outcome to the next status.
TRANSITIONS = {
    "Backlog": {
        "success": "Technical Design",
        "failure": "Backlog"
    },
    "Technical Design": {
        "success": "Test Design",
        "failure": "Backlog"
    },
    "Test Design": {
        "success": "Implementation",
        "failure": "Technical Design"
    },
    "Implementation": {
        "success": "Review",
        "failure": "Test Design",
        "design_revision_requested": "Technical Design"
    },
    "Review": {
        "audit_passed": "Done",
        # Code-level issues: send back to Developer via dedicated "Revision Required" status.
        # This distinguishes Auditor-driven rework from first-time implementation.
        "revision_required": "Revision Required",
        "failure": "Revision Required",              # alias kept for backward compatibility
        "test_revision_requested": "Test Design",
        "design_revision_requested": "Technical Design"
        # Note: closing the GitHub issue is done by the human reviewer only.
    },
    # Developer picks up Auditor feedback here and re-submits for review.
    "Revision Required": {
        "success": "Review",
        "failure": "Revision Required"
    }
}
