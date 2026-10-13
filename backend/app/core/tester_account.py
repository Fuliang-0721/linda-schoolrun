UNCLASSIFIED_TESTER_TYPE = ""
DEFAULT_TESTER_TYPE = "ordinary"

TESTER_TYPE_LABELS = {
    UNCLASSIFIED_TESTER_TYPE: "未分类账号",
    "ordinary": "普通测试账号",
    "advanced": "高级测试账号",
    "donor": "贡献者账号",
    "pioneer": "先锋测试账号",
}
VALID_TESTER_TYPES = {"ordinary", "advanced", "donor", "pioneer"}

VALID_ACCOUNT_STATUSES = {"active", "banned"}


def normalize_tester_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized or normalized not in VALID_TESTER_TYPES:
        return DEFAULT_TESTER_TYPE
    return normalized


def normalize_stored_tester_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in VALID_TESTER_TYPES:
        return UNCLASSIFIED_TESTER_TYPE
    return normalized


def tester_type_label(value: str | None) -> str:
    return TESTER_TYPE_LABELS[normalize_stored_tester_type(value)]


def normalize_account_status(value: str | None) -> str:
    normalized = (value or "active").strip().lower()
    if normalized not in VALID_ACCOUNT_STATUSES:
        return "active"
    return normalized
