from __future__ import annotations

import re
from typing import TypeAlias


RegexConfig: TypeAlias = list[dict[str, str]]
SearchResult: TypeAlias = list[dict[str, str | list[str]]]


def normalize_value(value: str) -> str:
    """清理匹配结果，并将中文日期转换为 YYYY-MM-DD。"""
    value = value.strip()
    date_match = re.fullmatch(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        value,
    )
    if date_match is None:
        return value

    year, month, day = date_match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def reg_search(text: str, regex_list: RegexConfig) -> SearchResult:
    """按照正则配置依次提取文本内容。"""
    results: SearchResult = []

    for regex_config in regex_list:
        item: dict[str, str | list[str]] = {}

        for field_name, pattern in regex_config.items():
            compiled_pattern = re.compile(pattern, flags=re.DOTALL)
            if compiled_pattern.groups > 1:
                raise ValueError(
                    f"{field_name!r} 的正则最多只能有一个捕获组，"
                    "其他分组请写成 (?:...)"
                )

            group_number = 1 if compiled_pattern.groups == 1 else 0
            values = [
                normalize_value(match.group(group_number))
                for match in compiled_pattern.finditer(text)
            ]

            if len(values) == 1:
                item[field_name] = values[0]
            else:
                item[field_name] = values

        results.append(item)

    return results


def main() -> None:
    text = """
    标的证券：本期发行的证券为可交换为发行人所持中国长江电力股份
    有限公司股票（股票代码：600900.SH，股票简称：长江电力）的可交换公司债
    券。
    换股期限：本期可交换公司债券换股期限自可交换公司债券发行结束
    之日满 12 个月后的第一个交易日起至可交换债券到期日止，即 2023 年 6 月 2
    日至 2027 年 6 月 1 日止。
    """

    regex_list = [
        {
            "标的证券": r"股票代码[：:\s]*([0-9]{6}\.(?:SH|SZ|BJ))",
            "换股期限": r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        }
    ]

    print(reg_search(text, regex_list))


if __name__ == "__main__":
    main()
