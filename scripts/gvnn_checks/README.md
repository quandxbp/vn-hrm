# Script kiểm tra edu_gvnn

Chạy bằng Odoo shell trên DB `gvnn`. Mỗi script tự tạo dữ liệu thử, in `PASS`/`FAIL` và `TOTAL n / n`, rồi rollback và đặt lại sequence về 1, nên DB không đổi.

| Script | Kiểm tra | Kết quả mong đợi |
|---|---|---|
| `check_phase3_tuition.py` | phiếu thu/chi, số dư, cảnh báo học phí, in phiếu | 28 / 28 |
| `check_phase4_payroll.py` | kỳ lương, chốt/khoá/mở khoá, đối soát Agency, in PDF | 51 / 51 |
| `check_phase5_alerts_reports.py` | cảnh báo tuần, báo cáo tài chính, export xlsx | 47 / 47 |
| `check_phase6_import.py` | import `TỔNG HỢP_GVNN.xlsx` (cần file ở `/tmp/gvnn.xlsx` trong container) | in bảng đối chiếu, xem `docs/GVNN_PLAN.md` mục 5 |

```sh
# từ thư mục gốc repo, Git Bash trên Windows
MSYS_NO_PATHCONV=1 docker compose cp scripts/gvnn_checks/check_phase4_payroll.py web:/tmp/check.py
MSYS_NO_PATHCONV=1 docker compose exec -T web sh -c "odoo shell -d gvnn --no-http < /tmp/check.py > /tmp/check.out 2>&1; grep -E '^FAIL|TOTAL|Traceback' /tmp/check.out"
```

Với `check_phase6_import.py`, copy file Excel vào container trước:
`docker compose cp "TỔNG HỢP_GVNN.xlsx" web:/tmp/gvnn.xlsx`. Các script chạy được cả khi DB đã có dữ liệu thật, nhưng nên chạy trên DB trống hoặc DB thử để số đếm không lẫn.
