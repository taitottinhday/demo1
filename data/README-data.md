# Bộ dữ liệu tuyển sinh HUST K71 — nhập học 2026

Bản chuẩn hóa kỹ thuật `k71-2026-v2`, tạo từ 6 PDF chuẩn trong `raw/`, dùng chung `source_catalog.json` với ứng dụng sau merge. Chủ dự án xác nhận các nguồn áp dụng cho K71 nhập học năm 2026. Xác nhận này không đổi năm của dữ kiện lịch sử, không mở rộng đối tượng của từng điều khoản, không thay thế việc đối chiếu kết quả OCR/bảng.

## Đọc nhanh trước khi triển khai

**Hiện đủ để backend nhập dữ liệu và AI phát triển retrieval/RAG/rerank. Chưa phải bộ kiến thức đã duyệt hoàn toàn để nghiệm thu tư vấn tuyển sinh.** Chủ dự án sẽ tiếp tục chuẩn hóa và đối chiếu nội dung ở lần cập nhật tiếp theo. Các bên có thể triển khai ngay theo schema hiện có, đồng thời giữ các trạng thái chất lượng và khả năng thay phiên bản data.

| Tổng quan bản hiện tại | Số lượng |
|---|---:|
| PDF nguồn / trang | 6 / 131 |
| Bảng trích xuất / trang OCR | 79 / 20 |
| Bản ghi chuẩn / chunks | 1.132 / 1.065 |
| Chương trình tuyển sinh | 68 |
| Dữ kiện điểm chuẩn lịch sử 2024/2025 | 358 |

Thống kê này mô tả snapshot `k71-2026-v2`; đọc `processed/release.json` để biết số liệu thực tế. Số bản ghi theo chủ đề có thể chồng lấp, không cộng thành tổng. Đã kiểm tra schema, ID, checksum toàn bộ snapshot/pipeline, liên kết bảng/nguồn, độ phủ trang và dữ kiện mốc; kiểm tra kỹ thuật không chứng minh accuracy ≥85% hoặc nguồn đã được cán bộ duyệt.

Thứ tự đọc dành cho người triển khai và agent:

1. README này: hiểu phạm vi, chất lượng và hợp đồng dữ liệu.
2. `processed/release.json` và `manifests/sources.json`: xác định snapshot, nguồn và checksum.
3. `schemas/record.schema.json`, `schemas/chunk.schema.json`: kiểm tra đầu vào.
4. `normalized/records.jsonl` cho backend; `processed/chunks.jsonl` cho AI.
5. `quality/report.md`, `quality/issues.jsonl`: biết những phần còn cần duyệt.

## Phân công và các giới hạn hiện tại

| Bên phụ trách | Có thể làm ngay | Cần giữ rõ |
|---|---|---|
| Data | Đối chiếu nguồn, sửa OCR/ô bảng, bổ sung dữ kiện, phát hành snapshot | Bản gốc, dẫn chứng và lịch sử thay đổi |
| Backend | Import records, tra cứu chương trình, hiển thị citations, nối dịch vụ retrieval | Schema, phiên bản, quyền dùng bản ghi và cơ chế cập nhật |
| AI | Tạo embedding, hybrid retrieval, rerank, kiểm tra grounding | Bộ lọc phạm vi/năm/đối tượng, ngữ cảnh cha và trạng thái chất lượng |
| Người duyệt | Kiểm tra số liệu, điều kiện, công thức, ngoại lệ | Chỉ xác nhận những mục đã thực sự đối chiếu |

- `application_steps.jsonl` là văn bản có nguồn được nhóm theo chủ đề, **chưa phải checklist hoàn chỉnh có schema riêng cho từng bước, giấy tờ và deadline**. Không giả định các trường đó đã có hoặc tự sinh chúng khi nguồn chưa đủ.
- Tương tự, các file quy định chứa cả section, hàng bảng và bản ghi định lượng. Không coi tất cả là rule có thể tự tính điểm/học phí hoặc kiểm tra đủ điều kiện.
- 19 trang TSA và bảng ảnh ngoại ngữ trang PDF 17 đã OCR nhưng cần đối chiếu. Ô gộp chưa giải quyết giữ nguyên null; không tự điền từ hàng trên.
- `admissions_facts_2026.json` và `cutoffs_2026_summary.json` từ main giữ một số dữ kiện web tóm tắt năm 2026, chưa có bản lưu web đầy đủ. Chúng nằm riêng với `records.jsonl` (điểm chuẩn lịch sử 2024/2025). Không gộp năm hoặc suy rộng thành bảng điểm đầy đủ. Học bổng chi tiết vẫn thiếu nguồn.
- Chưa có embedding, vector index, model reranker hay kết quả đánh giá chatbot trên snapshot này. Corpus là đầu vào để các bên triển khai các thành phần đó.
- `eval/retrieval-dev.jsonl` có 25 ca development chỉ cho `normalized_pdf_records_only`, gắn `dataset_release`; các candidate ID chỉ là đoạn cùng vùng trang, chưa phải nhãn relevance đã duyệt. Ca thiếu điểm chuẩn 2026 là kỳ vọng cho corpus PDF này, không áp dụng cho facts web riêng của runtime. Không dùng kết quả trên bộ này để tuyên bố đạt KPI đề tài.
- Việc backend hiện có đọc PDF/`knowledge.json` không đồng nghĩa đã dùng bộ chuẩn này: bên backend cần viết adapter/importer chủ động cho records/chunks. Người phụ trách Data không thay đổi code backend trong lần bàn giao này.

## Hướng dẫn tích hợp cho backend và agent

1. Validate schema và checksum trước import; lưu mã snapshot `release` cùng SHA nguồn.
2. Import kho records một lần, lập khóa tra cứu theo `record_id`; tải nguồn theo `source_id`. Các view chủ đề không được nhập như bản ghi mới.
3. Phân nhánh theo `record_type`; trường không xuất hiện và giá trị null đều phải được xử lý. Không ép mọi record thành cấu trúc program/cutoff.
4. Nối chunk với record cha bằng `record_id` và đọc `related_context_record_ids` khi cần. Chưa có quy ước API/DB bắt buộc; chọn kiến trúc backend phù hợp nhưng giữ được hợp đồng đầu vào.
5. Chặn bản ghi có `answer_eligible=false` trong luồng tự trả lời; nếu trường này thiếu thì xử lý như chưa đủ điều kiện, không mặc định được phép. Bản `true` vẫn cần kiểm tra nội dung, ngữ cảnh và chính sách sử dụng nguồn chưa được cán bộ duyệt.
6. Phục vụ citation theo từng nguồn và trang, thay vì cố định một PDF chung. Bản ghi bảng cần giữ vị trí hàng/cột và chú thích.
7. Bắt đầu với ngữ cảnh K71/2026, nhưng hỏi rõ hệ đào tạo, chương trình, phương thức hoặc đối tượng nếu chúng quyết định đáp án. Khi thiếu căn cứ, trả trạng thái làm rõ/fallback/handover.

Ví dụ import tối thiểu; đây là đọc corpus, không phải chính sách cho phép trả lời:

```python
import json
from pathlib import Path

records = {}
for line in Path("data/normalized/records.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        record = json.loads(line)
        records[record["record_id"]] = record

programs = [r for r in records.values() if r["record_type"] == "program"]
```

## Cập nhật data lần tới và mức ảnh hưởng

Định hướng cho schema v1 là giữ tên trường, kiểu dữ liệu và ý nghĩa đang dùng; ưu tiên bổ sung trường tùy chọn. Đây là quy ước bàn giao, không phải lời đảm bảo rằng mọi phiên bản tương lai đều tương thích. Khi đổi cấu trúc hoặc ý nghĩa trường, Data phải ghi rõ thay đổi và hướng dẫn chuyển đổi trước khi bên tiêu thụ cập nhật.

| Loại cập nhật | Tác động dự kiến |
|---|---|
| Sửa chữ OCR, số liệu, nhãn hoặc trạng thái duyệt | Nạp lại records/views; cập nhật các chunks liên quan, index và cache |
| Bổ sung nguồn hoặc dữ kiện cùng schema | Import nguồn/bản ghi mới; cập nhật retrieval và citations |
| Bổ sung checklist/rule có cấu trúc mới | Adapter/chức năng tương ứng cần đọc thêm trường hoặc loại bản ghi mới |
| Đổi tên, kiểu hoặc ý nghĩa trường | Cần migration/adapter; công bố thay đổi trước bàn giao |
| Đổi model embedding hoặc cách chia chunk | Dựng lại phần index bị ảnh hưởng; không mặc định dùng lại vector cũ |

**ID không phải định danh nghiệp vụ cố định qua mọi lần sửa.** `record_id` chứa SHA nguồn, vị trí và hash nội dung; `chunk_id` phụ thuộc record và nội dung chunk. Sửa nội dung/vị trí hoặc thay PDF có thể đổi ID. Dùng chúng trong phạm vi snapshot; không dùng làm khóa nghiệp vụ cố định cho hồ sơ, người dùng hoặc ticket. Với chương trình, có thể tra cứu theo mã chương trình kết hợp trường/năm/phạm vi, nhưng không coi một mã là bất biến cho mọi năm.

Khuyến nghị cập nhật bằng snapshot: nạp bản mới vào vùng riêng, kiểm tra schema/checksum/liên kết, dựng index, rồi chuyển phiên bản phục vụ. Giữ bản cũ để truy nguồn câu trả lời đã lưu và để rollback. Không trộn records của bản mới với chunks của bản cũ; vô hiệu hóa cache theo phiên bản kho. Nếu chỉ upsert theo ID mới mà không xử lý ID cũ, dữ kiện cũ có thể tiếp tục được truy xuất.

Khi bàn giao bản tiếp theo, ghi mã phiên bản mới cùng nguồn đã đổi, dữ kiện sửa, trạng thái đã duyệt và thay đổi schema; không ghi đè một gói đã bàn giao mà vẫn gọi nó là snapshot cũ. Script normalizer hiện còn dùng hằng `VERSION = "k71-2026-v2"`; người phát hành phải đổi mã này trước lần phát hành dữ liệu mới. Không chạy lại normalizer để áp dụng duyệt thủ công mà chưa lưu cơ chế giữ các quyết định duyệt: script hiện tái tạo dữ liệu và trạng thái trích xuất từ PDF.

## Các file bàn giao

| File/thư mục | Mục đích |
|---|---|
| `manifests/sources.json` | Nguồn, URL, SHA256, phạm vi K71, hiệu lực đã đọc được, nguồn web còn thiếu bản lưu |
| `extracted/<source_id>/page-*.json` | Văn bản gốc, văn bản OCR, block và vị trí bảng của từng trang |
| `extracted/<source_id>/page-*.ocr.json` | OCR vie+eng, confidence, vị trí từ; cache theo SHA256 PDF |
| `extracted/<source_id>/tables.jsonl` | Bảng đầy đủ, giữ nguyên ô null và tọa độ |
| `normalized/records.jsonl` | Kho bản ghi duy nhất; các file theo chủ đề là các view, có thể trùng ID giữa view |
| `normalized/knowledge.md` | Bản đọc thuận tiện để rà soát kiến thức, kèm chủ đề, phạm vi, trạng thái và trang nguồn |
| `normalized/programs.jsonl` | Chương trình, mã ngành, chỉ tiêu, phương thức, tổ hợp và ghi chú đã ghép dòng bảng |
| `normalized/cutoffs.jsonl` | Bản ghi điểm chuẩn lịch sử có score/scale/year/method; kèm mục văn bản liên quan |
| `normalized/tuition_rules.jsonl` | Quy định học phí, dòng bảng đơn giá và quy đổi tín chỉ; amount_vnd chỉ có khi ô số rõ ràng |
| `processed/chunks.jsonl` | Corpus cho BM25, embedding, rerank; nối về records bằng record_id |
| `processed/release.json` | Thống kê và checksum phiên bản |
| `quality/report.md`, `quality/issues.jsonl` | Giới hạn và vấn đề cần đối chiếu |
| `quality/page_inventory.jsonl` | Kiểm kê mọi trang, kể cả scan và bảng ảnh |
| `schemas/*.schema.json` | JSON Schema cho record/chunk |
| `eval/retrieval-dev.jsonl` | Câu hỏi development và dẫn chứng kỳ vọng; chưa là tập nghiệm thu KPI |

## Những nhóm hữu ích được bổ sung

Ngoài ngành, chỉ tiêu, học phí, điểm chuẩn và học bổng:

- `admission_rules`: đối tượng, điều kiện, XTTN từng diện, chứng chỉ quốc tế, hồ sơ năng lực và phỏng vấn.
- `application_steps`: đăng ký nguyện vọng, nộp hồ sơ, các kênh đăng ký và lịch có trong nguồn.
- `scoring_rules`: tổ hợp, tính/quy đổi điểm, thưởng, ưu tiên và tiêu chí phụ. Công thức phải đọc đầy đủ điều kiện.
- `enrollment_rules`: công bố kết quả, xác nhận nhập học, bảo lưu và xét tuyển bổ sung.
- `exam_rules`: quy chế TSA, nội dung/hình thức thi, đăng ký, trách nhiệm, xử lý vi phạm và các điều khoản thi khác. OCR cần duyệt trước dùng làm kết luận.
- `training_models`: mô hình cử nhân, tích hợp kỹ sư/thạc sĩ, ELITECH, tài năng, liên kết quốc tế, ngôn ngữ giảng dạy.
- `language_rules`: điều kiện tuyển sinh, phân loại đầu vào, miễn học, lộ trình học, chuẩn đầu ra và quy đổi chứng chỉ. Đối tượng của quy định K71 ngoại ngữ là sinh viên, không mặc định là điều kiện được trúng tuyển.
- `contacts`: mã trường, địa chỉ, website, điện thoại và liên hệ công khai trong tài liệu.
- `student_support`: hỗ trợ, quyền/trách nhiệm, khiếu nại và các mục liên quan được nguồn đề cập.
- `institutional_rules`: nội dung còn lại, gồm tổ chức và hiệu lực; không tự động coi tất cả là nội dung tư vấn ứng viên.

Nhãn chủ đề được gán bằng quy tắc từ khóa: dùng để lấy ứng viên truy xuất, không dùng như phân loại đã được cán bộ duyệt. Nguồn tổng quan có học bổng trang PDF 25–26. Dữ kiện web 2026 chỉ có bản tóm tắt riêng, chưa có bản lưu toàn trang và nội dung học bổng chi tiết.

## Hợp đồng sử dụng

JSONL: mỗi dòng là một JSON UTF-8, một bản ghi. Import `records.jsonl` một lần; các file chủ đề là view và không được cộng lại như dữ liệu độc lập. `record_type=program/cutoff` có trường định lượng; `section` là văn bản quy định; `table_row` là hàng đã gắn nhãn; `table` là grid để kiểm tra, không phải dữ kiện tự động tính toán.

`cohort=K71` là ngữ cảnh triển khai. `admission_year`, `cutoff_year`, `academic_year`, `historical`, `mentioned_years` có nghĩa khác nhau. Điểm chuẩn 2024/2025 không dùng để trả lời điểm chuẩn 2026; năm được viện dẫn trong phần căn cứ không đồng nghĩa với hiệu lực.

`scope` là bộ lọc sơ bộ ở cấp mục/trang. `mixed_training_levels`, `mixed_or_other_admissions`, `continuing_or_second_degree` cần đọc điều khoản hoặc hỏi rõ hệ; không dùng làm mặc định cho thí sinh THPT. `audience=student` dùng cho quy định ngoại ngữ sau nhập học.

`answer_eligible` chỉ là chất lượng trích xuất kỹ thuật. `true` không có nghĩa đã được cán bộ duyệt. `false` dành cho OCR và bảng chưa giải quyết ô gộp: có thể index cho công cụ rà soát nhưng không dùng để tự đưa kết luận. `staff_reviewed=false` giữ nguyên cho đến khi có người duyệt thực tế. Độ tin cậy OCR không phải độ chính xác nội dung.

ID có SHA nguồn và hash nội dung; thay một PDF chỉ thay ID của nguồn đó. OCR cache được dùng lại khi SHA không đổi. `evidence.quote` là text gốc đã làm sạch hoặc ô bảng, còn `text` có thể là câu mô tả được ghép từ các trường. Với bảng phải mở `evidence.location.table_id/table_rows` để kiểm tra liên kết cột và dòng; không coi riêng quote số là đủ hỗ trợ mọi kết luận.

`page_start/page_end` là trang PDF bắt đầu từ 1. `printed_page=null` vì chưa xác minh nhãn trang in. Chunk trỏ về section cha; nếu `context_required=true`, đọc record cha để giữ điều kiện và ngoại lệ. Chia theo khoảng 450 từ, không tuyên bố là 450 token; kiểm tra bằng tokenizer của model trước index.

`related_context_record_ids` nối dòng bảng với đoạn văn lân cận cùng phạm vi; cần đọc để lấy đơn vị, điều kiện và chú thích. Các link này là ứng viên ngữ cảnh, vẫn cần kiểm tra nội dung thực sự liên quan.

## RAG và rerank

1. Chọn đúng năm, hệ, đối tượng và loại câu hỏi; hỏi rõ khi thiếu ngữ cảnh.
2. Index `retrieval_text` cho embedding; BM25 dùng text có dấu và có thể thêm bản không dấu. Giữ text gốc để hiển thị.
3. Truy xuất BM25 + vector, gộp RRF rồi rerank cặp `(question, retrieval_text)`.
4. Với câu nhiều lượt bổ sung ngữ cảnh do người dùng xác nhận vào query; không nhập hồ sơ cá nhân vào corpus công khai.
5. Đọc record cha, lọc answer_eligible, kiểm tra năm/đơn vị/đối tượng và nguồn mâu thuẫn trước trả lời.
6. Dẫn nguồn bằng source_id, SHA, URL và trang PDF. Thiếu căn cứ thì hỏi rõ hoặc handover.

Chưa tạo embedding hay gắn với một database/model cụ thể. Bên AI có thể bắt đầu benchmark bằng corpus này; bên backend nhập dữ liệu bằng schema mà không cần sửa luồng trích xuất.

## Tái tạo và kiểm tra

Dependencies riêng cho Data/OCR ở `requirements-data.txt`; không sửa requirements của backend. Windows cần wheel tesserocr phù hợp Python/kiến trúc máy từ dự án tesserocr-windows_build; Linux cần thư viện Tesseract/Leptonica tương ứng. Mô hình ngôn ngữ lấy từ tesseract-ocr/tessdata_fast; setup ghi URL và checksum vào data/tools/tessdata/models.json.

```powershell
.venv/Scripts/python.exe scripts/setup_data_ocr.py
.venv/Scripts/python.exe -X utf8 scripts/normalize_admissions_data.py
.venv/Scripts/python.exe -X utf8 scripts/build_retrieval_dev.py
.venv/Scripts/python.exe -X utf8 scripts/validate_admissions_data.py --seal --package
```

Kiểm tra snapshot đã có (chỉ đọc, không cần OCR/model, không tạo ZIP):

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-data-validation.txt
.venv/Scripts/python.exe -X utf8 scripts/validate_admissions_data.py
```

`--skip-ocr` không phát hành release đủ 131 trang: pipeline dừng khi gặp trang cần OCR. PDF gốc và sources.md không bị ghi đè. Chỉ các thư mục đầu ra liệt kê ở trên được tái tạo; dữ liệu chuẩn không dùng tên `knowledge.json` đang phục vụ backend MVP. Chỉ dùng `--seal` sau khi hoàn thành build và kiểm tra nội dung; checksum chứng minh tính toàn vẹn, không chứng minh nội dung đúng.

Lưu bộ release cùng nhau khi bàn giao. Git theo dõi nguồn công khai, extracted, schema, normalized, quality và corpus; ZIP trong `data/releases/`, tools, database và dữ liệu ứng viên vẫn bị ignore. CI validate snapshot đã commit bằng chế độ chỉ đọc; không cần cài OCR. Không đưa dữ liệu phiên ứng viên hoặc database vào gói bàn giao.

## Thay đổi v2 và ranh giới trước tích hợp AI

- Catalog là metadata chung. Sáu PDF dùng tên chuẩn như runtime; năm bản sao trùng được bỏ. `source_id` corpus giữ nguyên, manifest bổ sung `runtime_source_id` để adapter nối đúng nguồn. Evidence chuyển sang đường dẫn PDF chuẩn.
- Schema v2 bắt buộc metadata nguồn/trang/phạm vi/đối tượng/chất lượng trên cả record và chunk. OCR và bảng chưa duyệt không được đánh dấu đủ điều kiện trả lời. Không nâng trạng thái duyệt tự động.
- `checksum_format=sha256_binary_pdf_utf8_lf_text`: PDF băm nguyên byte; file văn bản chuẩn hóa CRLF thành LF trước SHA256 để Windows/Linux kiểm tra cùng một snapshot. `.gitattributes` cố định LF cho dữ liệu và script phát hành.
- Ngày 07/09/2026 của quy định ngoại ngữ được giữ dưới dạng ghi chú chưa xác minh; `publication_date=null`. Hiệu lực học kỳ 1 năm học 2026–2027 giữ theo Điều 7, không còn cảnh báo sai về sources.md cũ.
- Gói bàn giao gồm cả catalog, facts tóm tắt, bộ golden 20 ca và bộ development 25 ca. Hai bộ chưa phải holdout, chưa đo chất lượng chatbot trên snapshot v2.
- Runtime vẫn đọc PDF và facts theo logic hiện có. Chưa nối records/chunks, chưa tạo embedding hoặc thay retrieval/LLM. Bước AI kế tiếp cần adapter, lọc chất lượng/phạm vi và benchmark riêng.
