"""Pre-registered suite of 20 benchmark tasks for M0 kill test (BUILD_HANDBOOK §10.1)."""

from __future__ import annotations

import json
from typing import Any

from bench.tasks.base import BenchTask


def _get_common_file_tool() -> dict[str, Any]:
    return {
        "name": "read_file",
        "description": "Reads contents of a file at given path",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }


def _get_grep_tool() -> dict[str, Any]:
    return {
        "name": "grep_code",
        "description": "Search codebase for regex or string pattern",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }


def _get_exec_tool() -> dict[str, Any]:
    return {
        "name": "run_command",
        "description": "Run shell verification command",
        "parameters": {
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    }


# Registry of 20 tasks
TASKS: list[BenchTask] = []


def register_task(task: BenchTask) -> BenchTask:
    TASKS.append(task)
    return task


# 1. repo_search
def _h_repo_search(tool: str, args: dict[str, Any]) -> str:
    if tool == "grep_code":
        return "src/auth/token.py:42: def verify_jwt(token: str) -> Claims:\nsrc/api/routes.py:15: from auth.token import verify_jwt"
    if tool == "read_file":
        return "def verify_jwt(token: str) -> Claims:\n    '''Verifies HMAC-SHA256 signature and returns Claims.'''\n    return parse_and_validate(token)"
    return "Not found"


register_task(
    BenchTask(
        id="repo_search",
        title="Find JWT verification implementation",
        instructions="Locate the JWT verification logic in the codebase and describe its signature requirements.",
        user_query="Where is JWT verification handled and what algorithm does it use?",
        tools=[_get_grep_tool(), _get_common_file_tool()],
        tool_handler=_h_repo_search,
        checker=lambda resp, calls: "verify_jwt" in resp and "HMAC-SHA256" in resp,
        expected_turns=2,
    )
)


# 2. test_fix
def _h_test_fix(tool: str, args: dict[str, Any]) -> str:
    if tool == "run_command":
        return (
            "FAILED tests/test_calc.py::test_division_by_zero - ZeroDivisionError: division by zero"
        )
    if tool == "read_file":
        return "def safe_divide(a: float, b: float) -> float:\n    return a / b\n"
    return "ok"


register_task(
    BenchTask(
        id="test_fix",
        title="Fix division by zero in calculator",
        instructions="Diagnose failing safe_divide test and propose the fix.",
        user_query="tests/test_calc.py is failing. Find out why and provide the fix.",
        tools=[_get_exec_tool(), _get_common_file_tool()],
        tool_handler=_h_test_fix,
        checker=lambda resp, calls: (
            "ZeroDivisionError" in resp and ("b == 0" in resp or "try" in resp)
        ),
        expected_turns=2,
    )
)


# 3. api_refactor
def _h_api_refactor(tool: str, args: dict[str, Any]) -> str:
    if tool == "read_file":
        return "@app.route('/user')\ndef get_user():\n    uid = request.args.get('id')\n    return db.fetch(uid)"
    return "ok"


register_task(
    BenchTask(
        id="api_refactor",
        title="Refactor Flask route to Pydantic",
        instructions="Inspect user endpoint and refactor it with Pydantic request validation.",
        user_query="Inspect /user endpoint and refactor it with Pydantic model validation.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_api_refactor,
        checker=lambda resp, calls: "BaseModel" in resp or "pydantic" in resp.lower(),
        expected_turns=2,
    )
)


# 4. doc_generate
def _h_doc_gen(tool: str, args: dict[str, Any]) -> str:
    return "class PaymentLedger:\n    def record(self, amount: Decimal, currency: str) -> str:\n        '''Record transaction.'''\n"


register_task(
    BenchTask(
        id="doc_generate",
        title="Generate docstrings for payment ledger",
        instructions="Read payment ledger class and generate OpenAPI/Google style docstrings.",
        user_query="Generate OpenAPI documentation for PaymentLedger.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_doc_gen,
        checker=lambda resp, calls: "PaymentLedger" in resp and "amount" in resp,
        expected_turns=2,
    )
)


# 5. sql_query
def _h_sql(tool: str, args: dict[str, Any]) -> str:
    return "TABLE orders (id INT, customer_id INT, total_amount DECIMAL, created_at TIMESTAMP);"


register_task(
    BenchTask(
        id="sql_query",
        title="Write SQL aggregation query",
        instructions="Read orders schema and write query for top 5 customers by spending.",
        user_query="Write a query to find top 5 spending customers from orders table.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_sql,
        checker=lambda resp, calls: "GROUP BY" in resp.upper() and "LIMIT 5" in resp.upper(),
        expected_turns=2,
    )
)


# 6. log_analysis
def _h_log(tool: str, args: dict[str, Any]) -> str:
    return "2026-10-19 10:14:02 ERROR [worker-3] ConnectionPoolTimeout: Timeout after 30000ms connecting to redis://10.0.1.5:6379"


register_task(
    BenchTask(
        id="log_analysis",
        title="Root cause Redis connection timeout",
        instructions="Inspect server error log and identify the root cause service and port.",
        user_query="Check server logs and identify why worker-3 crashed.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_log,
        checker=lambda resp, calls: "redis" in resp.lower() and "6379" in resp,
        expected_turns=2,
    )
)


# 7. config_migrate
def _h_config(tool: str, args: dict[str, Any]) -> str:
    return "server:\n  port: 8080\n  host: 0.0.0.0\nlogging:\n  level: INFO\n"


register_task(
    BenchTask(
        id="config_migrate",
        title="Migrate yaml config to toml",
        instructions="Read server yaml configuration and produce equivalent toml format.",
        user_query="Convert server.yaml to server.toml.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_config,
        checker=lambda resp, calls: "[server]" in resp and "8080" in resp,
        expected_turns=2,
    )
)


# 8. json_filter
def _h_json(tool: str, args: dict[str, Any]) -> str:
    return json.dumps(
        [
            {"id": 1, "active": True, "score": 95},
            {"id": 2, "active": False, "score": 40},
            {"id": 3, "active": True, "score": 88},
        ]
    )


register_task(
    BenchTask(
        id="json_filter",
        title="Filter active high score records",
        instructions="Analyze data.json and report the average score of active users.",
        user_query="Calculate the average score of active users from data.json.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_json,
        checker=lambda resp, calls: "91.5" in resp or "91" in resp,
        expected_turns=2,
    )
)


# 9. cli_help
def _h_cli(tool: str, args: dict[str, Any]) -> str:
    return (
        "parser.add_argument('--threshold', type=float, default=0.5, help='Confidence threshold')\n"
    )


register_task(
    BenchTask(
        id="cli_help",
        title="Explain CLI threshold flag",
        instructions="Inspect cli parser and describe the default threshold flag.",
        user_query="What is the default value and type of --threshold in cli.py?",
        tools=[_get_common_file_tool()],
        tool_handler=_h_cli,
        checker=lambda resp, calls: "0.5" in resp and "float" in resp.lower(),
        expected_turns=2,
    )
)


# 10. regex_builder
def _h_regex(tool: str, args: dict[str, Any]) -> str:
    return "Sample valid emails: user@example.com, alice.smith+tag@domain.co.uk"


register_task(
    BenchTask(
        id="regex_builder",
        title="Construct RFC 5322 email regex",
        instructions="Read sample email fixtures and provide a robust email validation regex.",
        user_query="Provide a python regex for validating emails with tag support.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_regex,
        checker=lambda resp, calls: "re.compile" in resp or "@" in resp,
        expected_turns=2,
    )
)


# 11. lint_fix
def _h_lint(tool: str, args: dict[str, Any]) -> str:
    if tool == "run_command":
        return "src/app.py:5:1: F401 'os' imported but unused\nsrc/app.py:10:80: E501 line too long"
    return "import os\n\ndef run():\n    print('hello world')\n"


register_task(
    BenchTask(
        id="lint_fix",
        title="Resolve unused import lint error",
        instructions="Run linter and fix the unused import warning in app.py.",
        user_query="Run ruff check and explain how to fix the errors reported.",
        tools=[_get_exec_tool(), _get_common_file_tool()],
        tool_handler=_h_lint,
        checker=lambda resp, calls: "unused import" in resp.lower() or "f401" in resp.lower(),
        expected_turns=2,
    )
)


# 12. git_conflict
def _h_git(tool: str, args: dict[str, Any]) -> str:
    return "<<<<<<< HEAD\nCACHE_TTL = 3600\n=======\nCACHE_TTL = 1800\n>>>>>>> feature/ttl\n"


register_task(
    BenchTask(
        id="git_conflict",
        title="Resolve git merge conflict in cache ttl",
        instructions="Inspect conflict markers in settings.py and explain the two conflicting branches.",
        user_query="Inspect settings.py and identify the conflicting CACHE_TTL values.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_git,
        checker=lambda resp, calls: "3600" in resp and "1800" in resp,
        expected_turns=2,
    )
)


# 13. mock_gen
def _h_mock(tool: str, args: dict[str, Any]) -> str:
    return "class StripeClient:\n    def create_charge(self, customer_id: str, amount_cents: int) -> dict:\n        pass\n"


register_task(
    BenchTask(
        id="mock_gen",
        title="Generate pytest mock for StripeClient",
        instructions="Inspect StripeClient interface and generate a pytest mock fixture.",
        user_query="Create a unittest.mock fixture for StripeClient.create_charge.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_mock,
        checker=lambda resp, calls: (
            "create_charge" in resp and ("mock" in resp.lower() or "fixture" in resp.lower())
        ),
        expected_turns=2,
    )
)


# 14. dep_audit
def _h_dep(tool: str, args: dict[str, Any]) -> str:
    return "requests==2.25.0\npydantic==1.8.2\nurllib3==1.26.4\n"


register_task(
    BenchTask(
        id="dep_audit",
        title="Audit legacy requirements.txt",
        instructions="Inspect requirements.txt and list dependencies requiring security updates.",
        user_query="Audit requirements.txt for outdated major versions.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_dep,
        checker=lambda resp, calls: "pydantic" in resp.lower() and "requests" in resp.lower(),
        expected_turns=2,
    )
)


# 15. security_scan
def _h_sec(tool: str, args: dict[str, Any]) -> str:
    return "def query_user(username: str):\n    sql = f'SELECT * FROM users WHERE name = \"{username}\"'\n    return db.execute(sql)\n"


register_task(
    BenchTask(
        id="security_scan",
        title="Identify SQL injection vulnerability",
        instructions="Scan user database query function and explain the vulnerability.",
        user_query="Review db/users.py for security vulnerabilities.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_sec,
        checker=lambda resp, calls: (
            "sql injection" in resp.lower() or "parameterized" in resp.lower()
        ),
        expected_turns=2,
    )
)


# 16. perf_opt
def _h_perf(tool: str, args: dict[str, Any]) -> str:
    return "def find_common(list_a: list[int], list_b: list[int]) -> list[int]:\n    # O(N*M)\n    return [x for x in list_a if x in list_b]\n"


register_task(
    BenchTask(
        id="perf_opt",
        title="Optimize list intersection from O(N*M) to O(N)",
        instructions="Inspect find_common function and optimize its time complexity.",
        user_query="Optimize find_common in utils/algo.py to run in O(N+M) time.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_perf,
        checker=lambda resp, calls: "set" in resp.lower(),
        expected_turns=2,
    )
)


# 17. schema_validate
def _h_schema(tool: str, args: dict[str, Any]) -> str:
    return "from pydantic import BaseModel, PositiveInt\n\nclass Order(BaseModel):\n    id: int\n    quantity: PositiveInt\n"


register_task(
    BenchTask(
        id="schema_validate",
        title="Explain validation rules on Order schema",
        instructions="Inspect order schema and describe the quantity constraints.",
        user_query="What constraint is placed on quantity in the Order model?",
        tools=[_get_common_file_tool()],
        tool_handler=_h_schema,
        checker=lambda resp, calls: (
            "positive" in resp.lower() or "> 0" in resp or "greater than zero" in resp.lower()
        ),
        expected_turns=2,
    )
)


# 18. error_handling
def _h_err(tool: str, args: dict[str, Any]) -> str:
    return "def fetch_data(url: str):\n    resp = requests.get(url, timeout=5)\n    return resp.json()\n"


register_task(
    BenchTask(
        id="error_handling",
        title="Add retry mechanism to HTTP client",
        instructions="Inspect fetch_data and propose retry handling for transient HTTP 5xx errors.",
        user_query="Add retry logic to fetch_data in client.py.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_err,
        checker=lambda resp, calls: "retry" in resp.lower() or "status_code" in resp.lower(),
        expected_turns=2,
    )
)


# 19. multi_step_math
def _h_math(tool: str, args: dict[str, Any]) -> str:
    return json.dumps(
        {
            "starting_balance": "1000.00",
            "transactions": [
                {"amount": "+250.50", "type": "credit"},
                {"amount": "-120.25", "type": "debit"},
                {"amount": "-30.25", "type": "debit"},
            ],
        }
    )


register_task(
    BenchTask(
        id="multi_step_math",
        title="Reconcile ending account balance",
        instructions="Read transactions ledger and calculate the exact ending balance.",
        user_query="Calculate the reconciled ending balance from transactions.json.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_math,
        checker=lambda resp, calls: "1100.00" in resp or "1100" in resp,
        expected_turns=2,
    )
)


# 20. code_review
def _h_review(tool: str, args: dict[str, Any]) -> str:
    return "diff --git a/auth.py b/auth.py\n+import hashlib\n+def hash_pwd(pwd: str) -> str:\n+    return hashlib.md5(pwd.encode()).hexdigest()\n"


register_task(
    BenchTask(
        id="code_review",
        title="Code review security warning on MD5 password hashing",
        instructions="Review pull request git diff and identify password security flaws.",
        user_query="Perform a security code review on the diff in auth.py.",
        tools=[_get_common_file_tool()],
        tool_handler=_h_review,
        checker=lambda resp, calls: (
            "md5" in resp.lower()
            and (
                "bcrypt" in resp.lower()
                or "argon" in resp.lower()
                or "salt" in resp.lower()
                or "insecure" in resp.lower()
            )
        ),
        expected_turns=2,
    )
)


def get_all_tasks() -> list[BenchTask]:
    return list(TASKS)


def get_task_by_id(task_id: str) -> BenchTask | None:
    for t in TASKS:
        if t.id == task_id:
            return t
    return None
