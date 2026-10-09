"""Read-only inventory of local admission PDF headings."""

import re
import sys
from pathlib import Path

import pymupdf

for path in Path("data/raw").glob("*.pdf"):
    if len(sys.argv) > 1 and sys.argv[1] not in path.name:
        continue
    document = pymupdf.open(path)
    print("\nFILE", path.name)
    for index, page in enumerate(document):
        text = page.get_text(sort=True)
        if len(sys.argv) > 2 and index + 1 in [int(value) for value in sys.argv[2:]]:
            print("FULL PAGE", index + 1, text)
            continue
        headings = [
            line.strip()
            for line in text.splitlines()
            if re.match(r"^(Điều\s+\d+|\d{1,2}\.\s|\d{1,2}\.\d+\.?\s|Phụ lục|[IVX]+\.\s|Bảng\s)", line.strip())
        ]
        if headings:
            print(index + 1, " | ".join(headings)[:1600])
