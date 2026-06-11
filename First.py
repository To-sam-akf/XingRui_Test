from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://www.chinamoney.com.cn"
CONDITION_URL = f"{BASE_URL}/ags/ms/cm-u-bond-md/BondBaseInfoSearchConditionEN"
LIST_URL = f"{BASE_URL}/ags/ms/cm-u-bond-md/BondMarketInfoListEN"
REFERER = f"{BASE_URL}/english/bdInfo/"

BOND_TYPE = "Treasury Bond"
ISSUE_YEAR = "2023"
PAGE_SIZE = 15
MAX_RETRIES = 3

OUTPUT_COLUMNS = {
    "ISIN": "isin",
    "Bond Code": "bondCode",
    "Issuer": "entyFullName",
    "Bond Type": "bondType",
    "Issue Date": "issueStartDate",
    "Latest Rating": "debtRtng",
}


def create_session() -> requests.Session:
    """创建一个复用连接和请求头的 HTTP 会话。"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
            ),
            "Referer": REFERER,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }
    )
    return session


def post_form(
    session: requests.Session,
    url: str,
    data: dict[str, str] | None = None,
) -> dict[str, Any]:
    """发送表单请求，并返回通过业务状态校验的 JSON 数据。"""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(url, data=data or {}, timeout=30)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(attempt)
                continue
            break

        reply_code = str(payload.get("head", {}).get("rep_code", ""))
        if reply_code != "200":
            message = payload.get("head", {}).get("rep_message", "unknown error")
            raise RuntimeError(f"ChinaMoney API error {reply_code}: {message}")
        return payload

    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {url}") from last_error


def get_bond_type_code(session: requests.Session, display_name: str) -> str:
    """根据页面展示名称查询网站内部的债券类型代码。"""
    payload = post_form(session, CONDITION_URL)
    bond_types = payload.get("data", {}).get("bondType", [])

    for item in bond_types:
        if item.get("bondDisplayType") == display_name:
            return str(item["bondTypeCode"])

    raise ValueError(f"Bond type not found: {display_name}")


def fetch_bonds(
    session: requests.Session,
    bond_type: str,
    issue_year: str,
) -> list[dict[str, Any]]:
    """按债券类型和发行年份获取全部分页数据。"""
    bond_type_code = get_bond_type_code(session, bond_type)
    rows: list[dict[str, Any]] = []
    page_no = 1
    page_total = 1
    expected_total = 0

    while page_no <= page_total:
        payload = post_form(
            session,
            LIST_URL,
            {
                "pageNo": str(page_no),
                "pageSize": str(PAGE_SIZE),
                "isin": "",
                "bondCode": "",
                "issueEnty": "",
                "bondType": bond_type_code,
                "couponType": "",
                "issueYear": issue_year,
                "rtngShrt": "",
                "bondSpclPrjctVrty": "",
            },
        )

        page_data = payload.get("data", {})
        result_list = page_data.get("resultList", [])
        if not isinstance(result_list, list):
            raise RuntimeError("Unexpected resultList format returned by ChinaMoney")

        rows.extend(result_list)
        page_total = int(page_data.get("pageTotal", 1))
        expected_total = int(page_data.get("total", len(rows)))
        print(f"Fetched page {page_no}/{page_total}: {len(result_list)} records")

        page_no += 1
        time.sleep(0.2)

    if len(rows) != expected_total:
        raise RuntimeError(
            f"Incomplete result: expected {expected_total} records, got {len(rows)}"
        )

    return rows


def save_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """提取指定字段并保存为可被 Excel 正常读取的 CSV 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(OUTPUT_COLUMNS))
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    column_name: row.get(source_name) or "---"
                    for column_name, source_name in OUTPUT_COLUMNS.items()
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download 2023 Treasury Bond data from ChinaMoney."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("treasury_bonds_2023.csv"),
        help="output CSV path (default: treasury_bonds_2023.csv)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with create_session() as session:
        rows = fetch_bonds(session, BOND_TYPE, ISSUE_YEAR)

    save_csv(rows, args.output)
    print(f"Saved {len(rows)} records to {args.output.resolve()}")


if __name__ == "__main__":
    main()
