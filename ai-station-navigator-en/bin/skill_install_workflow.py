#!/usr/bin/env python3
"""
skill_install_workflow.py - Skill Installation Workflow
--------------------------------------------------------
LangGraph Workflow: Chaining clone_manager + security_scanner + skill_manager

Flow:
1. clone_repo_node - Clone GitHub repo and extract skills
2. security_scan_node - Batch security scan
3. check_threat_level - Determine threat level
4. llm_analysis_review_node - LLM secondary analysis (interruptible)
5. install_skills_node - Install skills

Features:
- State persistence (SQLite)
- Interrupt recovery (interrupt)
- False positive handling (LLM analysis)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, TypedDict
from urllib.parse import urlparse

# Add project root directory to sys.path
# From bin/skill_install_workflow.py → project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))  # Add bin directory to import security_scanner

# Add lib directory to sys.path (portable package dependencies)
LIB_DIR = PROJECT_ROOT / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

# LangGraph imports
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, END
from typing_extensions import operator


# =============================================================================
# State Definition
# =============================================================================

class InstallWorkflowState(TypedDict):
    """Skill Installation Workflow State"""
    # Input parameters
    github_url: str                      # GitHub repo URL
    skill_name: Optional[str]            # Optional: sub-skill name
    force_install: bool                  # Force overwrite

    # Intermediate state
    cloned_repo_path: Optional[str]      # Cloned repo path
    extracted_skills: List[str]          # Extracted skill directory list
    scan_results: Dict[str, Dict]        # Scan results {skill_name: result}
    threatened_skills: List[Dict]        # Threatened skills list

    # LLM analysis
    llm_analysis_pending: bool           # Whether LLM secondary analysis needed
    llm_analysis_result: Optional[str]   # LLM analysis result (JSON string)
    rule_decisions: Dict[str, str]       # Rule engine decisions {skill_name: "keep"/"uninstall"}
    analysis_prompt: Optional[str]       # Analysis prompt (for Kernel use)
    pending_skills: List[str]            # Skills pending LLM review
    prompt_file: Optional[str]           # Analysis prompt file path

    # Output results
    installed_skills: List[str]          # Successfully installed skills
    failed_skills: List[str]             # Failed skills
    skipped_skills: List[str]            # Skipped skills

    # Logs
    logs: Annotated[List[str], operator.add]


# =============================================================================
# Utility Functions
# =============================================================================

def extract_skill_name_from_url(url: str) -> Optional[str]:
    """Extract final sub-skill name from GitHub URL

    Examples:
        https://github.com/user/repo/tree/main/skills/anndata → anndata
        https://github.com/user/repo → None
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')

        # Find /tree/ separator
        if 'tree' in path_parts:
            tree_idx = path_parts.index('tree')
            # Extract last segment after tree as skill name
            if len(path_parts) > tree_idx + 2:
                return path_parts[-1]
    except Exception:
        pass

    return None


def run_subprocess(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run subprocess command

    Args:
        cmd: Command list
        cwd: Working directory
        timeout: Timeout (seconds), default 5 minutes
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        timeout=timeout
    )


def parse_skill_paths(output: str) -> List[str]:
    """Parse skill paths from clone_manager output"""
    paths = []
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('- ') and len(line) > 2:
            path = line[2:].strip()
            if Path(path).exists():
                paths.append(path)
    return paths


def extract_github_info(github_url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract author and repo from GitHub URL

    Supported formats:
    - https://github.com/author/repo
    - https://github.com/author/repo/tree/branch/subpath
    - author/repo (shorthand format)

    Returns:
        (author, repo)
    """
    import re
    if "github.com" in github_url:
        # Parse URL, extract path part
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2:
            author = path_parts[0]
            repo = path_parts[1]
            return author, repo
    elif '/' in github_url:
        parts = github_url.strip().split('/')
        if len(parts) >= 2:
            author = parts[0]
            repo = parts[1]
            return author, repo
    return None, None


# =============================================================================
# Node Implementations
# =============================================================================

def clone_repo_node(state: InstallWorkflowState) -> Dict:
    """
    Clone GitHub repo and extract skill directories

    Call: python bin/clone_manager.py clone <url>
    Filter: Filter at workflow layer based on state["skill_name"] (architectural consistency)

    Auto-extract skill name from URL subpath:
    - https://github.com/user/repo/tree/main/skills/anndata -> skill_name="anndata"
    """
    url = state["github_url"]
    skill_name = state.get("skill_name")

    # Auto-extract skill name from URL (if not explicitly specified)
    if not skill_name:
        extracted_name = extract_skill_name_from_url(url)
        if extracted_name:
            skill_name = extracted_name

    force = state.get("force_install", False)

    cmd = [sys.executable, str(SCRIPT_DIR / "clone_manager.py"), "clone", url]
    # No longer pass --skill parameter, filter at workflow layer for architectural consistency
    if force:
        cmd.append("--force")

    result = run_subprocess(cmd, cwd=PROJECT_ROOT)

    logs = []
    if result.returncode != 0:
        error_msg = result.stderr or result.stdout
        logs.append(f"[ERROR] Clone failed: {error_msg}")
        return {"logs": logs}

    # Parse output to get skill directories
    skill_dirs = parse_skill_paths(result.stdout)

    if not skill_dirs:
        logs.append("[WARN] No skill directories detected")
        logs.append(f"[DEBUG] Output: {result.stdout}")
    else:
        logs.append(f"[OK] Clone successful, found {len(skill_dirs)} skills")

        # Filter at workflow layer based on skill_name (architectural uniformity: parameters passed via LangGraph state)
        if skill_name:
            normalized_target = skill_name.lower().replace('_', '-')
            filtered = []
            for skill_dir in skill_dirs:
                dir_name = Path(skill_dir).name
                # Support direct match and _/- variant matching
                if (dir_name.lower() == skill_name.lower() or
                    dir_name.lower().replace('_', '-') == normalized_target or
                    dir_name.lower().replace('-', '_') == normalized_target):
                    filtered.append(skill_dir)
                    logs.append(f"[FILTER] Matched skill: {dir_name}")

            if filtered:
                logs.append(f"[FILTER] Applied skill_name filter: {len(skill_dirs)} -> {len(filtered)} skills")
                skill_dirs = filtered
            else:
                logs.append(f"[WARN] No skill matching '{skill_name}' found, returning all {len(skill_dirs)} skills")

    return {
        "cloned_repo_path": url,
        "extracted_skills": skill_dirs,
        "logs": logs
    }


def security_scan_node(state: InstallWorkflowState) -> Dict:
    """
    Batch security scan for all skills (concurrent mode)

    Call: batch_scan() - 4 threads concurrent, batch processing
    """
    from security_scanner import batch_scan

    skill_dirs = state["extracted_skills"]
    scan_results = {}
    threatened_skills = []

    logs = [f"[INFO] Starting concurrent scan of {len(skill_dirs)} skills..."]

    # Convert to Path objects
    skill_paths = [Path(p) for p in skill_dirs]

    # Call concurrent scan (4 threads, batch processing)
    batch_results = batch_scan(skill_paths)

    # Process results
    for skill_name, scan_data in batch_results.items():
        scan_results[skill_name] = scan_data

        severity = scan_data.get("severity", "UNKNOWN")
        if severity not in ["SAFE", "LOW"]:
            # Find original path
            original_path = next((p for p in skill_dirs if Path(p).name == skill_name), None)
            if not original_path:
                original_path = str(skill_paths[0].parent / skill_name)
            threatened_skills.append({
                "name": skill_name,
                "path": original_path,
                "scan_result": scan_data
            })
            logs.append(f"[!] {skill_name}: {severity} ({scan_data.get('findings_count', 0)} threats)")
        else:
            logs.append(f"[OK] {skill_name}: {severity}")

    threatened_count = len(threatened_skills)
    logs.append(f"[SUMMARY] Scan complete: {threatened_count} threatened skills")

    return {
        "scan_results": scan_results,
        "threatened_skills": threatened_skills,
        "logs": logs
    }


def parse_scan_output(output: str, skill_name: str) -> Dict:
    """Parse security_scanner output to structured data"""
    lines = output.split('\n')

    result = {
        "name": skill_name,
        "status": "unknown",
        "severity": "UNKNOWN",
        "findings_count": 0,
        "threats": []
    }

    # Try to extract JSON data (scanner output may contain JSON)
    json_data = None
    for line in lines:
        if line.strip().startswith('{'):
            try:
                json_data = json.loads(line.strip())
                break
            except json.JSONDecodeError:
                pass

    if json_data:
        # Extract complete information from JSON
        result["status"] = json_data.get("status", "unknown")
        result["severity"] = json_data.get("severity", "UNKNOWN")
        result["findings_count"] = json_data.get("findings_count", 0)
        result["threats"] = json_data.get("threats", [])
    else:
        # Fallback to text parsing
        for line in lines:
            if "Status:" in line:
                result["status"] = line.split("Status:")[1].strip()
            elif "Severity:" in line:
                result["severity"] = line.split("Severity:")[1].strip()
            elif "Threats found:" in line:
                try:
                    result["findings_count"] = int(line.split("Threats found:")[1].strip())
                except ValueError:
                    pass

    return result


def extract_code_snippet(file_path: str, line_number: int, context_lines: int = 2, allowed_base: Optional[Path] = None) -> str:
    """
    Extract context snippet of specified code line

    Args:
        file_path: File path
        line_number: Problem code line number (1-based)
        context_lines: Context lines count (default 2 lines before and after)

    Returns:
        Code snippet string, returns error message on failure
    """
    # Path validation: ensure file_path is within allowed range
    abs_path = Path(file_path).resolve()
    if allowed_base is not None:
        allowed_abs = allowed_base.resolve()
        try:
            abs_path.relative_to(allowed_abs)
        except ValueError:
            return f"[Path validation failed: {file_path} not in allowed directory {allowed_base}]"

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Convert to 0-based index
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        snippet_lines = []
        for i in range(start, end):
            line_num = i + 1  # 1-based line number
            marker = ">>> " if line_num == line_number else "    "
            snippet_lines.append(f"{marker}{line_num:4d} | {lines[i].rstrip()}")

        return "\n".join(snippet_lines)

    except Exception as e:
        return f"[Cannot read file: {file_path}:{line_number} - {e}]"


def llm_analysis_review_node(state: InstallWorkflowState) -> Dict:
    """
    LLM Secondary Analysis Node (Pure LLM Analysis Mode)

    Flow:
    1. All threatened skills go directly to LLM analysis (no rule engine pre-filtering)
    2. Build analysis_prompt
    3. Return pending_llm_analysis state, handled by Kernel

    Note: Rule engine is commented out, uncomment below code to enable
    """
    threatened = state["threatened_skills"]

    if not threatened:
        return {"llm_analysis_pending": False, "logs": ["[INFO] No LLM analysis needed"]}

    logs = [f"[INFO] Starting LLM analysis for {len(threatened)} threatened skills..."]

    # ============================================================================
    # [Commented] Rule engine pre-filtering
    # To enable rule engine, uncomment below and comment out "Pure LLM Analysis Mode" section
    # ============================================================================

    # decisions = {}
    # pending_llm = []  # Skills requiring LLM review
    #
    # THREAT_PATTERNS = {
    #     "confirmed": [
    #         (r"requests\.post\([^)]*user[_-]input", "User input directly used for network requests"),
    #         (r"urllib\.request\.urlopen\([^)]*user", "User input directly used for URL requests"),
    #         (r"subprocess\.call\([^)]*user", "User input directly used for command execution"),
    #         (r"os\.system\([^)]*user", "User input directly used for system commands"),
    #         (r"eval\([^)]*user[_-]input", "User input directly used for eval"),
    #         (r"pathlib\.Path\([\"']home/[\"']\)\.rglob", "Scanning user home directory"),
    #         (r"shutil\.copy2\([^)]*\.ssh/", "Copying SSH keys"),
    #         (r"open\([^)]*\.env", "Reading environment variable files"),
    #         (r"while\s+True:.*requests\.post", "Infinite loop network requests (backdoor)"),
    #         (r"cryptonight|monero|bitcoin.*mining", "Cryptocurrency mining"),
    #         (r"socket\.create_server\([\"']0\.0\.0\.0", "Listening on all ports (backdoor)"),
    #         (r"base64\.b64decode\([^)]+exec\(", "Base64 decode then execute code"),
    #         (r"compile\([^)]+eval\(", "Dynamic compile and execute code"),
    #     ],
    #     "false_positive": [
    #         (r"test_|_test\.py", "Test files"),
    #         (r"example|demo|sample", "Example code"),
    #         (r"README|CONTRIBUTING|LICENSE", "Documentation files"),
    #         (r"__init__\.py", "Package initialization files"),
    #         (r"skill\.md", "Skill description files"),
    #         (r"pytest|unittest|assert", "Test frameworks"),
    #         (r"logging\.|print\(", "Log output"),
    #         (r"dataclass|@dataclass", "Data class definitions"),
    #         (r"typing\.|List\|Dict", "Type annotations"),
    #         (r"argparse|click|typer", "Command line argument parsing"),
    #         (r"pathlib\.Path\([^)]*\)\.exists\(\)", "File existence check"),
    #         (r"pathlib\.Path\([^)]*\)\.read_text\(\)", "Reading own files"),
    #         (r"State\[|TypedDict", "State type definitions"),
    #         (r"langgraph|LangGraph", "Workflow framework"),
    #         (r"def\s+.*_node\(", "Workflow node functions"),
    #         (r"workflow|graph\.add_edge", "Workflow building"),
    #     ]
    # }
    #
    # import re
    #
    # for threat in threatened:
    #     skill_name = threat["name"]
    #     skill_path = Path(threat["path"])
    #     severity = threat["scan_result"].get("severity", "UNKNOWN")
    #
    #     logs.append(f"[RULES] {skill_name} ({severity})")
    #
    #     # Read code
    #     all_code = []
    #     file_count = 0
    #     for file_path in skill_path.rglob("*"):
    #         if file_path.is_file() and file_path.suffix in [".py", ".js", ".ts", ".md"]:
    #             try:
    #                 content = file_path.read_text(encoding="utf-8", errors="ignore")
    #                 all_code.append(f"// {file_path.name}\n{content}")
    #                 file_count += 1
    #             except Exception:
    #                 pass
    #
    #     combined_code = "\n".join(all_code)
    #
    #     # Rule matching
    #     confirmed_count = 0
    #     false_positive_count = 0
    #
    #     for pattern, _ in THREAT_PATTERNS["confirmed"]:
    #         if re.search(pattern, combined_code, re.IGNORECASE):
    #             confirmed_count += 1
    #
    #     for pattern, _ in THREAT_PATTERNS["false_positive"]:
    #         if re.search(pattern, skill_name, re.IGNORECASE) or \
    #            re.search(pattern, combined_code, re.IGNORECASE):
    #             false_positive_count += 1
    #
    #     # Decision logic
    #     if confirmed_count >= 2:
    #         # High confidence threat
    #         decisions[skill_name] = "uninstall"
    #         logs.append(f"  -> CONFIRMED THREAT ({confirmed_count} threat patterns)")
    #     elif false_positive_count >= 3:
    #         # High confidence safe
    #         decisions[skill_name] = "keep"
    #         logs.append(f"  -> CONFIRMED SAFE ({false_positive_count} false positive features)")
    #     else:
    #         # Low confidence, needs LLM review
    #         pending_llm.append({
    #             "name": skill_name,
    #             "path": str(skill_path),
    #             "severity": severity,
    #             "code_preview": combined_code[:3000] if combined_code else "",
    #             "confirmed_count": confirmed_count,
    #             "false_positive_count": false_positive_count
    #         })
    #         logs.append(f"  -> PENDING LLM REVIEW")
    #
    # # ============================================================================
    # # Phase 2: Determine if LLM review is needed
    # # ============================================================================
    #
    # if not pending_llm:
    #     logs.append(f"[SUMMARY] Rule engine complete, no LLM review needed")
    #     return {
    #         "llm_analysis_result": json.dumps(decisions, ensure_ascii=False),
    #         "llm_analysis_pending": False,
    #         "logs": logs
    #     }
    #
    # # Skills requiring LLM review
    # logs.append(f"[INFO] {len(pending_llm)} skills need LLM review")

    # ============================================================================
    # Pure LLM Analysis Mode: All threatened skills go directly to LLM review
    # ============================================================================

    decisions = {}
    pending_llm = []  # Skills requiring LLM review

    for threat in threatened:
        skill_name = threat["name"]
        skill_path = Path(threat["path"])
        severity = threat["scan_result"].get("severity", "UNKNOWN")
        threats_data = threat["scan_result"].get("threats", [])

        logs.append(f"[LLM_ONLY] {skill_name} ({severity})")

        # Extract code snippets from scan results (use snippet to search context)
        code_snippets = []
        for t in threats_data:
            snippet = t.get("snippet")  # YARA matched keyword
            rule_id = t.get("rule_id")
            title = t.get("title", "")
            file_path = t.get("file")

            if snippet and file_path:
                # Use snippet as keyword to search in file, extract context
                abs_file_path = Path(file_path)
                if not abs_file_path.is_absolute():
                    abs_file_path = skill_path / file_path

                # Extract keyword for search (use first 50 chars of snippet as search term)
                keyword = snippet[:50].strip()

                # Search for keyword in file and extract context
                try:
                    with open(abs_file_path, encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    # Search for lines containing keyword
                    matched_line = -1
                    for i, line in enumerate(lines):
                        if keyword.lower() in line.lower():
                            matched_line = i
                            break

                    if matched_line >= 0:
                        # Extract context (2 lines before and after)
                        start = max(0, matched_line - 2)
                        end = min(len(lines), matched_line + 3)

                        context_lines = []
                        for i in range(start, end):
                            line_num = i + 1
                            marker = ">>> " if i == matched_line else "    "
                            context_lines.append(f"{marker}{line_num:4d} | {lines[i].rstrip()}")

                        code = "\n".join(context_lines)
                    else:
                        code = f"[Keyword not found: {keyword[:30]}...]"

                except Exception as e:
                    code = f"[Read failed: {e}]"

                code_snippets.append({
                    "rule": rule_id,
                    "title": title,
                    "file": file_path,
                    "line": matched_line + 1 if matched_line >= 0 else 0,
                    "code": code
                })

        # Add directly to LLM review list (no rule filtering)
        pending_llm.append({
            "name": skill_name,
            "path": str(skill_path),
            "severity": severity,
            "code_snippets": code_snippets,
            "threats_count": len(code_snippets),
            "confirmed_count": 0,  # No rule engine, set to 0
            "false_positive_count": 0  # No rule engine, set to 0
        })
        logs.append(f"  -> PENDING LLM REVIEW ({len(code_snippets)} code snippets)")

    # Skills requiring LLM review
    logs.append(f"[INFO] {len(pending_llm)} skills need LLM review (pure LLM mode)")

    # Build interrupt instruction (reference template: include complete context)
    instruction_parts = [
        "=" * 60,
        "[LLM Secondary Analysis Task]",
        "=" * 60,
        f"\nTask: Analyze the following {len(pending_llm)} threatened skills, determine if false positive",
        f"\nJudgment criteria:",
        "  - False positive features (allow install): workflow design, development tools, quality control, test code, normal code structure",
        "  - Confirmed threats (should uninstall): eval/exec concatenating user input, shell command injection, sensitive data theft, backdoors, mining",
        "\nSkills to analyze:",
    ]

    for i, skill in enumerate(pending_llm, 1):
        instruction_parts.extend([
            f"\n{i}. {skill['name']}",
            f"   Severity: {skill['severity']}",
            f"   Path: {skill['path']}",
        ])

        # Add specific code snippets
        if skill["code_snippets"]:
            instruction_parts.append(f"   Threat code snippets ({skill['threats_count']} total):")
            for j, snippet in enumerate(skill["code_snippets"][:5], 1):  # Show max 5 snippets
                instruction_parts.extend([
                    f"     [{j}] {Path(snippet['file']).name}:{snippet['line']}",
                    f"         Rule: {snippet['rule']} | {snippet['title']}",
                    f"         ```",
                    snippet['code'],
                    f"         ```",
                ])

            if skill['threats_count'] > 5:
                instruction_parts.append(f"     ... {skill['threats_count'] - 5} more snippets")
        else:
            instruction_parts.append(f"   No specific code snippets (metadata only)")

    instruction_parts.extend([
        "\n" + "=" * 60,
        "ACTION REQUIRED:",
        "Output format (JSON):",
        '{"skill-name-1": "keep", "skill-name-2": "uninstall", ...}',
        "\nResume method:",
        f"  python bin/skill_install_workflow.py {state.get('github_url', '')} --result='{{\"skill\": \"keep\"}}'",
        "=" * 60,
    ])

    analysis_prompt = "\n".join(instruction_parts)

    # Save analysis_prompt to file (for Kernel to read)
    prompt_file = PROJECT_ROOT / "mybox" / "temp" / "llm_analysis_prompt.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(analysis_prompt, encoding="utf-8")

    logs.append(f"[INFO] Analysis prompt saved: {prompt_file}")

    # ============================================================================
    # 使用 LangGraph interrupt() 暂停工作流
    # ============================================================================

    try:
        from langgraph.types import interrupt

        # Pause workflow, wait for LLM analysis result
        # On resume, LLM decision will be passed via Command(resume=...)
        llm_decision = interrupt(analysis_prompt)

        # After resume: parse LLM decision
        if llm_decision and str(llm_decision).strip():
            try:
                if isinstance(llm_decision, str):
                    decisions.update(json.loads(llm_decision))
                else:
                    decisions.update(llm_decision)
                logs.append(f"[INFO] LLM decision received: {decisions}")
            except json.JSONDecodeError as e:
                logs.append(f"[ERROR] LLM decision parse failed: {e}")
                # Fallback to conservative strategy
                for skill in pending_llm:
                    decisions[skill["name"]] = "keep"
                logs.append(f"[WARN] Fallback to conservative strategy: all keep")
        else:
            # No decision, conservative strategy: all keep
            for skill in pending_llm:
                decisions[skill["name"]] = "keep"
            logs.append(f"[WARN] No LLM decision, using conservative strategy: all keep")

        return {
            "llm_analysis_result": json.dumps(decisions, ensure_ascii=False),
            "llm_analysis_pending": False,
            "rule_decisions": decisions,
            "logs": logs
        }

    except ImportError as e:
        # interrupt not available, throw specific exception for main flow to handle
        logs.append(f"[ERROR] interrupt() not available: {e}")
        logs.append(f"[INFO] Analysis prompt: {prompt_file}")

        # Save manual resume request
        manual_request = {
            "url": state.get("github_url", ""),
            "pending_skills": [s["name"] for s in pending_llm],
            "prompt_file": str(prompt_file),
            "resume_command": f"python bin/skill_install_workflow.py {state.get('github_url', '')} --result='{{\"skill-name\": \"keep\", ...}}'"
        }

        request_file = PROJECT_ROOT / "mybox" / "temp" / "manual_resume_request.json"
        request_file.write_text(json.dumps(manual_request, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n" + "=" * 60)
        print("[INTERRUPT NOT AVAILABLE]")
        print("=" * 60)
        print(analysis_prompt)
        print(f"\nResume command saved: {request_file}")
        print("=" * 60)

        # Throw specific exception instead of direct exit, let main flow decide how to handle
        raise RuntimeError("LangGraph interrupt() not available, please ensure langgraph package is properly installed")


def install_skills_node(state: InstallWorkflowState) -> Dict:
    """
    Install skills node

    Call: python bin/skill_manager.py install <skill_path>
    """
    skill_dirs = state["extracted_skills"]
    scan_results = state["scan_results"]
    llm_analysis = state.get("llm_analysis_result")
    rule_decisions = state.get("rule_decisions", {})
    force = state.get("force_install", False)

    # Merge rule decisions and LLM decisions
    uninstall_skills = set()

    # 1. Process rule engine decisions (high confidence)
    for skill_name, decision in rule_decisions.items():
        if decision == "uninstall":
            uninstall_skills.add(skill_name)

    # 2. Process LLM analysis results (secondary review of low confidence skills)
    if llm_analysis:
        try:
            decisions = json.loads(llm_analysis)
            for skill_name, decision in decisions.items():
                if decision == "uninstall":
                    uninstall_skills.add(skill_name)
        except json.JSONDecodeError:
            pass

    installed = []
    failed = []
    skipped = list(uninstall_skills)

    logs = [f"[INFO] Starting installation of {len(skill_dirs)} skills..."]
    logs.append(f"[INFO] Rule decisions: {len(rule_decisions)}, LLM decisions: {len(json.loads(llm_analysis) if llm_analysis else {})}")

    # Extract author and repo from GitHub URL (for building skill names)
    github_author, github_repo = extract_github_info(state.get("github_url", ""))

    for skill_path in skill_dirs:
        skill_name = Path(skill_path).name

        # Skip skills determined as threats (by rules or LLM)
        if skill_name in uninstall_skills:
            source = "Rule engine" if skill_name in rule_decisions else "LLM analysis"
            logs.append(f"[SKIP] {skill_name}: {source} determined as threat, skipped")
            continue

        cmd = [sys.executable, str(SCRIPT_DIR / "skill_manager.py"), "install", skill_path]
        if force:
            cmd.append("--force")
        if github_author:
            cmd.extend(["--author", github_author])
        if github_repo:
            cmd.extend(["--repo", github_repo])

        result = run_subprocess(cmd, cwd=PROJECT_ROOT)

        if result.returncode == 0:
            installed.append(skill_name)
            logs.append(f"[OK] {skill_name}: Installation successful")
        else:
            failed.append(skill_name)
            error_msg = result.stderr or result.stdout
            logs.append(f"[FAIL] {skill_name}: {error_msg[:100]}")

    logs.append(f"[SUMMARY] Installation complete: {len(installed)} succeeded, {len(failed)} failed, {len(skipped)} skipped")

    return {
        "installed_skills": installed,
        "failed_skills": failed,
        "skipped_skills": skipped,
        "logs": logs
    }


# =============================================================================
# Routing Functions
# =============================================================================

def check_threat_level(
    state: InstallWorkflowState
) -> Literal["llm_analysis", "install"]:
    """
    Routing function: determine if LLM analysis is needed

    Logic:
    - No threats -> direct install
    - MEDIUM+ threats -> LLM analysis
    - Only LOW threats -> direct install
    """
    threatened = state["threatened_skills"]

    if not threatened:
        return "install"

    # Check if there are MEDIUM+ level threats
    for threat in threatened:
        severity = threat["scan_result"].get("severity", "")
        if severity in ["MEDIUM", "HIGH", "CRITICAL"]:
            return "llm_analysis"

    return "install"


# =============================================================================
# Workflow Builder
# =============================================================================

def build_graph() -> StateGraph:
    """Build workflow graph - return builder for external compilation"""
    builder = StateGraph(InstallWorkflowState)

    # Add nodes
    builder.add_node("clone_repo", clone_repo_node)
    builder.add_node("security_scan", security_scan_node)
    builder.add_node("llm_analysis_review", llm_analysis_review_node)
    builder.add_node("install_skills", install_skills_node)

    # Set entry point
    builder.set_entry_point("clone_repo")

    # Add edges
    builder.add_edge("clone_repo", "security_scan")

    # Conditional routing: determine if LLM analysis is needed based on threat level
    builder.add_conditional_edges(
        "security_scan",
        check_threat_level,
        {
            "llm_analysis": "llm_analysis_review",
            "install": "install_skills"
        }
    )

    builder.add_edge("llm_analysis_review", "install_skills")
    builder.add_edge("install_skills", END)

    return builder


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Skill installation workflow - chaining clone + scan + install",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic installation
  python bin/skill_install_workflow.py https://github.com/user/repo

  # Install specific sub-skill
  python bin/skill_install_workflow.py https://github.com/user/repo --skill my-skill

  # Force overwrite installation
  python bin/skill_install_workflow.py https://github.com/user/repo --force

  # Resume after interrupt (after LLM analysis)
  python bin/skill_install_workflow.py https://github.com/user/repo --result='{"skill": "keep"}'
        """
    )

    parser.add_argument("url", help="GitHub repository URL")
    parser.add_argument("--skill", help="Specify sub-skill name")
    parser.add_argument("--force", "-f", action="store_true", help="Force overwrite existing skills")

    # Interrupt recovery options
    parser.add_argument("--result", help="LLM analysis result (JSON format, for interrupt recovery)")
    parser.add_argument("--skip-interrupt", action="store_true", help="Skip interrupt, auto continue")

    # Debug options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only, do not execute")

    args = parser.parse_args()

    # Initial state
    initial_state: InstallWorkflowState = {
        "github_url": args.url,
        "skill_name": args.skill,
        "force_install": args.force,
        "cloned_repo_path": None,
        "extracted_skills": [],
        "scan_results": {},
        "threatened_skills": [],
        "llm_analysis_pending": False,
        "llm_analysis_result": args.result if args.result else None,
        "rule_decisions": {},
        "analysis_prompt": None,
        "pending_skills": [],
        "prompt_file": None,
        "installed_skills": [],
        "failed_skills": [],
        "skipped_skills": [],
        "logs": []
    }

    if args.dry_run:
        print("[DRY RUN] Planning to execute the following operations:")
        print(f"  1. Clone repository: {args.url}")
        if args.skill:
            print(f"  2. Extract sub-skill: {args.skill}")
        print(f"  3. Security scan all skills")
        print(f"  4. LLM analyze threats (if any)")
        print(f"  5. Install skills")
        return 0

    # Execute workflow
    builder = build_graph()

    # Generate unique thread_id (based on URL)
    url_normalized = args.url.replace('/', '_').replace('\\', '_').replace(':', '')
    thread_id = f"skill_install_{url_normalized}"

    # Configure checkpoint (reference template: independent database per task)
    checkpoint_dir = PROJECT_ROOT / "mybox" / "temp" / "langgraph" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    db_path = checkpoint_dir / f"skill_install_{url_normalized}.db"

    config = {"configurable": {"thread_id": thread_id}}

    print(f"[START] Skill installation workflow started")
    print(f"[URL] {args.url}")
    print(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # Use file-persisted checkpointer (reference template mode)
        with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            graph = builder.compile(checkpointer=checkpointer)

            # Check for incomplete tasks (interrupt recovery)
            current = graph.get_state(config)

            if current.next and not args.skip_interrupt:
                # Resume mode
                print(f"[System] Detected interrupted task, resuming: {thread_id}")

                # Parse resume parameter
                from langgraph.types import Command
                resume_value = args.result if args.result else "auto"
                graph.invoke(Command(resume=resume_value), config=config)

                # Clean up interrupt file after resume
                interrupt_file = PROJECT_ROOT / "mybox" / "temp" / "langgraph_interrupt.json"
                if interrupt_file.exists():
                    interrupt_file.unlink()
                    print(f"[System] Interrupt state file cleaned up")

            else:
                # New task mode
                graph.invoke(initial_state, config=config)

            # Output final state
            final = graph.get_state(config)

            if final.interrupts:
                # Task interrupted, display interrupt info
                # Reference template: only display interrupt value, LangGraph auto-persists to checkpoint
                interrupt_msg = final.interrupts[0].value

                print(interrupt_msg)
                print(f"\n[Info] Task paused, state saved to checkpoint")
                print(f"[Info] Resume method: python bin/skill_install_workflow.py {args.url} --result='{{\"skill-name\": \"keep\"}}'")

                # Exit on interrupt (LangGraph has auto-saved state to SQLite checkpoint)
                return 0
            else:
                # Task complete, display logs
                final_logs = final.values.get("logs", [])
                if final_logs:
                    print("\n" + "=" * 60)
                    print("[LOGS]")
                    for log in final_logs:
                        print(f"  {log}")

                print("\n" + "=" * 60)

                # Checkpoint database retained (for debugging and state tracking)
                # To clean up, manually delete: rm mybox/temp/langraph/checkpoints/skill_install.db

                # Determine exit code based on installation results
                installed = final.values.get("installed_skills", [])
                failed = final.values.get("failed_skills", [])

                # Check for error logs (clone failure etc.)
                has_error = any("[ERROR]" in log for log in final_logs)

                if len(installed) > 0:
                    print("[DONE] Workflow execution complete: Installation successful")
                    return 0
                elif len(failed) > 0:
                    print("[FAIL] Workflow execution complete: Installation failed")
                    return 1
                elif has_error:
                    print("[FAIL] Workflow execution complete: Clone or processing failed")
                    return 1
                else:
                    print("[DONE] Workflow execution complete: No skills to install")
                    return 0

    except KeyboardInterrupt:
        print("\n[INTERRUPT] User interrupted")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Workflow execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
